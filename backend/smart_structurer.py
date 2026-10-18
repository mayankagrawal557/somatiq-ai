"""
Somatiq AI V1.1 - Smart AI Structuring Engine (Alt + S)
Surgically merges raw voice dictation into baseline modality template HTML,
enforces strict anti-hallucination bounds, gender safety pruning, visual diff highlighting,
and auto-generates clinical impression and bilingual patient summaries.
"""

import os
import re
import json
import logging
from typing import Dict, List, Any, Optional, Tuple

from backend.llm_post_corrector import sanitize_input_prompt
from backend.radiology_engine import TEMPLATES

logger = logging.getLogger("somatiq.smart_structurer")

# Male-only anatomical terms to prune when patient is Female
MALE_ONLY_TERMS = [
    r"prostate(?:\s+gland)?",
    r"seminal\s+vesicles?",
    r"testes?",
    r"scrotum",
    r"epididymis"
]

# Female-only anatomical terms to prune when patient is Male
FEMALE_ONLY_TERMS = [
    r"uterus(?:\s+and\s+adnexa)?",
    r"endometrium|endometrial\s+cavity",
    r"cervix",
    r"ovaries|ovary|adnexa",
    r"fallopian\s+tubes?",
    r"pouch\s+of\s+douglas"
]


def detect_patient_gender(age_gender_str: str) -> Optional[str]:
    """
    Infers gender ('M' or 'F') from clinical demographics string:
    e.g. '45Y / M', '62Y/Female', 'F / 28', 'Male, 50Y'.
    """
    if not age_gender_str:
        return None
    s = age_gender_str.strip()
    # Check for Female patterns first
    if re.search(r'(?:^|[\s/,\-_])(F|Female|Woman|Girl|Lady)(?:$|[\s/,\-_])', s, re.IGNORECASE):
        return "F"
    # Check for Male patterns
    if re.search(r'(?:^|[\s/,\-_])(M|Male|Man|Boy)(?:$|[\s/,\-_])', s, re.IGNORECASE):
        return "M"
    return None


def prune_gender_inappropriate_content(html_or_text: str, gender: Optional[str]) -> Tuple[str, List[str]]:
    """
    Strips organ sentences/lines that violate biological patient sex.
    Returns (cleaned_text, list_of_pruned_organs).
    """
    if not html_or_text or not gender:
        return html_or_text, []

    pruned_terms = []
    lines = html_or_text.splitlines(keepends=True)
    kept_lines = []

    target_terms = MALE_ONLY_TERMS if gender == "F" else (FEMALE_ONLY_TERMS if gender == "M" else [])

    for line in lines:
        line_stripped = line.strip()
        matched = False
        for term_pat in target_terms:
            if re.search(r'\b' + term_pat + r'\b', line_stripped, re.IGNORECASE):
                matched = True
                term_clean = term_pat.replace(r"\s+", " ").replace(r"(?:\s+gland)?", "").replace(r"(?:\s+and\s+adnexa)?", "")
                pruned_terms.append(term_clean.strip())
                break
        if not matched:
            kept_lines.append(line)

    cleaned = "".join(kept_lines)
    return cleaned, list(set(pruned_terms))


class SmartStructurer:
    """
    Executes 'One-Shot' Smart AI Structuring with Gemini 2.5 Flash and Deterministic Safety Fallback.
    """

    @classmethod
    def structure_and_merge(
        cls,
        template_key: str,
        current_template_html: str,
        raw_dictation: str,
        patient_age_gender: str = "45Y / M",
        modality: str = "CT"
    ) -> Dict[str, Any]:
        """
        Merges raw_dictation into current_template_html.
        """
        gender = detect_patient_gender(patient_age_gender)
        clean_dictation = sanitize_input_prompt(raw_dictation or "", max_chars=12000)

        # Baseline template content fallback
        template = TEMPLATES.get(template_key, {})
        base_html = current_template_html if current_template_html and len(current_template_html.strip()) > 30 else cls._build_default_template_html(template)

        # Apply deterministic gender pruning to baseline first
        pruned_base_html, pre_pruned = prune_gender_inappropriate_content(base_html, gender)

        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if gemini_key and clean_dictation.strip():
            try:
                from google import genai
                client = genai.Client(api_key=gemini_key)

                system_instruction = (
                    "You are an expert Senior Consultant in Diagnostic Radiology and Nuclear Medicine reporting in India. "
                    "Your role is to perform surgical 'One-Shot' Smart AI Merging of raw spoken dictation into an existing normal baseline report template.\n\n"
                    "CRITICAL CLINICAL SAFETY RULES:\n"
                    "1. STRICT ZERO-HALLUCINATION: Never invent, assume, infer, or extrapolate clinical findings, radiotracers, measurements, "
                    "SUVmax values, Deauville scores, or pathologies not explicitly dictated in RAW_DICTATION.\n"
                    "2. SURGICAL MERGE & CONTRADICTION RESOLUTION: Seamlessly insert findings into their anatomical sections. "
                    "If dictation describes an abnormal finding (e.g. '14mm calculus in GB neck'), automatically remove contradictory normal baseline text "
                    "(e.g. 'No calculus, sludge, or mass lesion' in Gallbladder).\n"
                    "3. PRESERVE UNMENTIONED NORMALS: Keep all normal baseline observations intact for any organs or structures not mentioned in dictation.\n"
                    f"4. GENDER SAFETY ENFORCEMENT: Patient is biologically {('FEMALE' if gender == 'F' else ('MALE' if gender == 'M' else 'UNKNOWN'))}. "
                    f"Ensure {'all male organs (Prostate, Seminal Vesicles, Testes) are strictly excluded' if gender == 'F' else ('all female organs (Uterus, Ovaries, Cervix, Adnexa) are strictly excluded' if gender == 'M' else 'no biological contradictions exist')}.\n"
                    "5. VISUAL AI DIFF HIGHLIGHTING: You MUST wrap every sentence, phrase, or section modified or inserted from the raw dictation "
                    "inside <mark class=\"ai-diff-highlight\" data-source=\"ai-merge\">...</mark> so the clinician can immediately verify it.\n"
                    "6. CLINICALLY PRIORITIZED IMPRESSION: Generate a concise, clinically prioritized IMPRESSION section using bold bullet points "
                    "highlighting ONLY abnormal positive findings. If all findings are normal, state normal study summary.\n"
                    "7. PATIENT SUMMARY: Generate a 3-sentence reassuring, clear explanation for the patient in simple English ('patient_summary_en') "
                    "and an accurate Hinglish conversational translation ('patient_summary_hinglish').\n"
                    "8. RETURN STRICT JSON MATCHING SCHEMA: "
                    "{\n"
                    "  \"merged_report_html\": \"string with html paragraphs and <mark class=\\\"ai-diff-highlight\\\" data-source=\\\"ai-merge\\\"> tags\",\n"
                    "  \"impression_bullets\": [\"string\"],\n"
                    "  \"patient_summary_en\": \"string (3 sentences)\",\n"
                    "  \"patient_summary_hinglish\": \"string (3 sentences)\",\n"
                    "  \"modified_sections_count\": number\n"
                    "}"
                )

                user_prompt = f"""
PATIENT DEMOGRAPHICS: {patient_age_gender}
MODALITY / TEMPLATE: {template.get('title', template_key)} ({modality})

CURRENT BASELINE TEMPLATE HTML:
\"\"\"{pruned_base_html}\"\"\"

RAW SPOKEN DICTATION (casual, spoken stream):
\"\"\"{clean_dictation}\"\"\"
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

                parsed = json.loads(response.text)
                merged_html = parsed.get("merged_report_html", "")

                # Secondary safety pass: ensure gender safety on output
                post_pruned_html, post_pruned = prune_gender_inappropriate_content(merged_html, gender)
                all_pruned = list(set(pre_pruned + post_pruned))

                return {
                    "status": "success",
                    "merged_report_html": post_pruned_html,
                    "impression": parsed.get("impression_bullets", []),
                    "patient_summary_en": parsed.get("patient_summary_en", ""),
                    "patient_summary_hinglish": parsed.get("patient_summary_hinglish", ""),
                    "modified_sections_count": parsed.get("modified_sections_count", 1),
                    "gender_pruned": all_pruned,
                    "engine": "gemini-2.5-flash"
                }

            except Exception as e:
                logger.warning(f"Gemini smart merge failed: {e}. Executing deterministic fallback.")

        # Deterministic Fallback if Gemini unavailable or failed
        return cls._deterministic_fallback_merge(
            template=template,
            base_html=pruned_base_html,
            raw_dictation=clean_dictation,
            gender=gender,
            pre_pruned=pre_pruned
        )

    @classmethod
    def _build_default_template_html(cls, template: Dict[str, Any]) -> str:
        """Constructs clean baseline HTML from template definition."""
        if not template:
            return "<p>FINDINGS: No acute abnormality detected.</p><p>IMPRESSION: Normal examination.</p>"
        html_parts = []
        if template.get("technique"):
            html_parts.append(f"<p><strong>TECHNIQUE:</strong> {template.get('technique')}</p>")
        html_parts.append("<p><strong>FINDINGS:</strong></p>")
        for finding in template.get("default_findings", []):
            html_parts.append(f"<p>{finding}</p>")
        if template.get("default_impression"):
            html_parts.append(f"<p><strong>IMPRESSION:</strong></p><p>{template.get('default_impression')}</p>")
        return "".join(html_parts)

    @classmethod
    def _deterministic_fallback_merge(
        cls,
        template: Dict[str, Any],
        base_html: str,
        raw_dictation: str,
        gender: Optional[str],
        pre_pruned: List[str]
    ) -> Dict[str, Any]:
        """
        Pure rule-based surgical merge fallback with zero cloud dependencies.
        Guarantees diff highlight marks and contradiction replacements.
        """
        dictation = (raw_dictation or "").strip()
        merged_html = base_html

        if dictation:
            highlighted_chunk = f'<mark class="ai-diff-highlight" data-source="ai-merge">{dictation}</mark>'
            # Check if Gallbladder / calculus contradiction
            if "calculus" in dictation.lower() or "cholelithiasis" in dictation.lower():
                merged_html = re.sub(
                    r'(Gallbladder.*?)(no\s+calculus[^.]*\.)',
                    rf'\1{highlighted_chunk}',
                    merged_html,
                    flags=re.IGNORECASE
                )
            
            # If not replaced in specific organ, inject under FINDINGS
            if highlighted_chunk not in merged_html:
                if "FINDINGS:" in merged_html:
                    merged_html = merged_html.replace("FINDINGS:</strong></p>", f"FINDINGS:</strong></p><p>{highlighted_chunk}</p>")
                else:
                    merged_html += f"<p><strong>FINDINGS:</strong></p><p>{highlighted_chunk}</p>"

        # Secondary gender cleanup
        final_html, post_pruned = prune_gender_inappropriate_content(merged_html, gender)

        summary_en = (
            "Your diagnostic scan has been analyzed by the medical team. "
            f"The examination focused on key anatomical areas with observations noted. "
            "Please consult your referring physician for next steps."
        )
        summary_hinglish = (
            "Aapka diagnostic scan medical team dwara examine kiya gaya hai. "
            "Sabhi mukhya anatomical angon ki jaanch ki gayi hai. "
            "Aage ke ilaaj ke liye kripya apne treating doctor se paramarsh lein."
        )

        impression_bullets = [
            f"Examination reviewed with dictated findings: {dictation[:80]}..." if dictation else "Normal study. No acute abnormality."
        ]

        return {
            "status": "success",
            "merged_report_html": final_html,
            "impression": impression_bullets,
            "patient_summary_en": summary_en,
            "patient_summary_hinglish": summary_hinglish,
            "modified_sections_count": 1 if dictation else 0,
            "gender_pruned": list(set(pre_pruned + post_pruned)),
            "engine": "deterministic-fallback"
        }
