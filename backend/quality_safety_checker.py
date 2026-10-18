"""
Quality & Safety Checker for Radiology & Nuclear Medicine Voice Dictation
Implements safety boundaries from the Nuclear Medicine Terminology Handbook:
1. High-Risk Confusables (F-18 vs I-131, Ga-68 vs Lu-177, DOTATATE vs DOTATOC, PSMA vs SSTR, PET vs SPECT, CT vs MRI)
2. Laterality Verification (Right, Left, Bilateral, Unclear laterality - never silently choose)
3. Negation & Polarity Guard (No evidence of vs evidence of, positive vs negative, increased vs decreased)
4. Measurements & Decimal Quality Check (Lesion sizes, SUVmax vs SUVmean, split renal function sums)
5. Activity Units & Dosimetry (MBq vs GBq differing by factor 1,000, administered activity vs absorbed dose Gy)
6. Immutable Raw Transcript preservation and audit trail
"""

import re
import json
import os
from typing import Dict, List, Any, Optional

HANDBOOK_VOCAB_PATH = os.path.join(os.path.dirname(__file__), "data", "nuclear_medicine_handbook_vocab.json")

# High-Risk Confusable Pairs and Clinical Rules from Handbook Section 7
HIGH_RISK_PAIRS = [
    {
        "pair": "F-18 vs I-131",
        "patterns": [r'\b(?:f-?18|18-?f|fluorine-?18)\b', r'\b(?:i-?131|131-?i|iodine-?131|radioiodine)\b'],
        "warning": "Radionuclide Confusable: F-18 (Diagnostic PET) and I-131 (Thyroid Theranostic) have distinct clinical purposes. Preserve exact isotope and verify with clinician."
    },
    {
        "pair": "Ga-68 vs Lu-177",
        "patterns": [r'\b(?:ga-?68|68-?ga|gallium-?68)\b', r'\b(?:lu-?177|177-?lu|lutetium-?177)\b'],
        "warning": "Radionuclide Confusable: Ga-68 (Diagnostic) and Lu-177 (Therapeutic) have different roles. Never auto-correct one to the other."
    },
    {
        "pair": "DOTATATE vs DOTATOC",
        "patterns": [r'\bdotatate\b', r'\bdotatoc\b'],
        "warning": "Tracer Confusable: DOTATATE and DOTATOC are distinct somatostatin analogs. Do not treat as synonyms."
    },
    {
        "pair": "PSMA vs SSTR",
        "patterns": [r'\bpsma\b', r'\bsstr\b'],
        "warning": "Target Receptor Confusable: PSMA and SSTR are distinct biological targets. Retain exact target."
    },
    {
        "pair": "PET vs SPECT",
        "patterns": [r'\bpet\b|\bpet/ct\b', r'\bspect\b|\bspect/ct\b'],
        "warning": "Modality Confusable: PET and SPECT use different physics and tracers. Never substitute one for the other."
    },
    {
        "pair": "CT vs MRI",
        "patterns": [r'\bct\b|\bhrct\b', r'\bmri\b'],
        "warning": "Modality Confusable: Preserve dictated modality (CT vs MRI)."
    },
    {
        "pair": "SUVmax vs SUVmean",
        "patterns": [r'\bsuvmax\b|\bsuv\s*max\b', r'\bsuvmean\b|\bsuv\s*mean\b'],
        "warning": "Metric Confusable: SUVmax (voxel peak) and SUVmean (ROI average) are distinct metrics. Preserve reported metric."
    },
    {
        "pair": "Lymph node vs lung nodule",
        "patterns": [r'\blymph\s*node\b', r'\blung\s*nodule\b'],
        "warning": "Anatomical Structure Confusable: Verify whether lymphatic node or pulmonary lung nodule was dictated."
    }
]

class ClinicalQualityChecker:
    """
    Scans transcripts and structured reports for clinical risk factors,
    flags uncertainty, verifies arithmetic (e.g. split renal function),
    and enforces handbook safety boundaries.
    """

    @classmethod
    def analyze_transcript(cls, raw_text: str, template_id: str = "") -> Dict[str, Any]:
        """
        Analyzes speech transcript and flags:
        - uncertain_terms (with category, suggestion, severity)
        - laterality checks
        - negation terms
        - measurements & renal sum checks
        - activity units (MBq vs GBq, Gy)
        - confusable alerts
        """
        if not raw_text:
            return {
                "uncertain_terms": [],
                "quality_flags": [],
                "has_warnings": False,
                "human_review_required": False,
                "split_function_check": None
            }

        uncertain_terms: List[Dict[str, Any]] = []
        quality_flags: List[Dict[str, Any]] = []
        text_lower = raw_text.lower()

        # 1. High-Risk Confusable Checks
        for item in HIGH_RISK_PAIRS:
            found_matches = []
            for pat in item["patterns"]:
                match = re.search(pat, text_lower, re.IGNORECASE)
                if match:
                    found_matches.append(match.group(0))
            if found_matches:
                flag = {
                    "type": "CONFUSABLE_ALERT",
                    "pair": item["pair"],
                    "matched": found_matches,
                    "severity": "WARNING",
                    "guidance": item["warning"]
                }
                quality_flags.append(flag)
                uncertain_terms.append({
                    "term": ", ".join(found_matches),
                    "category": "High-Risk Confusable",
                    "severity": "WARNING",
                    "guidance": item["warning"]
                })

        # 2. Laterality Checks (Right, Left, Bilateral, Unclear laterality)
        has_right = bool(re.search(r'\bright\b', text_lower))
        has_left = bool(re.search(r'\bleft\b', text_lower))
        has_bilateral = bool(re.search(r'\bbilateral\b', text_lower))
        has_unclear_laterality = bool(re.search(r'\b(?:laterality is unclear|unclear laterality|left or right|right or left)\b', text_lower))

        if has_unclear_laterality:
            uncertain_terms.append({
                "term": "unclear laterality",
                "category": "Laterality Uncertainty",
                "severity": "CRITICAL_ALERT",
                "guidance": "Laterality is explicitly marked as unclear. Clinician must confirm side; never silently choose left or right."
            })
            quality_flags.append({
                "type": "LATERALITY_UNCERTAIN",
                "severity": "CRITICAL_ALERT",
                "message": "Critical Laterality Uncertainty: Clinician must explicitly verify side before final sign-off."
            })
        elif has_right or has_left or has_bilateral:
            lat_types = []
            if has_right: lat_types.append("Right")
            if has_left: lat_types.append("Left")
            if has_bilateral: lat_types.append("Bilateral")
            quality_flags.append({
                "type": "LATERALITY_CONFIRMED",
                "severity": "INFO",
                "message": f"Laterality detected: {', '.join(lat_types)}. Verify anatomical alignment."
            })

        # 3. Negation & Polarity Guard
        negation_patterns = [
            (r'\bno\s+evidence\s+of\b', "no evidence of", "Negative finding phrase preserved. Must not invert."),
            (r'\bno\s+(?:acute|focal|abnormal|significant|metastatic)\b', "no acute/abnormal", "Negative finding phrase preserved."),
            (r'\bwithout\b', "without", "Exclusionary qualifier preserved."),
            (r'\bnegative\s+for\b|\bnegative\b', "negative", "Polarity term: verify clinical direction."),
            (r'\bpositive\s+for\b|\bpositive\b', "positive", "Polarity term: verify clinical direction."),
            (r'\b(?:increased|hypermetabolic|increased uptake)\b', "increased uptake", "Comparative activity term: verify vs baseline."),
            (r'\b(?:decreased|hypometabolic|reduced uptake)\b', "decreased uptake", "Comparative activity term: verify vs baseline."),
            (r'\b(?:mild|mildly|moderate|moderately|intense|intensely)\b', "degree qualifier", "Degree term: should never be changed by automated rewriting.")
        ]
        for pat, label, guide in negation_patterns:
            matches = list(re.finditer(pat, text_lower))
            if matches:
                matched_phrases = [m.group(0) for m in matches[:2]]
                quality_flags.append({
                    "type": "NEGATION_POLARITY_GUARD",
                    "severity": "NOTICE",
                    "term": label,
                    "matched": matched_phrases,
                    "guidance": guide
                })

        # 4. Activity Units & Dosimetry Guard (MBq vs GBq, Gy)
        unit_matches = []
        if re.search(r'\bgbq\b|\bgigabecquerel\b', text_lower):
            unit_matches.append("GBq (10^9 Bq)")
        if re.search(r'\bmbq\b|\bmegabecquerel\b', text_lower):
            unit_matches.append("MBq (10^6 Bq)")
        if re.search(r'\bmci\b|\bmillicurie\b', text_lower):
            unit_matches.append("mCi")
        if re.search(r'\bgy\b|\bgray\b', text_lower):
            unit_matches.append("Gy (Absorbed dose)")

        if unit_matches:
            quality_flags.append({
                "type": "ACTIVITY_UNIT_CHECK",
                "severity": "NOTICE",
                "units_detected": unit_matches,
                "guidance": "Units differ by orders of magnitude (1 GBq = 1,000 MBq). Administered activity is not absorbed dose (Gy). Do not convert without explicit verification."
            })

        # 5. Arithmetic & Quality Verification on Measurements
        # A. Split Renal Function verification
        # e.g., "right forty-eight percent and left fifty-two percent" or "right 48% and left 52%"
        split_check = cls._check_renal_split(raw_text)
        if split_check:
            quality_flags.append({
                "type": "RENAL_SPLIT_CHECK",
                "severity": "INFO" if split_check["is_balanced"] else "WARNING",
                "details": split_check
            })

        # B. Lesion measurements and SUV decimals
        measurements = re.findall(r'\b\d+(?:\.\d+)?\s*(?:cm|mm|suvmax|suv|%)\b', text_lower)
        if measurements:
            quality_flags.append({
                "type": "MEASUREMENTS_PRESERVED",
                "severity": "INFO",
                "count": len(measurements),
                "values": measurements[:5]
            })

        has_critical = any(q.get("severity") in ["CRITICAL_ALERT", "WARNING"] for q in quality_flags)

        return {
            "uncertain_terms": uncertain_terms,
            "quality_flags": quality_flags,
            "has_warnings": has_critical,
            "human_review_required": has_critical,
            "split_function_check": split_check
        }

    @classmethod
    def _check_renal_split(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Parses dictated right and left split percentages and verifies sum ≈ 100%.
        Does not alter the dictated values (Page 12 Example C).
        """
        # Search for right and left percentages (digit or words)
        words_to_num = {
            "forty-eight": 48, "forty eight": 48, "fifty-two": 52, "fifty two": 52,
            "fifty": 50, "forty five": 45, "fifty five": 55, "forty": 40, "sixty": 60,
            "thirty": 30, "seventy": 70
        }
        text_norm = text.lower()
        for k, v in words_to_num.items():
            text_norm = text_norm.replace(k, str(v))

        right_match = re.search(r'right\s*(?:is)?\s*(\d+)\s*(?:percent|%)', text_norm)
        left_match = re.search(r'left\s*(?:is)?\s*(\d+)\s*(?:percent|%)', text_norm)

        if right_match and left_match:
            try:
                r_val = float(right_match.group(1))
                l_val = float(left_match.group(1))
                total = r_val + l_val
                is_balanced = (99.0 <= total <= 101.0)
                return {
                    "right_pct": r_val,
                    "left_pct": l_val,
                    "total_sum": total,
                    "is_balanced": is_balanced,
                    "message": f"Differential renal function: Right={r_val}%, Left={l_val}% (Sum: {total}%). " +
                               ("Sum validates to 100%." if is_balanced else "Quality Check Notice: Sum deviates from 100%. Clinician verification recommended.")
                }
            except Exception:
                return None
        return None

    @classmethod
    def build_audit_structure(
        cls,
        original_transcript: str,
        normalized_transcript: str,
        template_id: str,
        repairs: List[Dict[str, Any]],
        sections: Dict[str, str],
        reviewer: str = "Unassigned",
        status: str = "DRAFT"
    ) -> Dict[str, Any]:
        """
        Constructs the standard Nuclear Medicine Handbook data structure (Page 12 Section 9).
        """
        safety = cls.analyze_transcript(original_transcript, template_id)

        # Standard core sections mapping
        report_sections = {
            "clinical_indication": sections.get("indication", ""),
            "procedure_technique": sections.get("technique", ""),
            "findings": sections.get("findings", ""),
            "impression": sections.get("impression", ""),
            "limitations_additional_notes": sections.get("comparison", "") or "No technical motion artefact described."
        }

        return {
            "original_transcript": original_transcript,
            "normalized_transcript": normalized_transcript,
            "uncertain_terms": safety["uncertain_terms"],
            "quality_flags": safety["quality_flags"],
            "exam_metadata": {
                "template_id": template_id,
                "examination": sections.get("examination", ""),
                "study_date": None
            },
            "report_sections": report_sections,
            "provenance": {
                "dictated": bool(original_transcript.strip()),
                "repairs_count": len(repairs),
                "ai_assisted": True,
                "engine": "Somatiq Zero-Training Safety Engine"
            },
            "human_approval": {
                "reviewer": reviewer,
                "status": status,
                "requires_review": safety["human_review_required"],
                "approved": status in ["APPROVED", "FINAL"]
            }
        }
