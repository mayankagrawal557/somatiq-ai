"""
Somatiq AI - Radiology Voice Dictation Assistant (V1)
FastAPI Backend Server
Features:
- WebSocket endpoint `/ws/dictate` for real-time audio chunk and text streaming
- Medical vocabulary booster & spoken voice command interception
- REST endpoint `POST /api/format-report` for AI report structuring (Gemini API + Deterministic fallback)
- Report persistence (SQLite), template management, and PACS clipboard export
"""

import os
import io
import json
import time
import logging
import asyncio
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend.radiology_engine import RadiologyEngine, TEMPLATES
from backend.nuclear_med_vocab import NUCLEAR_MED_TEMPLATES, NUCLEAR_MED_HOTWORDS, NUCLEAR_INITIAL_PROMPT
from backend.context_biasing import ContextBiasingEngine
from backend.phonetic_pipeline import Pass1PhoneticPipeline
from backend.phonetic_corrector import PhoneticCorrector
from backend.llm_post_corrector import LLMPostCorrector
from backend.voice_commands import VoiceCommandInterceptor
from backend.stt_engine import SpeechToTextEngine
from backend.quality_safety_checker import ClinicalQualityChecker, HANDBOOK_VOCAB_PATH
from backend.database import (
    init_db,
    save_report,
    get_all_reports,
    get_report_by_id,
    delete_report,
    save_custom_template,
    get_custom_templates
)
from backend.db_service import DatabaseService
from backend.smart_structurer import SmartStructurer
from backend.clinical_collaborator_service import ClinicalCollaboratorService, CollaboratorRequest, CollaboratorResponse

# Zero-PHI Production Logger (HIPAA/DISHA compliant)
logger = logging.getLogger("somatiq.production")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Initialize SQLite database
init_db()

class ConnectionManager:
    """
    Production-Hardened WebSocket Connection Manager:
    - Thread-safe connection registry with heartbeat monitoring
    - Per-connection bounded asyncio.Queue (maxsize=50) for backpressure & OOM protection
    - Dead/idle connection pruning
    - PyTorch & Python memory reclamation upon disconnect
    - Zero-PHI logging (HIPAA/DISHA compliant: no patient names, UHIDs, or dictated speech in logs)
    """
    def __init__(self):
        self.active_connections: Dict[WebSocket, Dict[str, Any]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> Dict[str, Any]:
        await websocket.accept()
        client_id = f"clinician_{id(websocket)}_{int(time.time()*1000)%100000}"
        conn_state = {
            "client_id": client_id,
            "connected_at": time.time(),
            "last_active": time.time(),
            "queue": asyncio.Queue(maxsize=50),
            "worker_task": None
        }
        async with self.lock:
            self.active_connections[websocket] = conn_state
        logger.info(f"[WS_CONNECT] Client connected: {client_id}. Active pool size: {len(self.active_connections)}")
        return conn_state

    async def disconnect(self, websocket: WebSocket):
        async with self.lock:
            conn_state = self.active_connections.pop(websocket, None)
        if conn_state:
            client_id = conn_state["client_id"]
            worker = conn_state.get("worker_task")
            if worker and not worker.done():
                worker.cancel()
            logger.info(f"[WS_DISCONNECT] Client disconnected: {client_id}. Active pool size: {len(self.active_connections)}")
        
        # Explicit PyTorch and Python memory cleanup
        SpeechToTextEngine.cleanup_memory()

    async def update_activity(self, websocket: WebSocket):
        async with self.lock:
            if websocket in self.active_connections:
                self.active_connections[websocket]["last_active"] = time.time()

    async def prune_idle_connections(self, idle_timeout: float = 300.0):
        """Prunes connections idle for > idle_timeout seconds to prevent leaks."""
        now = time.time()
        to_prune: List[WebSocket] = []
        async with self.lock:
            for ws, info in self.active_connections.items():
                if now - info["last_active"] > idle_timeout:
                    to_prune.append(ws)

        for ws in to_prune:
            try:
                await ws.close(code=1000, reason="Idle timeout")
            except Exception:
                pass
            await self.disconnect(ws)

    async def reaper_loop(self):
        """Background heartbeat reaper running every 30 seconds."""
        try:
            while True:
                await asyncio.sleep(30)
                await self.prune_idle_connections(idle_timeout=300.0)
        except asyncio.CancelledError:
            pass

    async def close_all(self):
        """Gracefully closes all sockets during server shutdown."""
        async with self.lock:
            sockets = list(self.active_connections.keys())
        for ws in sockets:
            try:
                await ws.close(code=1001, reason="Server shutting down")
            except Exception:
                pass
            await self.disconnect(ws)

manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load persistent custom lexicon rules from Supabase / SQLite into Pass-1 engine
    try:
        loaded = DatabaseService.load_lexicon_into_engine()
        logger.info(f"Persistent custom lexicon synchronized: {loaded} terms.")
    except Exception as e:
        logger.warning(f"Failed loading persistent lexicon: {e}")

    # Start dead connection pruner loop
    reaper = asyncio.create_task(manager.reaper_loop())
    yield
    # Cleanup on shutdown
    reaper.cancel()
    await manager.close_all()
    SpeechToTextEngine.cleanup_memory()

app = FastAPI(
    title="Somatiq AI - Radiology Voice Dictation Assistant",
    description="Real-time medical speech-to-text, voice command interceptor, and structured report auto-formatter",
    version="1.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Models
class FormatReportRequest(BaseModel):
    dictation_text: str
    template_id: str = "ct_brain"
    clinical_indication: Optional[str] = ""
    technique_override: Optional[str] = ""
    comparison: Optional[str] = ""

class VoiceCommandRequest(BaseModel):
    text: str

class TrainWordRequest(BaseModel):
    term: str
    misheard: Optional[str] = ""
    modality: Optional[str] = "all"

class DeleteWordRequest(BaseModel):
    term: str

class CorrectTextRequest(BaseModel):
    text: str

class QualityCheckRequest(BaseModel):
    text: str
    template_id: Optional[str] = "petct_fdg_whole_body"

class SaveReportRequest(BaseModel):
    id: Optional[int] = None
    patient_name: str = "Synthetic Patient"
    patient_age_sex: str = "45Y / M"
    patient_uhid: str = "SYN-987654"
    modality: str = "CT"
    body_part: str = "Brain"
    template_id: str = "ct_brain"
    dictation_transcript: str = ""
    original_transcript: Optional[str] = ""
    normalized_transcript: Optional[str] = ""
    examination: str = ""
    indication: str = ""
    comparison: str = ""
    technique: str = ""
    findings: str = ""
    impression: str = ""
    full_report: str = ""
    status: str = "DRAFT"
    uncertain_terms: Optional[Any] = []
    quality_flags: Optional[Any] = []
    report_sections: Optional[Any] = {}
    provenance: Optional[Any] = {}
    human_approval: Optional[Any] = {}

class SmartStructureRequest(BaseModel):
    template_key: str
    current_template_html: Optional[str] = ""
    raw_dictation: str
    patient_age_gender: Optional[str] = "45Y / M"
    modality: Optional[str] = "CT"

class MacroRequest(BaseModel):
    trigger_phrase: str
    expansion_text: str
    modality: Optional[str] = "all"

# Endpoints

@app.get("/api/health")
def health_check():
    gemini_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    groq_key = bool(os.getenv("GROQ_API_KEY"))
    return {
        "status": "healthy",
        "app": "Somatiq AI - Method 1 & 2 Radiology & Nuclear Medicine Voice Dictation Assistant",
        "gemini_api_configured": gemini_key,
        "groq_api_configured": groq_key,
        "active_templates": len(TEMPLATES),
        "method1_biasing": "Active (Contextual Decoder Profiles)",
        "method2_pass1": "Active (<5ms Sound-Alike + Metaphone)",
        "method2_pass2": "Active (Gemini 2.5 Flash Contextual Repair)" if gemini_key else "Ready (Requires GEMINI_API_KEY)"
    }

@app.get("/api/templates")
def get_templates_endpoint():
    """Returns all available starter clinical templates across Radiology and Nuclear Medicine."""
    starter = [
        {
            "id": k,
            "title": v.get("title", k),
            "modality": v.get("modality", ""),
            "body_part": v.get("body_part", v.get("category", "General")),
            "category": v.get("category", "Diagnostic Imaging"),
            "radiopharmaceutical": v.get("radiopharmaceutical", ""),
            "header_fields": v.get("header_fields", []),
            "sections": v.get("sections", []),
            "technique": v.get("technique", ""),
            "indication_default": v.get("indication_default", ""),
            "comparison_default": v.get("comparison_default", ""),
            "default_findings": v.get("default_findings", []),
            "default_impression": v.get("default_impression", "")
        }
        for k, v in TEMPLATES.items()
    ]
    return {"starter_templates": starter}

@app.get("/api/trained-words")
def list_trained_words():
    """Returns doctor-trained custom vocabulary terms."""
    return {"trained_words": PhoneticCorrector.get_trained_words()}

@app.post("/api/train-word")
def train_word_endpoint(req: TrainWordRequest):
    """
    Trains a new word with phonetic alias.
    Syncs with PhoneticCorrector, Pass1PhoneticPipeline, and DatabaseService for permanent cloud persistence.
    """
    term = req.term.strip()
    if not term:
        raise HTTPException(status_code=400, detail="Term is required")
    res = PhoneticCorrector.add_trained_word(term, req.misheard or "", req.modality or "all")
    if req.misheard and req.misheard.strip():
        Pass1PhoneticPipeline.add_custom_rule(req.misheard.strip(), term, req.modality or "General")
    else:
        Pass1PhoneticPipeline.add_hotword(term)

    try:
        DatabaseService.add_lexicon_term(req.misheard or "", term, req.modality or "all")
    except Exception as e:
        logger.warning(f"Could not persist trained word to DB: {e}")

    return res

@app.delete("/api/trained-words")
def delete_trained_word_endpoint(req: DeleteWordRequest):
    """Deletes a doctor-trained term from custom vocabulary, Pass-1 rules, and DB."""
    term = req.term.strip()
    if not term:
        raise HTTPException(status_code=400, detail="Term is required")
    deleted = PhoneticCorrector.delete_trained_word(term)
    Pass1PhoneticPipeline.delete_rule_by_term(term)
    try:
        DatabaseService.delete_lexicon_term(term)
    except Exception as e:
        logger.warning(f"Could not delete trained word from DB: {e}")
    return {"status": "success", "deleted": deleted, "term": term}

@app.get("/api/biasing-profile/{template_id}")
def get_biasing_profile(template_id: str):
    """Returns the Method 1 initial prompt and hotwords for the selected scan modality."""
    rules_data = Pass1PhoneticPipeline.load_custom_rules()
    custom_hotwords = rules_data.get("hotwords", [])
    prompt = ContextBiasingEngine.get_initial_prompt(template_id, custom_hotwords)
    hotwords = ContextBiasingEngine.get_hotwords_string(template_id, custom_hotwords)
    profile = ContextBiasingEngine.get_profile(template_id)
    return {
        "template_id": template_id,
        "category": profile.get("category"),
        "title": profile.get("title"),
        "initial_prompt": prompt,
        "hotwords": hotwords,
        "hotwords_count": len(hotwords.split(','))
    }

@app.post("/api/custom-rule")
def add_custom_rule_endpoint(data: Dict[str, Any]):
    """
    Adds a custom doctor-trained pronunciation rule and persists to custom_rules.json and DB.
    Immediately reloads in active pipeline without server restart.
    """
    pattern = data.get("pattern", "")
    replacement = data.get("replacement", "")
    category = data.get("category", "General")
    if not pattern or not replacement:
        raise HTTPException(status_code=400, detail="Pattern and replacement are required")
    res = Pass1PhoneticPipeline.add_custom_rule(pattern, replacement, category)
    try:
        DatabaseService.add_lexicon_term(pattern, replacement, category)
    except Exception as e:
        logger.warning(f"Could not persist custom rule to DB: {e}")
    return res

@app.get("/api/custom-rules")
def list_custom_rules_endpoint():
    """Lists all user-added custom pronunciation rules."""
    rules = Pass1PhoneticPipeline.get_custom_rules()
    return {"custom_rules": rules}

@app.get("/api/handbook/vocabulary")
def get_handbook_vocabulary():
    """
    Returns the complete structured vocabulary from the Nuclear Medicine Terminology Handbook,
    grouped by PET/CT, Gamma Camera / SPECT, Therapeutic Nuclear Medicine, Confusables, and Abbreviations.
    """
    if os.path.exists(HANDBOOK_VOCAB_PATH):
        with open(HANDBOOK_VOCAB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="Handbook vocabulary file not found")

@app.get("/api/handbook/vocabulary/csv")
def download_handbook_vocabulary_csv():
    """Returns the companion CSV export of the Nuclear Medicine Handbook vocabulary."""
    csv_path = os.path.join(os.path.dirname(__file__), "data", "nuclear_medicine_handbook_vocab.csv")
    if os.path.exists(csv_path):
        return FileResponse(
            csv_path,
            media_type="text/csv",
            filename="nuclear_medicine_handbook_vocab.csv"
        )
    raise HTTPException(status_code=404, detail="Handbook vocabulary CSV not found")

@app.post("/api/check-quality")
def check_quality_endpoint(req: QualityCheckRequest):
    """
    Clinical Quality & Uncertainty Flagging Engine:
    Inspects transcript for uncertain radiopharmaceuticals, laterality ambiguity,
    negation preservation, measurement decimals/sums, and activity units.
    """
    analysis = ClinicalQualityChecker.analyze_transcript(req.text, req.template_id or "")
    return analysis

@app.post("/api/format-report")
def format_report_endpoint(req: FormatReportRequest):
    """
    AI Report Structuring: Converts raw dictation into standardized clinical sections
    via Google Gemini 2.5 Flash (or zero-hallucination deterministic fallback).
    """
    result = LLMPostCorrector.structure_full_report(
        raw_dictation=req.dictation_text,
        template_id=req.template_id,
        clinical_indication=req.clinical_indication or "",
        technique_override=req.technique_override or "",
        comparison=req.comparison or ""
    )
    return result

@app.post("/api/smart-structure")
def smart_structure_endpoint(req: SmartStructureRequest):
    """
    One-Shot Smart AI Structuring Mode (Alt+S):
    Surgically merges raw voice dictation into baseline template HTML,
    enforcing anti-hallucination bounds, gender safety pruning, diff highlighting,
    and generating clinical impression and patient summaries.
    """
    return SmartStructurer.structure_and_merge(
        template_key=req.template_key,
        current_template_html=req.current_template_html or "",
        raw_dictation=req.raw_dictation or "",
        patient_age_gender=req.patient_age_gender or "45Y / M",
        modality=req.modality or "CT"
    )

@app.post("/api/clinical-collaborator", response_model=CollaboratorResponse)
def clinical_collaborator_endpoint(req: CollaboratorRequest):
    """
    RadOne AI Clinical Collaborator:
    Context-aware clinical co-pilot offering differential diagnoses,
    history/completeness cross-checks, senior impression synthesis, critical value triage,
    and free-text inquiry with outbound PII scrubbing and zero-hallucinated measurement bounds.
    """
    return ClinicalCollaboratorService.execute(req)

@app.get("/api/macros")
def get_macros_endpoint():
    """Lists all user-defined custom macros."""
    return {"macros": DatabaseService.get_macros()}

@app.post("/api/macros")
def add_macro_endpoint(req: MacroRequest):
    """Adds or updates a custom voice macro."""
    if not req.trigger_phrase or not req.expansion_text:
        raise HTTPException(status_code=400, detail="Trigger phrase and expansion text required")
    return DatabaseService.add_macro(req.trigger_phrase, req.expansion_text, req.modality or "all")

@app.delete("/api/macros")
def delete_macro_endpoint(req: Dict[str, str]):
    """Deletes a custom voice macro by trigger phrase."""
    trigger = req.get("trigger_phrase", "")
    if not trigger:
        raise HTTPException(status_code=400, detail="Trigger phrase is required")
    deleted = DatabaseService.delete_macro(trigger)
    return {"status": "success", "deleted": deleted}

@app.get("/api/letterhead-settings")
def get_letterhead_settings_endpoint():
    """Retrieves hospital print letterhead calibration settings."""
    return DatabaseService.get_letterhead_settings()

@app.post("/api/letterhead-settings")
def save_letterhead_settings_endpoint(settings: Dict[str, Any]):
    """Persists hospital print letterhead calibration settings."""
    return DatabaseService.save_letterhead_settings(settings)

@app.post("/api/transcribe-audio")
async def transcribe_audio(
    file: UploadFile = File(...),
    template_id: str = Form("petct_fdg_whole_body"),
    stt_mode: str = Form("dual")
):
    """
    Handles audio file uploads (.wav/.mp3/.m4a) with medical vocabulary boosting,
    Pass-1 phonetic correction, voice command expansion, and safety boundary checks.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio payload")
    
    stt_result = SpeechToTextEngine.transcribe_audio_bytes(
        audio_bytes=content,
        filename=file.filename or "recording.wav"
    )

    if stt_result.get("error") and not stt_result.get("text"):
        raise HTTPException(status_code=422, detail=stt_result["error"])

    raw_text = stt_result.get("text", "")

    # Stage 1 (Pass 1): Sub-5ms Deterministic Sound-Alike, Metaphone & SUVmax Normalizer
    pass1_text, pass1_repairs = Pass1PhoneticPipeline.process_pass1(raw_text)

    # Stage 2: Voice Command Interceptor & Spoken Macro Expansion
    parsed = VoiceCommandInterceptor.process_text(pass1_text)

    # Clinical Safety & Quality Check (Handbook Boundaries)
    safety_eval = ClinicalQualityChecker.analyze_transcript(raw_text, template_id)

    return {
        "status": "success",
        "raw_text": raw_text,
        "transcription": parsed["text"],
        "macro_applied": parsed["macro_applied"],
        "command": parsed.get("command"),
        "corrections_applied": pass1_repairs,
        "quality_flags": safety_eval["quality_flags"],
        "uncertain_terms": safety_eval["uncertain_terms"],
        "has_warnings": safety_eval["has_warnings"],
        "split_function_check": safety_eval.get("split_function_check"),
        "engine": stt_result.get("engine", "default")
    }

@app.post("/api/reports")
def save_report_endpoint(req: SaveReportRequest):
    report_dict = req.dict()
    report_id = save_report(report_dict)
    try:
        DatabaseService.save_report({
            "patient_name": req.patient_name,
            "age_gender": req.patient_age_sex,
            "modality": req.modality,
            "template_key": req.template_id,
            "raw_transcript": req.dictation_transcript or req.original_transcript or "",
            "final_report_html": req.full_report,
            "patient_summary": "",
            "status": req.status
        })
    except Exception as e:
        logger.warning(f"Could not sync report to DatabaseService: {e}")
    return {"status": "success", "report_id": report_id}

@app.get("/api/reports")
def list_reports():
    reports = get_all_reports()
    return {"reports": reports}

@app.get("/api/reports/{report_id}")
def get_single_report(report_id: int):
    rep = get_report_by_id(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail="Report not found")
    return rep

@app.delete("/api/reports/{report_id}")
def delete_single_report(report_id: int):
    ok = delete_report(report_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"status": "success", "deleted_id": report_id}

# WebSocket Endpoint for Live Dictation Streaming (Production Hardened)
@app.websocket("/ws/dictate")
async def websocket_dictate(websocket: WebSocket):
    """
    Real-time bidirectional WebSocket for voice streaming with:
    - ConnectionManager registry with idle dead-connection pruning
    - Bounded per-connection queue (maxsize=50) for OOM prevention & backpressure
    - Zero-PHI logging (HIPAA/DISHA compliance)
    - Full exception boundaries to safeguard Uvicorn worker integrity
    - PyTorch & Python memory reclamation upon disconnect
    """
    conn_state = await manager.connect(websocket)
    client_id = conn_state["client_id"]
    queue = conn_state["queue"]

    # Background worker consumer task per socket connection
    async def process_queue():
        while True:
            try:
                item = await queue.get()
                if item is None:
                    queue.task_done()
                    break

                item_type, payload = item

                if item_type == "text":
                    raw_text = payload.get("text", "")
                    active_template = payload.get("template_id", "petct_fdg_whole_body")
                    is_final = payload.get("is_final", True)

                    # Stage 1 (Pass 1): Sub-5ms Deterministic Sound-Alike, Metaphone & SUVmax Normalizer
                    pass1_text, pass1_repairs = Pass1PhoneticPipeline.process_pass1(raw_text)

                    # Stage 2: Voice Command Interceptor & Spoken Macro Expansion
                    processed = VoiceCommandInterceptor.process_text(pass1_text)
                    final_text = processed["text"]
                    all_repairs = list(pass1_repairs)

                    # Stage 3 (Pass 2): Gemini 2.5 Flash Contextual Repair on sentence completion (<150ms)
                    if is_final and len(final_text.split()) >= 3 and (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
                        try:
                            pass2_res = LLMPostCorrector.repair_sentence_contextual(final_text, active_template)
                            final_text = pass2_res.get("corrected_text", final_text)
                            for r in pass2_res.get("repairs_made", []):
                                all_repairs.append({"from": r.get("from", ""), "to": r.get("to", ""), "stage": "Pass-2 Gemini Flash"})
                        except Exception as e:
                            logger.warning(f"[PASS2_SKIP] Contextual LLM repair failed gracefully: {type(e).__name__}")

                    # Clinical Safety & Quality Check (Handbook Boundaries)
                    safety_eval = ClinicalQualityChecker.analyze_transcript(raw_text, active_template)

                    await websocket.send_json({
                        "type": "transcription_result",
                        "raw_text": raw_text,
                        "formatted_text": final_text,
                        "command": processed["command"],
                        "macro_applied": processed["macro_applied"],
                        "corrections_applied": all_repairs,
                        "quality_flags": safety_eval["quality_flags"],
                        "uncertain_terms": safety_eval["uncertain_terms"],
                        "has_warnings": safety_eval["has_warnings"],
                        "human_review_required": safety_eval["human_review_required"],
                        "split_function_check": safety_eval["split_function_check"]
                    })

                elif item_type == "bytes":
                    audio_bytes = payload
                    stt_res = SpeechToTextEngine.transcribe_audio_bytes(audio_bytes)
                    pass1_text, pass1_repairs = Pass1PhoneticPipeline.process_pass1(stt_res.get("text", ""))
                    processed = VoiceCommandInterceptor.process_text(pass1_text)
                    safety_eval = ClinicalQualityChecker.analyze_transcript(stt_res.get("text", ""), "petct_fdg_whole_body")
                    await websocket.send_json({
                        "type": "audio_chunk_transcribed",
                        "formatted_text": processed["text"],
                        "engine": stt_res.get("engine", "local"),
                        "corrections_applied": pass1_repairs,
                        "quality_flags": safety_eval["quality_flags"],
                        "uncertain_terms": safety_eval["uncertain_terms"],
                        "has_warnings": safety_eval["has_warnings"]
                    })

                queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[QUEUE_WORKER_ERROR] Task error for {client_id}: {type(e).__name__}")
                try:
                    await websocket.send_json({"type": "error", "message": "Dictation processing error."})
                except Exception:
                    pass

    worker_task = asyncio.create_task(process_queue())
    conn_state["worker_task"] = worker_task

    try:
        # Send initial connection confirmation with active hotwords and doctor-trained words
        rules_data = Pass1PhoneticPipeline.load_custom_rules()
        trained_words = rules_data.get("hotwords", [])
        init_profile = ContextBiasingEngine.get_profile("petct_fdg_whole_body")
        await websocket.send_json({
            "type": "connection_ready",
            "message": "Connected to Somatiq AI Voice Engine",
            "initial_prompt": init_profile.get("initial_prompt", ""),
            "hotwords_count": len(init_profile.get("hotwords", [])) + len(trained_words),
            "trained_words_count": len(trained_words),
            "client_id": client_id
        })

        while True:
            message = await websocket.receive()
            await manager.update_activity(websocket)

            if "text" in message:
                try:
                    data = json.loads(message["text"])
                except Exception:
                    logger.warning(f"[MALFORMED_PACKET] Received non-JSON payload from {client_id}")
                    continue

                msg_type = data.get("type", "text_segment")
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": time.time()})
                elif msg_type == "text_segment":
                    # Backpressure enforcement: if queue is full, drop oldest item to avoid OOM
                    if queue.full():
                        try:
                            _ = queue.get_nowait()
                            queue.task_done()
                            logger.warning(f"[BACKPRESSURE] Queue limit reached (50). Dropped oldest segment for {client_id} to prevent OOM.")
                        except Exception:
                            pass
                    await queue.put(("text", data))

            elif "bytes" in message:
                audio_bytes = message["bytes"]
                # Backpressure enforcement for binary audio chunks
                if queue.full():
                    try:
                        _ = queue.get_nowait()
                        queue.task_done()
                        logger.warning(f"[BACKPRESSURE] Audio queue limit reached (50). Dropped oldest chunk for {client_id} to prevent OOM.")
                    except Exception:
                        pass
                await queue.put(("bytes", audio_bytes))

    except WebSocketDisconnect:
        logger.info(f"[WS_DISCONNECT_EVENT] Client {client_id} disconnected cleanly.")
    except Exception as e:
        logger.warning(f"[WS_EXCEPTION] Socket exception for {client_id}: {type(e).__name__}")
    finally:
        await manager.disconnect(websocket)

# Serve Frontend
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_frontend():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
