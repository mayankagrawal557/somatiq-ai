# PET/CT de-identified starter dataset

## Contents
- `petct_report_structured.json`: one de-identified report represented as a structured JSON object.
- `report_generation.jsonl`: one JSONL example mapping clinical details/procedure/comparison/findings to the source impression and closing.
- `deidentified_clinical_petct_report.pdf`: de-identified PDF source used for this extraction.

## Important limitations
- This package contains **one report only**. It is a schema/prototype example, not a useful training corpus by itself.
- No audio file or verified verbatim dictation transcript was supplied. Therefore this is **not** an audio-to-text or speech-recognition training pair.
- Report text is preserved from the supplied source as closely as possible. It has not been clinically edited or verified by a radiologist.
- Some clinical dates can be identifying in context. The biopsy date remains in the clinical indication because it was part of the clinical narrative. Apply your organization’s date-handling policy before external sharing or model training.
- Before using real patient reports, complete a documented de-identification review, check PDF metadata/embedded images/OCR layers, and ensure the data is authorized for the intended use.

## Suggested dataset growth
For each authorized report, create:
1. A de-identified source report.
2. Structured fields: study type, indication, technique, comparison, findings by region, impression, recommendations.
3. If training voice recognition: a real, verified transcript aligned to the actual audio (with speaker consent/authorization and no identifiers).
4. If training report generation: input dictation or structured clinical observations paired with the reviewed final report.
5. Quality labels: de-identification reviewed, transcription checked, radiologist reviewed, and any uncertain words flagged.

Never invent clinical findings to fill missing fields. Preserve uncertainty and source wording unless a qualified reviewer approves edits.
