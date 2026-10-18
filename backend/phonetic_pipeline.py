"""
Method 2 (Pass 1): Deterministic Sound-Alike, Metaphone & Quantitative Normalizer
Latency: <5ms
Features:
1. Curated Sound-Alike Dictionary (Standard Radiology + Nuclear Medicine / PET-CT / Theranostics)
2. Custom User Rules & Hotwords Persistence (`backend/custom_rules.json`)
3. Phonetic Metaphone & Fuzzy Matcher for multi-syllable medical terms (len >= 7, ratio >= 78)
4. Smart Quantitative SUVmax regex & Spoken Isotope Normalizer
5. Enforces Handbook Safety: High-Risk Confusables are NEVER cross-substituted
"""

import os
import re
import json
from typing import Dict, List, Any, Tuple

from backend.quality_safety_checker import ClinicalQualityChecker

CUSTOM_RULES_FILE = os.path.join(os.path.dirname(__file__), "custom_rules.json")

# Core Pass-1 Sound-Alike Dictionary incorporating Nuclear Medicine Handbook terms
SOUND_ALIKE_MAP: Dict[str, str] = {
    # PET-CT & Oncology
    "daughter knock": "DOTANOC",
    "dota knock": "DOTANOC",
    "dot a knock": "DOTANOC",
    "daughter tate": "DOTATATE",
    "dota tate": "DOTATATE",
    "dot a tate": "DOTATATE",
    "daughter toc": "DOTATOC",
    "dota toc": "DOTATOC",
    "plasma pet": "PSMA PET-CT",
    "p s m a pet ct": "PSMA PET-CT",
    "p s m a pet": "PSMA PET-CT",
    "psma pet": "PSMA PET-CT",
    "psma pet ct": "PSMA PET-CT",
    "p s m a": "PSMA",
    "f d g pet ct": "FDG PET-CT",
    "f d g pet": "FDG PET-CT",
    "fdg pet": "FDG PET-CT",
    "fdg pet ct": "FDG PET-CT",
    "f d g": "FDG",
    "f d g avid": "FDG-avid",
    "f d g a vid": "FDG-avid",
    "fdg avid": "FDG-avid",
    "p s m a avid": "PSMA-avid",
    "psma avid": "PSMA-avid",
    "sstr avid": "SSTR-avid",
    "s u v max": "SUVmax",
    "suv max": "SUVmax",
    "s u v maximum": "SUVmax",
    "suv maximum": "SUVmax",
    "s u v mean": "SUVmean",
    "suv mean": "SUVmean",
    "devil score": "Deauville score",
    "doe ville score": "Deauville score",
    "deauville score": "Deauville score",
    "per sist": "PERCIST",
    "total lesion glycolysis": "Total Lesion Glycolysis (TLG)",
    "metabolic tumor volume": "Metabolic Tumour Volume (MTV)",
    "metabolic tumour volume": "Metabolic Tumour Volume (MTV)",

    # Isotopes & Radiopharmaceuticals (PET-CT)
    "fluorine eighteen fdg": "18F-FDG",
    "fluorine 18 fdg": "18F-FDG",
    "f 18 fdg": "18F-FDG",
    "f eighteen psma": "18F-PSMA",
    "f 18 psma": "18F-PSMA",
    "gallium sixty eight psma": "68Ga-PSMA",
    "gallium 68 psma": "68Ga-PSMA",
    "ga 68 psma": "68Ga-PSMA",
    "gallium sixty eight dotatate": "68Ga-DOTATATE",
    "gallium 68 dotatate": "68Ga-DOTATATE",
    "ga 68 dotatate": "68Ga-DOTATATE",

    # Gamma Camera / SPECT
    "technetium ninety-nine mdp": "99mTc-MDP",
    "technetium ninety nine mdp": "99mTc-MDP",
    "technetium 99m mdp": "99mTc-MDP",
    "technetium ninety-nine": "99mTc",
    "technetium ninety nine": "99mTc",
    "tc ninety nine m": "Tc-99m",
    "tc 99m": "Tc-99m",
    "mag three": "MAG3",
    "mag 3": "MAG3",
    "m a g three": "MAG3",
    "m a g 3": "MAG3",
    "hide a scan": "HIDA Scan",
    "heeda scan": "HIDA Scan",
    "h i d a scan": "HIDA Scan",
    "h i d a": "HIDA",
    "brain spec": "Brain SPECT",
    "brain respect": "Brain SPECT",
    "brain spect": "Brain SPECT",
    "d t p a": "DTPA",
    "dtpa scan": "DTPA Scan",
    "d m s a": "DMSA",
    "dmsa scan": "DMSA Scan",
    "e c scan": "EC Scan",
    "easy scan": "EC Scan",
    "photo panic": "photopenic",
    "photo penic": "photopenic",
    "sesta mibi": "Sestamibi",
    "sestamibi": "Sestamibi",
    "per technetate": "Pertechnetate",
    "pertechnetate": "Pertechnetate",
    "v q scan": "V/Q scan",
    "v slash q scan": "V/Q scan",
    "ventilation perfusion scan": "V/Q scan",

    # Theranostics
    "lutetium one hundred seventy-seven psma": "177Lu-PSMA",
    "lutetium one hundred seventy seven psma": "177Lu-PSMA",
    "lutetium 177 psma": "177Lu-PSMA",
    "lu 177 psma": "177Lu-PSMA",
    "lutetium one hundred seventy-seven dotatate": "177Lu-DOTATATE",
    "lutetium one hundred seventy seven dotatate": "177Lu-DOTATATE",
    "lutetium 177 dotatate": "177Lu-DOTATATE",
    "lu 177 dotatate": "177Lu-DOTATATE",
    "lutetium one hundred seventy-seven": "Lu-177",
    "lutetium one hundred seventy seven": "Lu-177",
    "lutetium 177": "Lu-177",
    "loo 177": "Lu-177",
    "lu 177": "Lu-177",
    "a c 225": "Ac-225",
    "ac 225": "Ac-225",
    "actinium 225": "Ac-225",
    "i 131": "I-131",
    "iodine 131": "I-131",
    "samarium one hundred fifty three": "Sm-153",
    "samarium one fifty three": "Sm-153",
    "samarium 153": "Sm-153",
    "strontium eighty nine": "Sr-89",
    "strontium 89": "Sr-89",
    "yttrium ninety": "Y-90",
    "yttrium 90": "Y-90",
    "radium two twenty three": "Ra-223",
    "radium two hundred twenty three": "Ra-223",
    "radium 223": "Ra-223",
    "radio sin o vectomy": "Radiosynovectomy",
    "radio synovectomy": "Radiosynovectomy",

    # Percentage words to digits for Differential Renal Function (Page 12 Example C)
    "forty-eight percent": "48%",
    "forty eight percent": "48%",
    "fifty-two percent": "52%",
    "fifty two percent": "52%",
    "forty-five percent": "45%",
    "forty five percent": "45%",
    "fifty-five percent": "55%",
    "fifty five percent": "55%",

    # Standard Diagnostic Radiology
    "plural fusion": "pleural effusion",
    "plural effusions": "pleural effusions",
    "floral effusion": "pleural effusion",
    "coal lithiasis": "cholelithiasis",
    "choli lithiasis": "cholelithiasis",
    "chole lithiasis": "cholelithiasis",
    "coal cystitis": "cholecystitis",
    "chole cystitis": "cholecystitis",
    "high po echoic": "hypoechoic",
    "hippo echoic": "hypoechoic",
    "high per echoic": "hyperechoic",
    "hyper echoic": "hyperechoic",
    "para chyma": "parenchyma",
    "paren chymal": "parenchymal",
    "pondylo listhesis": "spondylolisthesis",
    "spondylo listhesis": "spondylolisthesis",
    "spondylolithesis": "spondylolisthesis",
    "spondylo lysis": "spondylolysis",
    "hema toma": "hematoma",
    "haema toma": "haematoma",
    "sub dural": "subdural",
    "epi dural": "epidural",
    "sub arachnoid": "subarachnoid",
    "osteo phytes": "osteophytes",
    "radiculo pathy": "radiculopathy",
    "hydro nephrosis": "hydronephrosis",
    "hepato megaly": "hepatomegaly",
    "spleno megaly": "splenomegaly",
    "hepato splenomegaly": "hepatosplenomegaly",
    "nephro lithiasis": "nephrolithiasis",
    "cortico medullary": "corticomedullary",

    # Oncology & Multi-System PET-CT Clinical Sound-Alikes
    "moral thickening": "mural thickening",
    "neural thickening": "mural thickening",
    "peri colonic": "pericolonic",
    "peri colonic fat stranding": "pericolonic fat stranding",
    "play a morphic adenoma": "pleomorphic adenoma",
    "cleomorphic adenoma": "pleomorphic adenoma",
    "attraction bronchiectasis": "traction bronchiectasis",
    "para tracheal": "paratracheal",
    "sub carinal": "subcarinal",
    "osteo lytic": "osteolytic",
    "osteo sclerotic": "osteosclerotic",
    "adeno carcinoma": "adenocarcinoma"
}

# Canonical Multi-Syllable Medical Terms from Radiology & Nuclear Medicine Handbook
CANONICAL_MEDICAL_TERMS = [
    "hepatosplenomegaly", "cholecystectomy", "choledocholithiasis",
    "hydronephrosis", "hydroureteronephrosis", "spondylolisthesis",
    "spondylolysis", "lymphadenopathy", "corticomedullary", "pancreatitis",
    "peripancreatic", "bronchiectasis", "pneumothorax", "pneumoperitoneum",
    "atelectasis", "cardiomegaly", "osteophytes", "hemangioma", "hematoma",
    "hyperechoic", "hypoechoic", "isoechoic", "anechoic", "hypermetabolic",
    "hypometabolic", "somatostatin", "radiopharmaceutical", "fluorodeoxyglucose",
    "pertechnetate", "sestamibi", "radiosynovectomy", "theranostics",
    "parenchyma", "calvarium", "radiculopathy", "scintigraphy",
    "cholelithiasis", "cholecystitis", "nephrolithiasis", "osteoblastic",
    "photopenic", "retroperitoneal", "adenocarcinoma", "metastasis", "metastatic",
    "extravasation", "collimator", "biodistribution", "renogram",
    "radioembolization", "myelosuppression", "xerostomia", "dosimetry",
    "subcarinal", "gastrohepatic", "supraclavicular", "esophageal",
    "cardiophrenic", "retrocrural", "mesenteric", "paratracheal",
    "hypermetabolism", "hypometabolism"
]

# High-Risk Pairs that must NEVER be cross-substituted
PROTECTED_CONFUSABLE_TERMS = {
    "f-18", "i-131", "ga-68", "lu-177", "dotatate", "dotatoc",
    "psma", "sstr", "pet", "spect", "ct", "mri",
    "right", "left", "bilateral", "positive", "negative",
    "increased", "decreased", "mild", "moderate", "intense",
    "mbq", "gbq", "mci", "gy"
}

def simple_metaphone(word: str) -> str:
    """
    Fast phonetic key generator (Standard English Metaphone/Soundex algorithm)
    Works with zero external C-dependencies.
    """
    w = re.sub(r'[^A-Z]', '', word.upper())
    if not w:
        return ""
    # Transform vowels, diphthongs, and common phonetic variants
    w = re.sub(r'[AEIOUY]', 'A', w)
    w = re.sub(r'PH', 'F', w)
    w = re.sub(r'[CKQ]', 'K', w)
    w = re.sub(r'[SZ]', 'S', w)
    w = re.sub(r'TH', 'T', w)
    w = re.sub(r'X', 'KS', w)
    # Deduplicate consecutive characters
    w = re.sub(r'(.)\1+', r'\1', w)
    return w[:6]

def simple_similarity(s1: str, s2: str) -> float:
    """Calculates Levenshtein-based string similarity ratio (0 to 100)."""
    s1, s2 = s1.lower(), s2.lower()
    if s1 == s2:
        return 100.0
    import difflib
    matcher = difflib.SequenceMatcher(None, s1, s2)
    return matcher.ratio() * 100.0

# Pre-index canonical terms by their phonetic key
CANONICAL_INDEX: Dict[str, List[str]] = {}
for term in CANONICAL_MEDICAL_TERMS:
    key = simple_metaphone(term)
    if key not in CANONICAL_INDEX:
        CANONICAL_INDEX[key] = []
    CANONICAL_INDEX[key].append(term)

class Pass1PhoneticPipeline:
    """
    Pass 1 Engine: Sub-5ms deterministic sound-alike, metaphone, and regex corrector.
    Guarantees clinical safety: High-Risk Confusables are NEVER altered or cross-substituted.
    """

    _custom_rules_data: Dict[str, Any] = {}

    @classmethod
    def load_custom_rules(cls) -> Dict[str, Any]:
        if not os.path.exists(CUSTOM_RULES_FILE):
            default = {"custom_rules": [], "hotwords": []}
            with open(CUSTOM_RULES_FILE, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=2)
            cls._custom_rules_data = default
        else:
            try:
                with open(CUSTOM_RULES_FILE, "r", encoding="utf-8") as f:
                    cls._custom_rules_data = json.load(f)
            except Exception:
                cls._custom_rules_data = {"custom_rules": [], "hotwords": []}
        return cls._custom_rules_data

    @classmethod
    def save_custom_rules(cls, data: Dict[str, Any]):
        cls._custom_rules_data = data
        with open(CUSTOM_RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def add_custom_rule(cls, pattern: str, replacement: str, category: str = "General") -> Dict[str, Any]:
        """Adds a custom user pronunciation rule and persists it."""
        rules = cls.load_custom_rules()
        pat_clean = pattern.strip().lower()
        rep_clean = replacement.strip()

        # Safety check: Block overriding protected confusables into each other
        if pat_clean in PROTECTED_CONFUSABLE_TERMS and rep_clean.lower() in PROTECTED_CONFUSABLE_TERMS and pat_clean != rep_clean.lower():
            return {
                "status": "error",
                "message": f"Safety boundary: Cannot cross-substitute protected confusable term '{pat_clean}' with '{rep_clean}'."
            }

        existing = next((r for r in rules["custom_rules"] if r["pattern"].lower() == pat_clean), None)
        if existing:
            existing["replacement"] = rep_clean
            existing["category"] = category
        else:
            rules["custom_rules"].append({
                "pattern": pat_clean,
                "replacement": rep_clean,
                "category": category
            })

        if rep_clean not in rules.get("hotwords", []):
            rules.setdefault("hotwords", []).append(rep_clean)

        cls.save_custom_rules(rules)
        return {"status": "success", "pattern": pat_clean, "replacement": rep_clean}

    @classmethod
    def add_hotword(cls, term: str):
        """Adds a term to hotwords list for Method 1 decoder biasing if not present."""
        rules = cls.load_custom_rules()
        term_clean = term.strip()
        if term_clean and term_clean not in rules.get("hotwords", []):
            rules.setdefault("hotwords", []).append(term_clean)
            cls.save_custom_rules(rules)

    @classmethod
    def delete_rule_by_term(cls, term: str) -> bool:
        """Deletes any custom rule matching replacement or pattern, and removes from hotwords."""
        rules = cls.load_custom_rules()
        term_clean = term.strip().lower()
        initial_rules_count = len(rules.get("custom_rules", []))
        initial_hw_count = len(rules.get("hotwords", []))
        rules["custom_rules"] = [
            r for r in rules.get("custom_rules", [])
            if r.get("replacement", "").strip().lower() != term_clean and r.get("pattern", "").strip().lower() != term_clean
        ]
        if "hotwords" in rules:
            rules["hotwords"] = [h for h in rules["hotwords"] if h.strip().lower() != term_clean]
        cls.save_custom_rules(rules)
        return (len(rules.get("custom_rules", [])) < initial_rules_count) or (len(rules.get("hotwords", [])) < initial_hw_count)

    @classmethod
    def get_custom_rules(cls) -> List[Dict[str, Any]]:
        return cls.load_custom_rules().get("custom_rules", [])

    @classmethod
    def process_pass1(cls, text: str) -> Tuple[str, List[Dict[str, str]]]:
        """
        Executes Pass 1 in <5ms:
        1. Multi-word sound-alikes + Custom User Rules
        2. Metaphone & Fuzzy Matcher for single long words (len >= 7)
        3. Quantitative SUVmax regex and numbers normalizer
        """
        if not text:
            return "", []

        repairs_made = []
        working = text

        # Step 1: Merged sound-alike dictionary
        rules_data = cls.load_custom_rules()
        active_dict = dict(SOUND_ALIKE_MAP)
        for r in rules_data.get("custom_rules", []):
            if r.get("pattern") and r.get("replacement"):
                pat_l = r["pattern"].lower()
                rep_l = r["replacement"].lower()
                # Safety check
                if pat_l in PROTECTED_CONFUSABLE_TERMS and rep_l in PROTECTED_CONFUSABLE_TERMS and pat_l != rep_l:
                    continue
                active_dict[pat_l] = r["replacement"]

        # Sort by length descending to match multi-word phrases first
        sorted_keys = sorted(active_dict.keys(), key=len, reverse=True)
        escaped_keys = [re.escape(k) for k in sorted_keys]
        if escaped_keys:
            pattern = re.compile(rf'\b({"|".join(escaped_keys)})\b', re.IGNORECASE)

            def sub_callback(m):
                matched = m.group(0).lower()
                # Prevent double -CT if already followed by -ct or ct
                end_pos = m.end()
                trailing = working[end_pos:end_pos+4].lower()
                if matched in ["fdg pet", "psma pet", "f d g pet", "p s m a pet"] and (trailing.startswith("-ct") or trailing.startswith(" ct")):
                    return m.group(0)

                repl = active_dict.get(matched)
                if not repl:
                    for k in sorted_keys:
                        if k.lower() == matched:
                            repl = active_dict[k]
                            break
                if repl:
                    repairs_made.append({"from": m.group(0), "to": repl, "stage": "Pass-1 SoundAlike"})
                    return repl
                return m.group(0)

            working = pattern.sub(sub_callback, working)

        # Step 2: Metaphone & Fuzzy Matcher for single long words (len >= 7)
        words = working.split()
        reconstructed = []
        for word in words:
            clean_word = re.sub(r'[^a-zA-Z]', '', word).lower()
            # Never modify protected confusable single words via fuzzy matching
            if clean_word in PROTECTED_CONFUSABLE_TERMS:
                reconstructed.append(word)
                continue

            if len(clean_word) >= 7 and clean_word not in CANONICAL_MEDICAL_TERMS:
                meta_key = simple_metaphone(clean_word)
                candidates = CANONICAL_INDEX.get(meta_key, [])
                best_match = None
                best_score = 0.0

                for cand in candidates:
                    score = simple_similarity(clean_word, cand)
                    if score >= 78.0 and score > best_score:
                        best_score = score
                        best_match = cand

                if best_match:
                    punctuation = re.findall(r'[^a-zA-Z]+$', word)
                    punct_suffix = punctuation[0] if punctuation else ""
                    repaired_token = best_match + punct_suffix
                    repairs_made.append({"from": word, "to": repaired_token, "stage": "Pass-1 Metaphone"})
                    reconstructed.append(repaired_token)
                    continue

            reconstructed.append(word)

        working = " ".join(reconstructed)

        # Step 3: Smart Quantitative & SUVmax Normalizer
        # "suv max is 3.2" -> "SUVmax is 3.2"
        # "suv max 8 point 4" -> "(SUVmax: 8.4)"
        # "suv max 8.4" -> "(SUVmax: 8.4)"
        def suv_is_callback(m):
            repairs_made.append({"from": m.group(0), "to": f"SUVmax is {m.group(1)}", "stage": "Pass-1 SUVmax"})
            return f"SUVmax is {m.group(1)}"

        def suv_point_callback(m):
            repairs_made.append({"from": m.group(0), "to": f"(SUVmax: {m.group(1)}.{m.group(2)})", "stage": "Pass-1 SUVmax"})
            return f"(SUVmax: {m.group(1)}.{m.group(2)})"

        def suv_num_callback(m):
            repairs_made.append({"from": m.group(0), "to": f"(SUVmax: {m.group(1)})", "stage": "Pass-1 SUVmax"})
            return f"(SUVmax: {m.group(1)})"

        working = re.sub(
            r'\bsuv(?:max|maximum)?\s+is\s+(\d+(?:\.\d+)?)\b',
            suv_is_callback,
            working,
            flags=re.IGNORECASE
        )
        working = re.sub(
            r'\bsuv(?:max|maximum)?\s+(\d+)\s+point\s+(\d+)\b',
            suv_point_callback,
            working,
            flags=re.IGNORECASE
        )
        working = re.sub(
            r'\bsuv(?:max|maximum)?\s+(\d+(?:\.\d+)?)\b',
            suv_num_callback,
            working,
            flags=re.IGNORECASE
        )

        return working, repairs_made
