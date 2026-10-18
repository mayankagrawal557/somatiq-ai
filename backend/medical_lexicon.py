"""
Layer 1: Whisper Context-Biasing & Modality-Specific Lexicons
Generates targeted initial_prompts and hotwords dynamically based on the active scan modality.
"""

from typing import Dict, List, Any

# Modality-specific lexicons tailored for radiology acoustic decoding
MODALITY_LEXICONS: Dict[str, Dict[str, Any]] = {
    "usg_abdomen": {
        "title": "Ultrasound Whole Abdomen & Pelvis",
        "hotwords": [
            "Hepatomegaly", "Splenomegaly", "Cholelithiasis", "Cholecystitis",
            "Hydronephrosis", "Hydroureteronephrosis", "Hypoechoic", "Hyperechoic",
            "Isoechoic", "Anechoic", "Acoustic shadowing", "Parenchyma",
            "Hemangioma", "Choledocholithiasis", "Intrahepatic biliary radicles",
            "Portal vein", "Calculus", "Nephrolithiasis", "Ascites", "Corticomedullary",
            "Pancreatitis", "Mesenteric lymphadenopathy", "Urinary bladder"
        ],
        "initial_prompt": (
            "Ultrasound abdomen dictation with acoustic terms: hepatomegaly, cholelithiasis, "
            "hypoechoic, hyperechoic, acoustic shadowing, parenchyma, hemangioma, calculus, "
            "hydronephrosis, corticomedullary differentiation, intrahepatic biliary radicles, ascites."
        )
    },
    "ct_brain": {
        "title": "CT Brain Plain / Non-Contrast",
        "hotwords": [
            "Intracranial haemorrhage", "Subdural hematoma", "Epidural hematoma",
            "Subarachnoid hemorrhage", "Midline shift", "Mass effect", "Calvarium",
            "Parenchyma", "Grey-white matter differentiation", "Basal cisterns",
            "Ventricles", "Hydrocephalus", "Sulcal effacement", "Cerebral edema",
            "Territorial infarction", "Lacunar infarct", "Ischemic stroke", "Hyperdense"
        ],
        "initial_prompt": (
            "CT brain plain non-contrast report: acute intracranial haemorrhage, subdural, "
            "epidural hematoma, subarachnoid, mass effect, midline shift, parenchyma, "
            "ventricular system, basal cisterns, calvarium, territorial infarction."
        )
    },
    "ct_chest": {
        "title": "CT Chest / HRCT Thorax",
        "hotwords": [
            "Ground-glass opacities", "Consolidation", "Pleural effusion",
            "Pneumothorax", "Atelectasis", "Bronchiectasis", "Emphysema",
            "Mediastinum", "Hilar lymphadenopathy", "Interlobular septal thickening",
            "Tree-in-bud nodularity", "Apical fibrobullous", "Costophrenic angle",
            "Pericardial effusion", "Tracheobronchial tree"
        ],
        "initial_prompt": (
            "HRCT Thorax and CT chest report: ground-glass opacities, consolidation, "
            "pleural effusion, pneumothorax, atelectasis, bronchiectasis, mediastinum, "
            "hilar lymphadenopathy, tracheobronchial tree, costophrenic angle."
        )
    },
    "mri_brain": {
        "title": "MRI Brain Multi-sequence",
        "hotwords": [
            "T1 hyperintense", "T2 hyperintense", "FLAIR hyperintense",
            "Restricted diffusion", "DWI", "ADC map", "Vasogenic edema",
            "Cytotoxic edema", "Major flow voids", "Craniocervical junction",
            "Meningeal enhancement", "Parenchyma", "Cerebellopontine angle", "Gliosis"
        ],
        "initial_prompt": (
            "MRI brain dictation: T1, T2, FLAIR hyperintense, restricted diffusion, "
            "DWI, ADC map, vasogenic edema, parenchymal mass, flow voids, gliosis."
        )
    },
    "mri_lumbar_spine": {
        "title": "MRI Lumbar Spine",
        "hotwords": [
            "Spondylolisthesis", "Spondylolysis", "Osteophytes", "Radiculopathy",
            "Disc bulge", "Disc protrusion", "Disc extrusion", "Thecal sac compression",
            "Neural foraminal stenosis", "Conus medullaris", "Cauda equina",
            "Ligamentum flavum hypertrophy", "Facet arthropathy", "Modic changes"
        ],
        "initial_prompt": (
            "MRI lumbar spine report: spondylolisthesis, osteophytes, disc protrusion, "
            "extrusion, thecal sac impingement, neural foraminal stenosis, conus medullaris, "
            "cauda equina, ligamentum flavum hypertrophy, facet arthropathy."
        )
    },
    "chest_xray": {
        "title": "Chest X-Ray PA View",
        "hotwords": [
            "Cardiomegaly", "Cardiothoracic ratio", "Costophrenic angles",
            "Cardiophrenic angles", "Bronchovascular markings", "Pleural effusion",
            "Pneumothorax", "Consolidation", "Infiltrate", "Hilar fullness",
            "Hemidiaphragm", "Bony thorax"
        ],
        "initial_prompt": (
            "Chest X-ray radiograph PA view: cardiomegaly, cardiothoracic ratio, "
            "costophrenic angles, bronchovascular markings, consolidation, pneumothorax, "
            "pleural effusion, hemidiaphragm."
        )
    },
    "petct_whole_body": {
        "title": "18F-FDG Whole Body PET-CT",
        "hotwords": [
            "18F-FDG", "SUVmax", "Hypermetabolic", "Hypometabolic", "Fluorodeoxyglucose",
            "Lymphadenopathy", "Metastatic", "Physiological uptake", "Spiculated mass",
            "Attenuation correction", "Vertex to mid-thigh", "Metabolic activity"
        ],
        "initial_prompt": (
            "18F-FDG whole body PET-CT scan: fluorodeoxyglucose, SUVmax, hypermetabolic, "
            "lymphadenopathy, distant metastases, physiological uptake, staging report."
        )
    }
}

class MedicalLexiconManager:
    """
    Manages active clinical lexicons, dynamic initial prompts, and hotwords.
    """

    @classmethod
    def get_lexicon_for_template(cls, template_id: str) -> Dict[str, Any]:
        """Returns the specific lexicon and initial prompt for a modality."""
        from backend.nuclear_med_vocab import NUCLEAR_INITIAL_PROMPT, NUCLEAR_MED_HOTWORDS, NUCLEAR_MED_TEMPLATES

        if template_id in MODALITY_LEXICONS:
            return MODALITY_LEXICONS[template_id]
        elif template_id in NUCLEAR_MED_TEMPLATES:
            t = NUCLEAR_MED_TEMPLATES[template_id]
            return {
                "title": t["title"],
                "hotwords": NUCLEAR_MED_HOTWORDS,
                "initial_prompt": f"{t['title']}: {NUCLEAR_INITIAL_PROMPT}"
            }
        return MODALITY_LEXICONS.get("ct_brain")

    @classmethod
    def get_combined_hotwords(cls, template_id: str, custom_words: List[str] = None) -> List[str]:
        """Combines modality hotwords with doctor-trained custom terms."""
        lex = cls.get_lexicon_for_template(template_id)
        words = list(lex["hotwords"])
        if custom_words:
            for w in custom_words:
                if w not in words:
                    words.append(w)
        return words

    @classmethod
    def get_active_prompt(cls, template_id: str, custom_words: List[str] = None) -> str:
        """Constructs an acoustic decoder initial prompt biased towards the current study."""
        lex = cls.get_lexicon_for_template(template_id)
        prompt = lex["initial_prompt"]
        if custom_words:
            prompt += " Custom terms: " + ", ".join(custom_words[:15]) + "."
        return prompt
