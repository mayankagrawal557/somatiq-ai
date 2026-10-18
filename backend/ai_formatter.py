"""
AI Report Auto-Formatter Module
Uses Google Gemini API (`google-genai` / REST) when an API key is configured.
Falls back safely to the deterministic zero-hallucination engine when no key is present.
"""

import os
import json
import urllib.request
from typing import Dict, Any, Optional

from backend.radiology_engine import RadiologyEngine, TEMPLATES

class AIReportFormatter:
    """
    Transforms raw, unedited voice notes into professional structured radiology reports.
    Strictly forbids clinical hallucinations.
    """

    @classmethod
    def format_report(
        cls,
        raw_dictation: str,
        template_id: str = "ct_brain",
        clinical_indication: str = "",
        technique_override: str = "",
        comparison: str = ""
    ) -> Dict[str, Any]:
        """
        Structures dictation using Gemini API if GEMINI_API_KEY is configured,
        or the deterministic safety parser if running in zero-cost offline mode.
        """
        gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        template = TEMPLATES.get(template_id, TEMPLATES["ct_brain"])

        if gemini_api_key:
            try:
                # Call Gemini API via official google.genai client
                from google import genai
                client = genai.Client(api_key=gemini_api_key)
                
                system_instruction = (
                    "You are a Senior Radiologist, Nuclear Medicine Physician, and Theranostics Specialist. "
                    "Your task is to organize raw voice dictation into a standard, structured medical report. "
                    "CRITICAL RULES:\n"
                    "1. DO NOT fabricate, guess, or invent any positive findings, measurements, SUVmax, or lesions not stated.\n"
                    "2. Retain all radiotracers, injected activities, anatomical regions, SUVmax values, and quantitative metrics (GFR, split function, ejection fraction).\n"
                    "3. For PET-CT: format findings by anatomical regions (Head & Neck, Thorax, Abdomen & Pelvis, Skeleton).\n"
                    "4. For Theranostics: format as a Therapy Administration & Post-Therapy Scintigraphy Summary (Administered activity, Pre-meds/Renal protection, Post-therapy scan findings, Radiation safety).\n"
                    "5. Return a clean JSON object with keys: 'examination', 'indication', 'comparison', 'technique', 'findings', and 'impression'."
                )

                user_prompt = f"""
Modality Template: {template['title']} ({template['modality']})
Category: {template.get('category', 'Diagnostic Imaging')}
Default Technique: {technique_override or template['technique']}
Clinical Indication: {clinical_indication or template['indication_default']}
Comparison: {comparison or template['comparison_default']}

RAW RADIOLOGY / NUCLEAR MEDICINE DICTATION:
\"\"\"{raw_dictation}\"\"\"

Format strictly into JSON with:
{{
  "examination": "string",
  "indication": "string",
  "comparison": "string",
  "technique": "string",
  "findings": "string (bulleted or structured organ-by-organ)",
  "impression": "string (numbered key conclusions and recommendations)"
}}
"""
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=user_prompt,
                    config=dict(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        temperature=0.1
                    )
                )

                parsed_json = json.loads(response.text)
                return {
                    "template_id": template["id"],
                    "template_title": template["title"],
                    "modality": template["modality"],
                    "body_part": template["body_part"],
                    "original_transcript": raw_dictation,
                    "sections": {
                        "examination": parsed_json.get("examination", template["title"]),
                        "indication": parsed_json.get("indication", clinical_indication or template["indication_default"]),
                        "comparison": parsed_json.get("comparison", comparison or template["comparison_default"]),
                        "technique": parsed_json.get("technique", technique_override or template["technique"]),
                        "findings": parsed_json.get("findings", ""),
                        "impression": parsed_json.get("impression", "")
                    },
                    "engine_used": "gemini-2.5-flash",
                    "is_draft": True
                }
            except Exception as e:
                # Fallback directly to deterministic clinical engine on API errors
                pass

        # Zero-cost Deterministic Engine (Offline / Local Mode)
        fallback_draft = RadiologyEngine.process_dictation(
            dictated_text=raw_dictation,
            template_id=template_id,
            clinical_indication=clinical_indication,
            technique_override=technique_override,
            comparison=comparison
        )
        fallback_draft["engine_used"] = "deterministic_clinical_engine_v1"
        return fallback_draft
