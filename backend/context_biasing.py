"""
Method 1: Dynamic Contextual Decoder Biasing
Provides modality-specific initial_prompts (in natural clinical prose to avoid list-style Whisper hallucinations),
hotwords / phrase hints, and Whisper anti-hallucination configuration.
Directly incorporates domain terms from the Nuclear Medicine Terminology Handbook.
"""

from typing import Dict, List, Any

# Modality Categories & Profile Definitions from Handbook
MODALITY_PROFILES: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # Category A: PET-CT Scans
    # -------------------------------------------------------------------------
    "petct": {
        "category": "PET-CT Scans",
        "title": "PET-CT Examination",
        "initial_prompt": (
            "Clinical PET-CT Report: Whole Body 18F-FDG PET-CT from skull base to mid thighs, "
            "68Ga-PSMA and 18F-PSMA PET-CT, 68Ga-DOTATATE and DOTATOC PET-CT, Amyloid PET, "
            "and Brain FDG PET. Findings demonstrate hypermetabolic FDG-avid and PSMA-avid lesions with "
            "SUVmax 8.4, SUVmean, Deauville score 3, PERCIST response, physiological biodistribution in myocardium, "
            "brown fat, muscle uptake, and urinary excretion. Metabolic tumour volume MTV and TLG."
        ),
        "hotwords": [
            "FDG PET-CT", "18F-FDG", "PSMA PET-CT", "68Ga-PSMA", "18F-PSMA",
            "DOTANOC", "DOTATATE", "DOTATOC", "68Ga-DOTATATE", "Amyloid PET", "Brain FDG PET",
            "SUVmax", "SUVmean", "FDG-avid", "PSMA-avid", "SSTR-avid",
            "Deauville score", "PERCIST", "hypermetabolic", "hypometabolic",
            "physiological uptake", "brown fat", "muscle uptake", "urinary excretion",
            "liver background", "mediastinal blood pool", "MTV", "TLG",
            "skull base to mid thighs"
        ]
    },

    # -------------------------------------------------------------------------
    # Category B: Gamma Camera Scans (SPECT / Scintigraphy)
    # -------------------------------------------------------------------------
    "spect": {
        "category": "Gamma Camera Scans (SPECT / Scintigraphy)",
        "title": "Gamma Camera Scintigraphy / SPECT",
        "initial_prompt": (
            "Gamma Camera Scintigraphy Report: Whole Body 99mTc-MDP Bone Scan, HDP, "
            "Renal Scans DTPA, EC, DMSA, and MAG3 renogram, Thyroid and Parathyroid Sestamibi Scan, "
            "Pertechnetate, Myocardial Perfusion Imaging MPI stress and rest, Gated SPECT ejection fraction EF, "
            "Lung Perfusion V/Q Scan, HIDA Hepatobiliary Scan, Gastric Emptying Study, and Brain SPECT. "
            "Differential renal function percentages, photopenic defect, osteoblastic uptake, and drainage washout."
        ),
        "hotwords": [
            "Bone Scan", "99mTc-MDP", "HDP", "HMDP", "DTPA", "DMSA", "MAG3",
            "EC Scan", "HIDA Scan", "Brain SPECT", "Sestamibi", "Pertechnetate",
            "differential renal function", "split renal function", "renogram", "ejection fraction",
            "Gated SPECT", "MPI", "stress imaging", "rest imaging", "V/Q scan",
            "perfusion defect", "ventilation defect", "sentinel lymph node", "photopenic defect",
            "drainage washout", "collimator", "extravasation"
        ]
    },

    # -------------------------------------------------------------------------
    # Category C: Therapeutic Nuclear Medicine (Theranostics)
    # -------------------------------------------------------------------------
    "theranostics": {
        "category": "Therapeutic Nuclear Medicine (Theranostics)",
        "title": "Targeted Radionuclide Therapy",
        "initial_prompt": (
            "Therapeutic Nuclear Medicine Report: Radioiodine Therapy I-131, "
            "Lu-177 PSMA Therapy, 177Lu-PSMA, Lu-177 DOTATATE PRRT Therapy, 177Lu-DOTATATE, "
            "Ac-225 PSMA Targeted Alpha Therapy, Y-90 Radioembolization, Ra-223, Sr-89, "
            "and Sm-153 Bone Pain Palliation Therapy, and Radiosynovectomy. Administered activity "
            "in MBq and GBq, absorbed dose in Gy, radiation precautions, post-therapy imaging, "
            "dosimetry, and xerostomia."
        ),
        "hotwords": [
            "Radioiodine Therapy", "I-131", "Lu-177", "177Lu-PSMA", "177Lu-DOTATATE",
            "PRRT", "Ac-225 PSMA", "Actinium-225", "Y-90", "Radioembolization",
            "Ra-223", "Sr-89", "Sm-153", "Radiosynovectomy", "Bone Pain Palliation",
            "administered activity", "absorbed dose", "MBq", "GBq", "Gy",
            "half-life", "radiation precautions", "treatment cycle", "post-therapy imaging",
            "dosimetry", "xerostomia", "myelosuppression", "salivary gland toxicity"
        ]
    },

    # -------------------------------------------------------------------------
    # Category D: Standard Diagnostic Radiology
    # -------------------------------------------------------------------------
    "radiology": {
        "category": "Standard Diagnostic Radiology",
        "title": "Diagnostic Radiology (CT/MRI/USG/X-Ray)",
        "initial_prompt": (
            "Diagnostic Radiology Report: Ultrasound Whole Abdomen, Non-contrast and Contrast CT, "
            "MRI T1 T2 FLAIR sequences. Hepatomegaly, cholelithiasis, hydronephrosis, "
            "pleural effusion, parenchyma, spondylolisthesis, osteophytes, and lymphadenopathy."
        ),
        "hotwords": [
            "hepatomegaly", "cholelithiasis", "hydronephrosis", "pleural effusion",
            "parenchyma", "spondylolisthesis", "hypoechoic", "hyperechoic",
            "FLAIR", "lymphadenopathy", "calculus", "atelectasis", "consolidation",
            "mass effect", "midline shift", "intracranial haemorrhage"
        ]
    }
}

# Template-to-Category Mapping
TEMPLATE_CATEGORY_MAP: Dict[str, str] = {
    # PET-CT
    "petct_fdg_whole_body": "petct",
    "petct_psma": "petct",
    "petct_dotanoc": "petct",
    "petct_brain": "petct",
    "petct_cardiac": "petct",
    "petct_whole_body": "petct",

    # Gamma Camera / SPECT
    "spect_bone_scan": "spect",
    "spect_renal_dtpa": "spect",
    "spect_renal_dmsa": "spect",
    "spect_thyroid": "spect",
    "spect_cardiac_perfusion": "spect",
    "spect_lung_vq": "spect",
    "spect_hida": "spect",
    "spect_brain": "spect",

    # Theranostics
    "thera_radioiodine_i131": "theranostics",
    "thera_lu177_psma": "theranostics",
    "thera_lu177_dotatate": "theranostics",
    "thera_ac225_psma": "theranostics",
    "thera_bone_pain_palliation": "theranostics",
    "thera_radiosynovectomy": "theranostics",

    # Radiology
    "ct_brain": "radiology",
    "ct_chest": "radiology",
    "mri_brain": "radiology",
    "mri_lumbar_spine": "radiology",
    "chest_xray": "radiology",
    "usg_abdomen": "radiology"
}

# Whisper Anti-Hallucination Parameters
WHISPER_ANTI_HALLUCINATION_CONFIG = {
    "condition_on_previous_text": False,  # Prevents infinite looping during dictation pauses
    "no_speech_threshold": 0.6,
    "log_prob_threshold": -1.0,
    "compression_ratio_threshold": 2.2,
    "temperature": 0.0,
    "beam_size": 5
}

class ContextBiasingEngine:
    """
    Method 1 Engine: Manages dynamic context-biasing profiles, initial prompts,
    and phrase hints injection for speech-recognition engines.
    """

    @classmethod
    def get_category_key(cls, template_id: str) -> str:
        return TEMPLATE_CATEGORY_MAP.get(template_id, "radiology")

    @classmethod
    def get_profile(cls, template_id: str) -> Dict[str, Any]:
        cat_key = cls.get_category_key(template_id)
        return MODALITY_PROFILES.get(cat_key, MODALITY_PROFILES["radiology"])

    @classmethod
    def get_initial_prompt(cls, template_id: str, custom_terms: List[str] = None) -> str:
        profile = cls.get_profile(template_id)
        prompt = profile["initial_prompt"]
        if custom_terms:
            prompt += f" Doctor-trained custom terms: {', '.join(custom_terms[:10])}."
        return prompt

    @classmethod
    def get_hotwords_string(cls, template_id: str, custom_terms: List[str] = None) -> str:
        profile = cls.get_profile(template_id)
        words = list(profile["hotwords"])
        if custom_terms:
            for t in custom_terms:
                if t not in words:
                    words.append(t)
        return ", ".join(words)

    @classmethod
    def get_anti_hallucination_config(cls) -> Dict[str, Any]:
        return dict(WHISPER_ANTI_HALLUCINATION_CONFIG)
