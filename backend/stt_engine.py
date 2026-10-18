"""
Speech-to-Text Pipeline (Dual-Mode Architecture)
Mode A: Local Whisper / Fast VAD chunk transcriber (CTranslate2 or fallback)
Mode B: Cloud / Low-Resource Fallback (Groq Whisper-large-v3 or Gemini Audio API)
"""

import os
import io
import wave
import tempfile
import urllib.request
import json
from typing import Dict, Any, Optional

from backend.medical_vocab import RADIOLOGY_INITIAL_PROMPT, RADIOLOGY_HOTWORDS

# STT Mode configuration
STT_MODE = os.getenv("STT_MODE", "cloud_fallback").lower()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")

class SpeechToTextEngine:
    """
    Unified STT engine handling real-time audio chunk transcription.
    Automatically routes between local faster-whisper and cloud fallback.
    """

    _local_model = None

    @classmethod
    def get_local_model(cls):
        """Loads faster-whisper model lazily if available locally."""
        if cls._local_model is None:
            try:
                from faster_whisper import WhisperModel
                # Load small or base model for low-latency CPU transcription
                cls._local_model = WhisperModel("base.en", device="cpu", compute_type="int8")
            except Exception as e:
                cls._local_model = False
        return cls._local_model

    @classmethod
    def cleanup_memory(cls):
        """
        Frees up memory and PyTorch VRAM if applicable.
        Invoked after client disconnection or heavy batch transcriptions.
        """
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    @classmethod
    def transcribe_audio_bytes(
        cls,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribes audio bytes with medical vocabulary boosting.
        Zero-logging of audio payload content for HIPAA/DISHA compliance.
        """
        if not audio_bytes or len(audio_bytes) < 100:
            return {"text": "", "engine": "empty_payload"}

        initial_prompt = prompt or RADIOLOGY_INITIAL_PROMPT

        # Try Mode A (Local Faster-Whisper) if configured and installed
        if STT_MODE == "local":
            model = cls.get_local_model()
            if model and model is not False:
                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        tmp.write(audio_bytes)
                        tmp_path = tmp.name

                    from backend.context_biasing import WHISPER_ANTI_HALLUCINATION_CONFIG
                    anti_hal = dict(WHISPER_ANTI_HALLUCINATION_CONFIG)
                    segments, info = model.transcribe(
                        tmp_path,
                        beam_size=anti_hal.get("beam_size", 5),
                        initial_prompt=initial_prompt,
                        condition_on_previous_text=anti_hal.get("condition_on_previous_text", False),
                        no_speech_threshold=anti_hal.get("no_speech_threshold", 0.6),
                        log_prob_threshold=anti_hal.get("log_prob_threshold", -1.0),
                        compression_ratio_threshold=anti_hal.get("compression_ratio_threshold", 2.2),
                        vad_filter=True,
                        vad_parameters=dict(min_silence_duration_ms=400)
                    )
                    transcription = " ".join(seg.text for seg in segments).strip()
                    return {"text": transcription, "engine": "faster_whisper_local"}
                except Exception as e:
                    pass
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass

        # Mode B1: Groq Cloud API if GROQ_API_KEY is available (whisper-large-v3-turbo for sub-second latency)
        groq_key = os.getenv("GROQ_API_KEY", "")
        if groq_key:
            try:
                # Groq Whisper endpoint
                url = "https://api.groq.com/openai/v1/audio/transcriptions"
                boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
                body = bytearray()
                
                # Model parameter (Turbo preferred for ultra-fast latency)
                body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\nwhisper-large-v3-turbo\r\n".encode('utf-8'))
                # Prompt parameter
                body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"prompt\"\r\n\r\n{initial_prompt}\r\n".encode('utf-8'))
                # Audio file
                body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: audio/wav\r\n\r\n".encode('utf-8'))
                body.extend(audio_bytes)
                body.extend(f"\r\n--{boundary}--\r\n".encode('utf-8'))

                req = urllib.request.Request(
                    url,
                    data=body,
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": f"multipart/form-data; boundary={boundary}"
                    }
                )
                with urllib.request.urlopen(req, timeout=12) as response:
                    res_json = json.loads(response.read().decode('utf-8'))
                    return {"text": res_json.get("text", "").strip(), "engine": "groq_whisper_v3"}
            except Exception as e:
                pass

        # Mode B2: Google Gemini Audio Fallback if GEMINI_API_KEY is available
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if gemini_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=gemini_key)
                mime = "audio/wav"
                fn_lower = filename.lower()
                if fn_lower.endswith(".mp3"):
                    mime = "audio/mp3"
                elif fn_lower.endswith(".m4a"):
                    mime = "audio/m4a"
                elif fn_lower.endswith(".webm") or fn_lower.endswith(".ogg"):
                    mime = "audio/webm"

                audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime)
                prompt = (
                    "Please accurately transcribe this audio recording of a doctor's medical radiology/nuclear medicine voice dictation.\n"
                    f"Contextual Vocabulary & Modality Guidance: {initial_prompt}\n"
                    "Return ONLY the verbatim transcription text. Do NOT add conversational replies, markdown greetings, or introductory phrases."
                )
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[prompt, audio_part]
                )
                transcription = response.text.strip().replace('"', '')
                if transcription:
                    return {"text": transcription, "engine": "gemini_audio_stt"}
            except Exception as e:
                pass

        # Mode B3: Unconfigured STT Fallback
        return {
            "text": "",
            "engine": "unconfigured",
            "error": "Audio file transcription requires GROQ_API_KEY or GEMINI_API_KEY on cloud deployments (or faster-whisper locally). Use live microphone dictation in Chrome/Edge for zero-key browser STT."
        }
