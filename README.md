# Somatiq AI — Radiology & Nuclear Medicine Voice Dictation Assistant
## Zero-Training 2-Stage Accuracy Pipeline (Method 1 & Method 2)

An enterprise-grade, real-time medical speech-to-text and AI structured reporting workstation built specifically for **Radiology, PET-CT, Gamma Camera (SPECT), and Theranostics** centers.

Designed to overcome Indian English clinician accents and complex radiopharmaceutical terminology (>98% entity accuracy) using a **Zero-Training 2-Stage Pipeline** without requiring expensive acoustic model retraining.

---

## 🌟 The 2-Stage Accuracy Architecture

```
                             DOCTOR DICTATION (Mic / Audio Stream)
                                              │
                                              ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ METHOD 1: Dynamic Contextual Decoder Biasing (`backend/context_biasing.py`)               │
│ - Injects natural-prose `initial_prompt` (prevents list-style Whisper hallucinations)      │
│ - Injects scan-specific `hotwords` (PET-CT, SPECT, Theranostics, Diagnostic Radiology)    │
│ - Enforces anti-hallucination decoder guards:                                             │
│   * condition_on_previous_text=False (eliminates pause loops)                             │
│   * no_speech_threshold=0.6, log_prob_threshold=-1.0, compression_ratio_threshold=2.2    │
└─────────────────────────────────────────────┬─────────────────────────────────────────────┘
                                              │
                                              ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ METHOD 2 (Pass 1): Deterministic Sound-Alike & Metaphone Matcher (<5ms Latency)            │
│ (`backend/phonetic_pipeline.py`)                                                          │
│ - Curated Indian clinical sound-alikes:                                                   │
│   * "daughter knock" ──> "DOTANOC"         * "plasma pet"       ──> "PSMA PET-CT"         │
│   * "daughter tate"  ──> "DOTATATE"        * "hide a scan"      ──> "HIDA Scan"           │
│   * "brain spec"     ──> "Brain SPECT"     * "photo panic"      ──> "photopenic"          │
│   * "plural fusion"  ──> "pleural effusion"* "coal lithiasis"   ──> "cholelithiasis"      │
│ - Double Metaphone & Levenshtein fallback (len >= 7, similarity >= 78%):                  │
│   * Snaps multi-syllable terms (e.g., 'hepatosplenomegally' ──> 'hepatosplenomegaly')     │
│ - Smart Quantitative Normalizer:                                                          │
│   * "SUVmax 8 point 4" / "SUVmax 8.4" ──> "(SUVmax: 8.4)"                                 │
│ - Spoken Voice Commands & Macros:                                                         │
│   * "normal physiological fdg", "normal bone scan", "normal brain pet", "normal dtpa"     │
└─────────────────────────────────────────────┬─────────────────────────────────────────────┘
                                              │
                                              ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ METHOD 2 (Pass 2): Contextual Two-Pass LLM Repair (<150ms Latency)                        │
│ (`backend/llm_post_corrector.py`)                                                         │
│ - Triggered on sentence completion or pauses >700ms via Gemini 2.5 Flash                  │
│   (temperature=0.0, thinking_budget=0 for instant execution)                              │
│ - Fixes remaining mangled phrasing using scan modality context while preserving the       │
│   exact doctor sentence structure, grammar, and observations.                             │
└─────────────────────────────────────────────┬─────────────────────────────────────────────┘
                                              │
                                              ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ PACS DARK-ROOM WORKSPACE & INSTANT DICTIONARY TRAINER (`frontend/`)                       │
│ - Live Method 1 & 2 status badges in top navigation bar                                  │
│ - Live ASR Correction Feed showing real-time phonetic fixes                               │
│ - "➕ Add Pronunciation Rule" quick card (`POST /api/custom-rule`) for instant zero-restart │
│   dictionary additions saved to `custom_rules.json`                                       │
│ - Full A4 hospital print letterhead export (`frontend/print.css`)                         │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Target Services Supported (19 Specialized Scan Types)

### Category A: PET-CT Scans
1. **Whole Body FDG PET-CT** (Oncology staging & restaging)
2. **PSMA PET-CT** (68Ga / 18F-PSMA for prostate cancer)
3. **DOTANOC / DOTATATE PET-CT** (SSTR-avid Neuroendocrine tumors)
4. **Brain PET-CT** (Dementia / Epilepsy metabolic focus)
5. **Cardiac PET-CT** (Myocardial viability assessment)

### Category B: Gamma Camera / SPECT Scans
6. **Bone Scan** (99mTc-MDP Whole Body / Three-Phase)
7. **Renal Scan - DTPA** (Dynamic Diuretic Renography with GFR table)
8. **Renal Scan - DMSA** (Static Cortical Scintigraphy with Split Function %)
9. **Thyroid & Parathyroid** (99mTc-Pertechnetate / Sestamibi MIBI)
10. **Myocardial Perfusion SPECT** (Stress & Rest with LVEF table)
11. **Lung Perfusion Scan** (V/Q Scan - 99mTc-MAA)
12. **HIDA Scan** (Hepatobiliary Scintigraphy - 99mTc-Mebrofenin)
13. **Brain SPECT** (Perfusion - 99mTc-HMPAO / ECD)

### Category C: Therapeutic Nuclear Medicine (Theranostics)
14. **Radioiodine Therapy (I-131)** (Thyroid remnant ablation / DTC)
15. **Lu-177 PSMA Therapy** (Metastatic prostate cancer & post-therapy scan)
16. **Lu-177 DOTATATE Therapy (PRRT)** (GEP-NET with amino acid renal protection)
17. **Ac-225 PSMA Targeted Alpha Therapy (TAT)**
18. **Bone Pain Palliation Therapy** (Samarium-153 / Strontium-89)
19. **Radiosynovectomy** (Y-90 / Rh-186 intra-articular joint therapy)

### Category D: Standard Diagnostic Radiology
- *CT Brain Plain, CT Chest / HRCT Thorax, MRI Brain, MRI Lumbar Spine, Chest X-Ray PA View, Ultrasound Whole Abdomen.*

---

## 🚀 Quick Start Guide

### 1. Launch the Server:
```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### 2. Access the Application:
Open Google Chrome or Microsoft Edge and navigate to:
```
http://127.0.0.1:8000
```

### 3. Run Automated Tests:
```powershell
python -m unittest discover tests
```
Expected output:
```text
Ran 26 tests in 0.200s — OK
```

---

## ⚙️ Environment Configuration (`.env`)

```ini
# Google Gemini API Key (Enables Pass-2 Contextual Repair & Full AI Structuring)
GEMINI_API_KEY=your_gemini_api_key_here

# Cloud STT Fallback (Groq Whisper-large-v3-turbo for sub-second latency)
GROQ_API_KEY=your_groq_api_key_here

# STT Mode: 'dual', 'local', or 'cloud'
STT_MODE=dual
```
*(If no API keys are provided, Pass 1 deterministic correction and local safety report generation operate 100% locally with zero cost).*
