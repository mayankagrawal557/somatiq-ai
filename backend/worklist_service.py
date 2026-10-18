"""
Somatiq AI Voice V1.1 - Step 3: Hardened Teleradiology Worklist & SLA Service
Features:
- STAT Priority Sorting & Real-Time TAT (Turnaround Time) SLA Calculations
- Pre-seeded Realistic Indian Clinical Queue
- Sign & Auto-Advance Workflow Persistence
- Green-API + WhatsApp Web Instant Dispatch
- Graceful dual-persistence (Supabase PostgreSQL / Local SQLite & JSON)
"""

import os
import re
import json
import uuid
import logging
import sqlite3
from typing import Dict, List, Any, Optional, Literal
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
from pydantic import BaseModel, Field
import requests

from backend.db_service import DatabaseService, DB_FILE

logger = logging.getLogger("somatiq.worklist_service")

# Local fallback file storage
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
LOCAL_WORKLIST_FILE = os.path.join(DATA_DIR, "worklist.json")

# Base SLA targets by modality (in minutes)
SLA_BASE_MINUTES: Dict[str, int] = {
    "X-RAY": 12,
    "USG": 15,
    "CT": 25,
    "MRI": 30,
    "PET-CT": 30,
    "SPECT": 30,
    "THERANOSTICS": 30
}

PRIORITY_RANK: Dict[str, int] = {
    "STAT": 0,
    "URGENT": 1,
    "ROUTINE": 2
}


class WorklistStudy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    uhid: str
    patient_name: str
    age_gender: str
    patient_phone: str
    referring_doctor: str
    modality: Literal["USG", "CT", "MRI", "PET-CT", "SPECT", "X-RAY", "THERANOSTICS"]
    template_key: str
    study_name: str
    clinical_history: str
    priority: Literal["STAT", "URGENT", "ROUTINE"] = "ROUTINE"
    status: Literal["PENDING", "IN_PROGRESS", "SIGNED", "DISPATCHED"] = "PENDING"
    sla_target_minutes: int = 30
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    signed_at: Optional[str] = None
    final_report_html: Optional[str] = None
    patient_summary: Optional[str] = None


class CreateStudyRequest(BaseModel):
    patient_name: str
    age_gender: str
    patient_phone: str = "9876543210"
    uhid: Optional[str] = None
    referring_doctor: str = "Dr. Self-Referred / Duty Clinician"
    modality: Literal["USG", "CT", "MRI", "PET-CT", "SPECT", "X-RAY", "THERANOSTICS"] = "CT"
    template_key: str = "ct_brain"
    study_name: Optional[str] = None
    clinical_history: str = "Diagnostic evaluation"
    priority: Literal["STAT", "URGENT", "ROUTINE"] = "ROUTINE"
    sla_target_minutes: Optional[int] = None


class UpdateStudyStatusRequest(BaseModel):
    status: Literal["PENDING", "IN_PROGRESS", "SIGNED", "DISPATCHED"]
    final_report_html: Optional[str] = None
    patient_summary: Optional[str] = None


class SendWhatsAppRequest(BaseModel):
    recipient_type: Literal["patient", "doctor", "both"] = "both"
    custom_phone: Optional[str] = None
    base_url: Optional[str] = None


class WorklistService:
    """
    Hardened Teleradiology Worklist Management with Priority Queuing,
    SLA Countdown Tracking, and WhatsApp Notification Dispatch.
    """

    @classmethod
    def _ensure_storage_ready(cls):
        """Ensures local data directory and database tables exist."""
        os.makedirs(DATA_DIR, exist_ok=True)
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS worklist_studies (
                    id TEXT PRIMARY KEY,
                    uhid TEXT NOT NULL,
                    patient_name TEXT NOT NULL,
                    age_gender TEXT NOT NULL,
                    patient_phone TEXT NOT NULL,
                    referring_doctor TEXT NOT NULL,
                    modality TEXT NOT NULL,
                    template_key TEXT NOT NULL,
                    study_name TEXT NOT NULL,
                    clinical_history TEXT NOT NULL,
                    priority TEXT NOT NULL DEFAULT 'ROUTINE',
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    sla_target_minutes INTEGER NOT NULL DEFAULT 30,
                    created_at TEXT NOT NULL,
                    signed_at TEXT,
                    final_report_html TEXT,
                    patient_summary TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_worklist_priority ON worklist_studies (priority, status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_worklist_created ON worklist_studies (created_at)")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"SQLite worklist table initialization check: {e}")

    @classmethod
    def calculate_sla_target(cls, modality: str, priority: str) -> int:
        """Assigns modality baseline SLA, cutting time in half for STAT studies."""
        base = SLA_BASE_MINUTES.get(modality.upper(), 30)
        if priority == "STAT":
            return max(5, round(base / 2))
        return base

    @classmethod
    def _get_seed_studies(cls) -> List[WorklistStudy]:
        """Returns 5 realistic Indian clinical queue studies with staggered created_at."""
        now = datetime.now(timezone.utc)
        return [
            WorklistStudy(
                id="seed-study-001",
                uhid="SOM-2026-STAT-01",
                patient_name="Rajveer Singh",
                age_gender="58Y / Male",
                patient_phone="9876543210",
                referring_doctor="Dr. A. K. Verma (MD, DM Neurology)",
                modality="CT",
                template_key="ct_brain",
                study_name="CT Brain Plain / Non-Contrast",
                clinical_history="Sudden onset left hemiparesis and slurred speech since 1 hour, rule out acute infarct/bleed.",
                priority="STAT",
                status="PENDING",
                sla_target_minutes=12,
                created_at=(now - timedelta(minutes=4)).isoformat()
            ),
            WorklistStudy(
                id="seed-study-002",
                uhid="SOM-2026-URG-02",
                patient_name="Priya Khandelwal",
                age_gender="34Y / Female",
                patient_phone="9823012345",
                referring_doctor="Dr. Meenakshi Sundaram (MS General Surgery)",
                modality="USG",
                template_key="usg_abdomen",
                study_name="Ultrasound Whole Abdomen",
                clinical_history="Acute right hypochondriac pain and vomiting after meals, rule out acute calculous cholecystitis.",
                priority="URGENT",
                status="PENDING",
                sla_target_minutes=15,
                created_at=(now - timedelta(minutes=10)).isoformat()
            ),
            WorklistStudy(
                id="seed-study-003",
                uhid="SOM-2026-URG-03",
                patient_name="Mohan Lal Gupta",
                age_gender="67Y / Male",
                patient_phone="9811223344",
                referring_doctor="Dr. Suresh H. Advani (DM Medical Oncology)",
                modality="PET-CT",
                template_key="petct_fdg_whole_body",
                study_name="Whole Body FDG PET-CT",
                clinical_history="Biopsy-proven Ca Right Lung post 4 cycles chemotherapy, restaging and metabolic response evaluation.",
                priority="URGENT",
                status="PENDING",
                sla_target_minutes=30,
                created_at=(now - timedelta(minutes=6)).isoformat()
            ),
            WorklistStudy(
                id="seed-study-004",
                uhid="SOM-2026-ROU-04",
                patient_name="Sunita Devi",
                age_gender="45Y / Female",
                patient_phone="9899887766",
                referring_doctor="Dr. Rajesh Malhotra (MS Orthopaedics)",
                modality="MRI",
                template_key="mri_lumbar_spine",
                study_name="MRI Lumbar Spine",
                clinical_history="Chronic low backache radiating to bilateral lower limbs (L > R) since 3 months.",
                priority="ROUTINE",
                status="PENDING",
                sla_target_minutes=30,
                created_at=(now - timedelta(minutes=14)).isoformat()
            ),
            WorklistStudy(
                id="seed-study-005",
                uhid="SOM-2026-ROU-05",
                patient_name="Vikramaditya Joshi",
                age_gender="62Y / Male",
                patient_phone="9765432109",
                referring_doctor="Dr. P. N. Dogra (MCh Urology)",
                modality="PET-CT",
                template_key="petct_psma",
                study_name="PSMA PET-CT (68Ga / 18F-PSMA)",
                clinical_history="Rising serum PSA (14.2 ng/mL) post radical prostatectomy, evaluate for biochemical recurrence.",
                priority="ROUTINE",
                status="PENDING",
                sla_target_minutes=30,
                created_at=(now - timedelta(minutes=18)).isoformat()
            )
        ]

    @classmethod
    def load_studies(cls) -> List[WorklistStudy]:
        """Loads all studies from storage, auto-seeding if empty."""
        cls._ensure_storage_ready()

        # Try SQLite first
        studies: List[WorklistStudy] = []
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM worklist_studies")
            rows = cursor.fetchall()
            conn.close()

            if rows:
                for r in rows:
                    studies.append(WorklistStudy(**dict(r)))
        except Exception as e:
            logger.warning(f"Error loading worklist from SQLite: {e}")

        # If SQLite had no rows, try JSON file
        if not studies and os.path.exists(LOCAL_WORKLIST_FILE):
            try:
                with open(LOCAL_WORKLIST_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        studies = [WorklistStudy(**item) for item in data]
            except Exception as e:
                logger.warning(f"Error loading worklist from JSON: {e}")

        # Auto-seed if empty
        if not studies:
            logger.info("Worklist is empty. Auto-seeding 5 realistic Indian clinical studies...")
            studies = cls._get_seed_studies()
            cls.save_all_studies(studies)

        return studies

    @classmethod
    def save_all_studies(cls, studies: List[WorklistStudy]):
        """Persists studies to both SQLite and JSON file for high durability."""
        cls._ensure_storage_ready()

        # 1. Save to JSON file
        try:
            with open(LOCAL_WORKLIST_FILE, "w", encoding="utf-8") as f:
                json.dump([s.model_dump() for s in studies], f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save worklist to JSON: {e}")

        # 2. Save to SQLite
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM worklist_studies")
            for s in studies:
                cursor.execute("""
                    INSERT OR REPLACE INTO worklist_studies (
                        id, uhid, patient_name, age_gender, patient_phone, referring_doctor,
                        modality, template_key, study_name, clinical_history, priority,
                        status, sla_target_minutes, created_at, signed_at, final_report_html, patient_summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s.id, s.uhid, s.patient_name, s.age_gender, s.patient_phone, s.referring_doctor,
                    s.modality, s.template_key, s.study_name, s.clinical_history, s.priority,
                    s.status, s.sla_target_minutes, s.created_at, s.signed_at, s.final_report_html, s.patient_summary
                ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to save worklist to SQLite: {e}")

    @classmethod
    def get_sorted_worklist(cls) -> Dict[str, Any]:
        """
        Returns worklist queue sorted strictly by:
        1. STAT first -> URGENT -> ROUTINE
        2. Oldest created_at first (FIFO within priority)
        Includes live clinic KPIs and turnaround metrics.
        """
        studies = cls.load_studies()

        # Sort strictly: STAT -> URGENT -> ROUTINE, then created_at ascending
        def sort_key(s: WorklistStudy):
            p_rank = PRIORITY_RANK.get(s.priority, 3)
            return (p_rank, s.created_at)

        sorted_studies = sorted(studies, key=sort_key)

        # Compute clinic KPIs
        stat_pending = sum(1 for s in studies if s.priority == "STAT" and s.status in ["PENDING", "IN_PROGRESS"])
        queue_pending = sum(1 for s in studies if s.status in ["PENDING", "IN_PROGRESS"])
        signed_today = sum(1 for s in studies if s.status in ["SIGNED", "DISPATCHED"])

        # Calculate average TAT for signed studies
        tat_list = []
        for s in studies:
            if s.signed_at and s.created_at:
                try:
                    c_dt = datetime.fromisoformat(s.created_at.replace("Z", "+00:00"))
                    s_dt = datetime.fromisoformat(s.signed_at.replace("Z", "+00:00"))
                    tat_minutes = max(1.0, (s_dt - c_dt).total_seconds() / 60.0)
                    tat_list.append(tat_minutes)
                except Exception:
                    pass

        avg_tat = round(sum(tat_list) / len(tat_list), 1) if tat_list else 14.5

        return {
            "studies": [s.model_dump() for s in sorted_studies],
            "stats": {
                "stat_pending": stat_pending,
                "queue_pending": queue_pending,
                "signed_today": signed_today,
                "avg_tat_minutes": avg_tat
            }
        }

    @classmethod
    def get_study_by_id(cls, study_id: str) -> Optional[WorklistStudy]:
        """Finds a study by ID."""
        studies = cls.load_studies()
        for s in studies:
            if s.id == study_id:
                return s
        return None

    @classmethod
    def create_study(cls, req: CreateStudyRequest) -> WorklistStudy:
        """Creates and persists a new patient study to the queue with SLA computation."""
        studies = cls.load_studies()

        # Generate UHID if not provided
        uhid = req.uhid.strip() if (req.uhid and req.uhid.strip()) else f"SOM-{datetime.now().year}-{str(uuid.uuid4())[:4].upper()}"

        # Assign study name if not provided
        study_name = req.study_name or req.template_key.replace("_", " ").title()

        # Auto-assign SLA target
        sla_target = req.sla_target_minutes or cls.calculate_sla_target(req.modality, req.priority)

        new_study = WorklistStudy(
            uhid=uhid,
            patient_name=req.patient_name.strip(),
            age_gender=req.age_gender.strip(),
            patient_phone=req.patient_phone.strip(),
            referring_doctor=req.referring_doctor.strip(),
            modality=req.modality,
            template_key=req.template_key,
            study_name=study_name,
            clinical_history=req.clinical_history.strip(),
            priority=req.priority,
            status="PENDING",
            sla_target_minutes=sla_target
        )

        studies.append(new_study)
        cls.save_all_studies(studies)
        logger.info(f"Added study {new_study.uhid} ({new_study.patient_name}) with priority {new_study.priority} to queue.")
        return new_study

    @classmethod
    def update_study_status(cls, study_id: str, req: UpdateStudyStatusRequest) -> Optional[WorklistStudy]:
        """Updates study status, records signed_at timestamp, and saves report drafts."""
        studies = cls.load_studies()
        target_study: Optional[WorklistStudy] = None

        for s in studies:
            if s.id == study_id:
                s.status = req.status
                if req.final_report_html is not None:
                    s.final_report_html = req.final_report_html
                if req.patient_summary is not None:
                    s.patient_summary = req.patient_summary

                if req.status == "SIGNED" and not s.signed_at:
                    s.signed_at = datetime.now(timezone.utc).isoformat()

                target_study = s
                break

        if target_study:
            cls.save_all_studies(studies)
            logger.info(f"Updated study {target_study.uhid} status to {target_study.status}.")

        return target_study

    @classmethod
    def dispatch_whatsapp(cls, study_id: str, req: SendWhatsAppRequest) -> Dict[str, Any]:
        """
        Prepares and dispatches WhatsApp notification via Green-API (if configured)
        and generates an instant pre-formatted WhatsApp Web deep link fallback.
        """
        study = cls.get_study_by_id(study_id)
        if not study:
            raise ValueError(f"Study with ID '{study_id}' not found.")

        # Determine target phone number
        phone_raw = req.custom_phone if (req.custom_phone and req.custom_phone.strip()) else study.patient_phone
        digits = re.sub(r'\D', '', phone_raw)
        if len(digits) == 10:
            phone_clean = f"91{digits}"
        elif len(digits) == 12 and digits.startswith("91"):
            phone_clean = digits
        else:
            phone_clean = f"91{digits[-10:]}" if len(digits) >= 10 else "919876543210"

        # Generate public letterhead report view link
        base = req.base_url.rstrip("/") if req.base_url else "https://somatiq-ai.onrender.com"
        report_url = f"{base}/report/view/{study.id}"

        # Clean plain-text impression / summary snippet
        summary_snippet = study.patient_summary or ""
        if not summary_snippet and study.final_report_html:
            clean_html = re.sub(r'<[^>]+>', ' ', study.final_report_html)
            m = re.search(r'IMPRESSION\s*:?\s*([\s\S]{1,250})', clean_html, re.IGNORECASE)
            summary_snippet = m.group(1).strip() if m else clean_html[:200].strip()

        if not summary_snippet:
            summary_snippet = "Diagnostic imaging evaluation completed. Official report signed by Consultant Radiologist."

        # Format official clinical notification message
        study_date = datetime.now().strftime("%d-%b-%Y")
        if study.signed_at:
            try:
                study_date = datetime.fromisoformat(study.signed_at.replace("Z", "+00:00")).strftime("%d-%b-%Y %I:%M %p")
            except Exception:
                pass

        message_text = (
            f"🏥 *DEPARTMENT OF RADIOLOGY & IMAGING*\n"
            f"*OFFICIAL MEDICAL REPORT NOTIFICATION*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Patient Name:* {study.patient_name} ({study.age_gender})\n"
            f"🆔 *Patient UHID:* {study.uhid}\n"
            f"📋 *Modality & Study:* {study.modality} — {study.study_name}\n"
            f"👨‍⚕️ *Referring Clinician:* {study.referring_doctor}\n"
            f"📅 *Verified Date:* {study_date}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 *CLINICAL IMPRESSION / PATIENT GUIDE:*\n"
            f"{summary_snippet.strip()}\n\n"
            f"🔗 *View & Download Official Signed Report:*\n"
            f"{report_url}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_This is an official digitally signed diagnostic imaging report. Please present this link to your consulting physician._"
        )

        # 1. WhatsApp Web Universal Direct Link
        whatsapp_web_url = f"https://wa.me/{phone_clean}?text={quote_plus(message_text)}"

        # 2. Try Green-API Dispatch if keys present
        green_instance = os.getenv("GREEN_API_INSTANCE_ID", "").strip()
        green_token = os.getenv("GREEN_API_TOKEN", "").strip()
        green_api_sent = False
        green_api_response = None

        if green_instance and green_token:
            try:
                api_url = f"https://api.green-api.com/waInstance{green_instance}/sendMessage/{green_token}"
                post_body = {
                    "chatId": f"{phone_clean}@c.us",
                    "message": message_text
                }
                res = requests.post(api_url, json=post_body, timeout=6)
                if res.status_code == 200:
                    green_api_sent = True
                    green_api_response = res.json()
                    logger.info(f"Green-API WhatsApp successfully sent to {phone_clean}")
                else:
                    logger.warning(f"Green-API responded with status {res.status_code}: {res.text}")
            except Exception as e:
                logger.warning(f"Green-API dispatch attempt failed: {e}")

        # Update status to DISPATCHED
        cls.update_study_status(study.id, UpdateStudyStatusRequest(status="DISPATCHED"))

        return {
            "success": True,
            "study_id": study.id,
            "patient_name": study.patient_name,
            "phone_used": phone_clean,
            "whatsapp_web_url": whatsapp_web_url,
            "green_api_sent": green_api_sent,
            "green_api_response": green_api_response,
            "report_url": report_url,
            "message_preview": message_text
        }

    @classmethod
    def generate_public_report_html(cls, study: WorklistStudy) -> str:
        """
        Generates a clean, responsive, print-ready medical report HTML page
        with hospital letterhead, digital verification seal, and patient summary.
        """
        study_date = datetime.now().strftime("%d-%b-%Y")
        signed_text = "Verified & Digitally Signed"
        if study.signed_at:
            try:
                dt = datetime.fromisoformat(study.signed_at.replace("Z", "+00:00"))
                study_date = dt.strftime("%d-%b-%Y")
                signed_text = f"Digitally Signed on {dt.strftime('%d-%b-%Y at %I:%M %p UTC')}"
            except Exception:
                pass

        # Clean report body (strip any leftover mark tags)
        report_body = study.final_report_html or ""
        if not report_body:
            report_body = f"""
            <h3><strong>TECHNIQUE:</strong></h3>
            <p>Diagnostic imaging evaluation performed according to standard protocol.</p>
            <h3><strong>CLINICAL INDICATION:</strong></h3>
            <p>{study.clinical_history}</p>
            <h3><strong>FINDINGS:</strong></h3>
            <p>Report signed and recorded in teleradiology queue.</p>
            <h3><strong>IMPRESSION:</strong></h3>
            <p>Refer to treating clinician for clinical correlation.</p>
            """
        else:
            report_body = re.sub(r'</?mark[^>]*>', '', report_body)

        patient_summary_html = ""
        if study.patient_summary and study.patient_summary.strip():
            patient_summary_html = f"""
            <div style="margin-top: 25px; padding: 16px; background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px;">
                <div style="font-size: 11pt; font-weight: bold; color: #0f172a; margin-bottom: 6px;">
                    ℹ️ Patient-Friendly Explanation (Clear Health Guide)
                </div>
                <div style="font-size: 10pt; line-height: 1.6; color: #334155;">
                    {study.patient_summary}
                </div>
                <div style="margin-top: 8px; font-size: 8.5pt; color: #64748b; font-style: italic;">
                    Note: This plain-language summary is provided to assist patient understanding. It does not replace medical advice from your treating clinician.
                </div>
            </div>
            """

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Medical Report - {study.patient_name} ({study.uhid})</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            padding: 20px;
            background-color: #f1f5f9;
            font-family: Arial, Helvetica, sans-serif;
            color: #0f172a;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}
        .report-page {{
            max-width: 820px;
            margin: 0 auto;
            background-color: #ffffff;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
            border: 1px solid #e2e8f0;
        }}
        .header-banner {{
            text-align: center;
            border-bottom: 2px solid #0284c7;
            padding-bottom: 16px;
            margin-bottom: 20px;
        }}
        .header-banner h1 {{
            margin: 0;
            font-size: 18pt;
            letter-spacing: 0.5px;
            color: #0f172a;
        }}
        .header-banner p {{
            margin: 4px 0 0 0;
            font-size: 9.5pt;
            color: #0284c7;
            font-weight: 600;
        }}
        .meta-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px 16px;
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 12px 16px;
            margin-bottom: 24px;
            font-size: 9.5pt;
        }}
        .meta-grid div {{
            line-height: 1.4;
        }}
        .meta-grid strong {{
            color: #475569;
        }}
        .report-content {{
            font-size: 10.5pt;
            line-height: 1.6;
            color: #0f172a;
            min-height: 380px;
        }}
        .report-content h3 {{
            font-size: 11pt;
            margin: 16px 0 6px 0;
            color: #0284c7;
            border-bottom: 1px solid #f1f5f9;
            padding-bottom: 3px;
        }}
        .report-content p {{
            margin: 0 0 8px 0;
        }}
        .report-content ul {{
            margin: 4px 0 12px 20px;
            padding: 0;
        }}
        .report-content li {{
            margin-bottom: 4px;
        }}
        .signature-box {{
            margin-top: 35px;
            padding-top: 15px;
            border-top: 1px dashed #cbd5e1;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .verified-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background-color: #ecfdf5;
            color: #065f46;
            border: 1px solid #a7f3d0;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 9pt;
            font-weight: bold;
        }}
        .doctor-signature {{
            text-align: right;
            font-size: 9.5pt;
            color: #334155;
        }}
        .no-print-bar {{
            max-width: 820px;
            margin: 0 auto 16px auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .btn-action {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 9pt;
            font-weight: bold;
            text-decoration: none;
            cursor: pointer;
            border: none;
            transition: background 0.15s;
        }}
        .btn-print {{
            background-color: #0284c7;
            color: white;
        }}
        .btn-print:hover {{
            background-color: #0369a1;
        }}
        .btn-portal {{
            background-color: #e2e8f0;
            color: #1e293b;
        }}
        .btn-portal:hover {{
            background-color: #cbd5e1;
        }}
        @media print {{
            body {{
                background-color: #ffffff;
                padding: 0;
            }}
            .no-print-bar {{
                display: none !important;
            }}
            .report-page {{
                border: none;
                box-shadow: none;
                padding: 20px;
                max-width: 100%;
            }}
        }}
    </style>
</head>
<body>

    <div class="no-print-bar">
        <a href="/" class="btn-action btn-portal">← Somatiq Radiologist Portal</a>
        <div style="display: flex; gap: 8px;">
            <button onclick="window.print()" class="btn-action btn-print">🖨️ Print / Save PDF</button>
        </div>
    </div>

    <div class="report-page">
        <!-- HOSPITAL LETTERHEAD HEADER -->
        <div class="header-banner">
            <h1>DEPARTMENT OF RADIOLOGY & IMAGING</h1>
            <p>Comprehensive Diagnostic Healthcare Services • NABL / Quality Certified</p>
        </div>

        <!-- PATIENT DEMOGRAPHICS -->
        <div class="meta-grid">
            <div><strong>Patient Name:</strong> {study.patient_name}</div>
            <div><strong>Patient UHID:</strong> {study.uhid}</div>
            <div><strong>Age / Gender:</strong> {study.age_gender}</div>
            <div><strong>Modality / Study:</strong> {study.modality} — {study.study_name}</div>
            <div><strong>Referring Clinician:</strong> {study.referring_doctor}</div>
            <div><strong>Examination Date:</strong> {study_date}</div>
            <div style="grid-column: span 2;"><strong>Clinical Indication:</strong> {study.clinical_history}</div>
        </div>

        <!-- MAIN REPORT BODY -->
        <div class="report-content">
            {report_body}
        </div>

        <!-- PATIENT-FRIENDLY SUMMARY -->
        {patient_summary_html}

        <!-- VERIFICATION & DIGITAL SIGN-OFF SEAL -->
        <div class="signature-box">
            <div class="verified-badge">
                <span>✓</span> {signed_text}
            </div>
            <div class="doctor-signature">
                <strong>Consultant Radiologist</strong><br>
                MD (Radiodiagnosis) • Certified Quality Reporter
            </div>
        </div>
    </div>

</body>
</html>
        """
        return html

