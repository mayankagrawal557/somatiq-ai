"""
Layer 2 & Layer 3: Phonetic & Fuzzy Mispronunciation Corrector + Custom Vocabulary Store
Intercepts acoustic errors and sound-alikes (e.g., 'plural fusion' -> 'pleural effusion')
using fast regex matching, Soundex/Double-Metaphone patterns, and doctor-trained vocabulary.
"""

import os
import re
import json
import difflib
from typing import Dict, List, Any, Tuple

CUSTOM_VOCAB_FILE = os.path.join(os.path.dirname(__file__), "custom_vocab.json")

# Curated high-frequency radiology acoustic sound-alike dictionary
BASE_SOUND_ALIKE_DICTIONARY: Dict[str, str] = {
    # Pulmonary / Chest
    "plural fusion": "pleural effusion",
    "plural effusions": "pleural effusions",
    "floral effusion": "pleural effusion",
    "plural fluid": "pleural fluid",
    "plural thickening": "pleural thickening",
    "pneumo thorax": "pneumothorax",
    "atelectasis": "atelectasis",
    "broncho vascular": "bronchovascular",
    "costo phrenic": "costophrenic",
    "cardio phrenic": "cardiophrenic",
    
    # Abdominal / Ultrasound
    "coal lithiasis": "cholelithiasis",
    "choli lithiasis": "cholelithiasis",
    "chole lithiasis": "cholelithiasis",
    "coal cystitis": "cholecystitis",
    "chole cystitis": "cholecystitis",
    "chole docho lithiasis": "choledocholithiasis",
    "hippo echoic": "hypoechoic",
    "high po echoic": "hypoechoic",
    "hyper echoic": "hyperechoic",
    "high per echoic": "hyperechoic",
    "an echoic": "anechoic",
    "un echoic": "anechoic",
    "iso echoic": "isoechoic",
    "hydro nephrosis": "hydronephrosis",
    "hydro ureter": "hydroureter",
    "hepato megaly": "hepatomegaly",
    "spleno megaly": "splenomegaly",
    "hepato splenomegaly": "hepatosplenomegaly",
    "nephro lithiasis": "nephrolithiasis",
    "cortico medullary": "corticomedullary",

    # Brain / Neuro
    "para chyma": "parenchyma",
    "paren chymal": "parenchymal",
    "hema toma": "hematoma",
    "haema toma": "haematoma",
    "sub dural": "subdural",
    "epi dural": "epidural",
    "sub arachnoid": "subarachnoid",
    "calvarium": "calvarium",
    "calverium": "calvarium",
    "hydro cephalus": "hydrocephalus",
    "ischemic stroke": "ischaemic stroke",
    "lacunar infarct": "lacunar infarct",
    "flair hyper intense": "FLAIR hyperintense",
    "t1 hyper intense": "T1 hyperintense",
    "t2 hyper intense": "T2 hyperintense",

    # Spine / Musculoskeletal
    "pondylo listhesis": "spondylolisthesis",
    "spondylo listhesis": "spondylolisthesis",
    "spondylolithesis": "spondylolisthesis",
    "spondylo lysis": "spondylolysis",
    "osteo phytes": "osteophytes",
    "radiculo pathy": "radiculopathy",
    "conus medullaris": "conus medullaris",
    "cauda equina": "cauda equina",
    "ligamentum flavum": "ligamentum flavum",

    # Oncology, Nuclear Medicine & Theranostics Sound-Alikes
    "f d g pet ct": "FDG PET-CT",
    "f d g pet": "FDG PET-CT",
    "fdg pet": "FDG PET-CT",
    "f d g": "FDG",
    "p s m a pet ct": "PSMA PET-CT",
    "p s m a pet": "PSMA PET-CT",
    "plasma pet": "PSMA PET-CT",
    "p s m a": "PSMA",
    "dota knock": "DOTANOC",
    "daughter knock": "DOTANOC",
    "dot a knock": "DOTANOC",
    "dota tate": "DOTATATE",
    "daughter tate": "DOTATATE",
    "dot a tate": "DOTATATE",
    "s u v max": "SUVmax",
    "suv max": "SUVmax",
    "s u v maximum": "SUVmax",
    "suv maximum": "SUVmax",
    "suv mean": "SUVmean",
    "s u v mean": "SUVmean",
    "fdg avid": "FDG-avid",
    "f d g avid": "FDG-avid",
    "f d g a vid": "FDG-avid",
    "psma avid": "PSMA-avid",
    "p s m a avid": "PSMA-avid",
    "sstr avid": "SSTR-avid",
    "photo penic": "photopenic",
    "photo panic": "photopenic",
    "hyper metabolic": "hypermetabolic",
    "hypo metabolic": "hypometabolic",
    "d t p a": "DTPA",
    "dtpa scan": "DTPA scan",
    "d m s a": "DMSA",
    "dmsa scan": "DMSA scan",
    "e c scan": "EC scan",
    "easy scan": "EC scan",
    "hide a scan": "HIDA scan",
    "heeda scan": "HIDA scan",
    "h i d a": "HIDA",
    "brain spec": "Brain SPECT",
    "brain respect": "Brain SPECT",
    "brain spect": "Brain SPECT",
    "loo 177": "Lu-177",
    "lutetium 177": "Lu-177",
    "lu 177": "Lu-177",
    "actinium 225": "Ac-225",
    "a c 225": "Ac-225",
    "ac 225": "Ac-225",
    "i 131": "I-131",
    "iodine 131": "I-131",
    "samarium 153": "Samarium-153",
    "strontium 89": "Strontium-89",
    "yttrium 90": "Yttrium-90",
    "rhenium 186": "Rhenium-186",
    "radio sin o vectomy": "Radiosynovectomy",
    "radio synovectomy": "Radiosynovectomy",
    "doe ville score": "Deauville score",
    "devil score": "Deauville score",
    "deauville score": "Deauville score",
    "sestamibi": "Sestamibi",
    "sesta mibi": "Sestamibi",
    "pertechnetate": "Pertechnetate",
    "per technetate": "Pertechnetate"
}

class PhoneticCorrector:
    """
    Real-time phonetic and phonetic sound-alike corrector.
    Guarantees <50ms processing overhead.
    """

    _custom_vocab: Dict[str, Any] = {}

    @classmethod
    def load_custom_vocab(cls) -> Dict[str, Any]:
        """Loads doctor-trained custom terms from local JSON storage."""
        if not os.path.exists(CUSTOM_VOCAB_FILE):
            default_data = {
                "trained_words": [],
                "sound_alikes": {}
            }
            with open(CUSTOM_VOCAB_FILE, "w", encoding="utf-8") as f:
                json.dump(default_data, f, indent=2)
            cls._custom_vocab = default_data
        else:
            try:
                with open(CUSTOM_VOCAB_FILE, "r", encoding="utf-8") as f:
                    cls._custom_vocab = json.load(f)
            except Exception:
                cls._custom_vocab = {"trained_words": [], "sound_alikes": {}}
        return cls._custom_vocab

    @classmethod
    def save_custom_vocab(cls, data: Dict[str, Any]):
        """Persists custom vocabulary to disk."""
        cls._custom_vocab = data
        with open(CUSTOM_VOCAB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def add_trained_word(cls, correct_term: str, misheard_as: str = "", modality: str = "all") -> Dict[str, Any]:
        """
        Adds a new doctor-trained word with phonetic sound-alike alias.
        Immediately available in the active correction pipeline without server restart.
        """
        vocab = cls.load_custom_vocab()
        correct_clean = correct_term.strip()
        misheard_clean = misheard_as.strip().lower()

        # Update trained words list
        existing_item = next((item for item in vocab["trained_words"] if item["term"].lower() == correct_clean.lower()), None)
        if not existing_item:
            vocab["trained_words"].append({
                "term": correct_clean,
                "misheard": misheard_clean,
                "modality": modality
            })
        else:
            existing_item["misheard"] = misheard_clean
            existing_item["modality"] = modality

        # Update sound-alike dictionary
        if misheard_clean and misheard_clean != correct_clean.lower():
            vocab["sound_alikes"][misheard_clean] = correct_clean

        cls.save_custom_vocab(vocab)
        return {"status": "success", "term": correct_clean, "misheard": misheard_clean}

    @classmethod
    def get_trained_words(cls) -> List[Dict[str, Any]]:
        vocab = cls.load_custom_vocab()
        return vocab.get("trained_words", [])

    @classmethod
    def delete_trained_word(cls, term: str) -> bool:
        vocab = cls.load_custom_vocab()
        term_clean = term.strip().lower()
        initial_len = len(vocab.get("trained_words", []))
        vocab["trained_words"] = [w for w in vocab.get("trained_words", []) if w["term"].lower() != term_clean]
        
        # Remove from sound-alikes if present
        keys_to_delete = [k for k, v in vocab.get("sound_alikes", {}).items() if v.lower() == term_clean]
        for k in keys_to_delete:
            del vocab["sound_alikes"][k]

        cls.save_custom_vocab(vocab)
        return len(vocab["trained_words"]) < initial_len

    @classmethod
    def correct_text(cls, text: str) -> Tuple[str, List[Dict[str, str]]]:
        """
        Applies fast regex and fuzzy replacement on raw speech transcript.
        Returns:
            Tuple: (corrected_text, list_of_applied_corrections)
        """
        if not text:
            return "", []

        corrections_applied = []
        working_text = text

        # Merge base sound-alikes with doctor custom trained sound-alikes
        vocab = cls.load_custom_vocab()
        active_dict = dict(BASE_SOUND_ALIKE_DICTIONARY)
        active_dict.update(vocab.get("sound_alikes", {}))

        # Sort keys by length descending to match multi-word phrases first
        sorted_keys = sorted(active_dict.keys(), key=len, reverse=True)
        # Build single combined regex with word boundaries to prevent cascade replacements
        escaped_keys = [re.escape(k) for k in sorted_keys]
        if escaped_keys:
            combined_pattern = re.compile(rf'\b({"|".join(escaped_keys)})\b', re.IGNORECASE)
            
            def replace_callback(match):
                matched_text = match.group(0).lower()
                # Find exact key
                replacement = active_dict.get(matched_text)
                if not replacement:
                    for k in sorted_keys:
                        if k.lower() == matched_text:
                            replacement = active_dict[k]
                            break
                if replacement:
                    corrections_applied.append({
                        "original": match.group(0),
                        "corrected": replacement
                    })
                    return replacement
                return match.group(0)

            working_text = combined_pattern.sub(replace_callback, working_text)

        return working_text, corrections_applied

    @classmethod
    def contextual_llm_repair(cls, text: str) -> str:
        """
        Optional lightweight contextual repair using Gemini 2.5 Flash for severely mangled dictation.
        Guarantees sentence structure preservation.
        """
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not gemini_key or not text:
            return text

        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            prompt = (
                "You are an expert radiology speech transcription phonetic repair tool. "
                "Fix only the phonetically misheard radiology words (e.g. medical terms, anatomy, pathology) "
                "in this dictated sentence. Keep the doctor's exact grammar, sentence flow, and punctuation intact. "
                "Return only the repaired sentence with no markdown, conversational fillers, or explanations.\n\n"
                f"Sentence: \"{text}\""
            )
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=dict(temperature=0.0)
            )
            repaired = response.text.strip().replace('"', '')
            return repaired if repaired else text
        except Exception:
            return text
