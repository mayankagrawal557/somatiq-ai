"""
Test Clinical Dataset Integration:
Validates training sample integration from uploaded de-identified PET/CT report dataset:
- petct_report_structured.json
- report_generation.jsonl
- Sound-alike corrections: moral thickening -> mural thickening, play a morphic adenoma -> pleomorphic adenoma
- Quantitative metrics preservation: SUVmax 21.9, SUVmax 7.3
- Whole Body FDG PET-CT multi-system staging report structuring
"""

import os
import json
import unittest

from backend.phonetic_pipeline import Pass1PhoneticPipeline
from backend.radiology_engine import RadiologyEngine
from backend.quality_safety_checker import ClinicalQualityChecker
from backend.voice_commands import VoiceCommandInterceptor

CLINICAL_SAMPLE_JSON = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "backend", "data", "clinical_sample", "petct_report_structured.json"
)

class TestClinicalDatasetIntegration(unittest.TestCase):

    def test_clinical_dataset_file_structure(self):
        """Verify the uploaded clinical dataset exists and contains structured fields."""
        self.assertTrue(os.path.exists(CLINICAL_SAMPLE_JSON), "clinical sample JSON not found")
        with open(CLINICAL_SAMPLE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["record_id"], "PETCT_DEID_0001")
        self.assertIn("study", data)
        self.assertEqual(data["study"]["radiopharmaceutical"], "18F-FDG")
        self.assertIn("findings", data)
        self.assertIn("abdomen_and_pelvis", data["findings"])
        self.assertIn("head_and_neck", data["findings"])
        self.assertIn("thorax", data["findings"])
        self.assertIn("impression", data)

    def test_phonetic_corrections_for_clinical_sample(self):
        """
        Verify phonetic pipeline repairs acoustic misinterpretations of the clinical terms
        present in this PET-CT dataset.
        """
        raw_speech = (
            "FDG avid irregular circumferential moral thickening involving ascending colon SUVmax 21.9. "
            "Note is made of mild peri colonic fat stranding. "
            "Few tiny enhancing nodules in superficial left parotid gland likely play a morphic adenoma SUVmax 7.3. "
            "Bilateral lung parenchyma shows attraction bronchiectasis. "
            "no distant metastasis"
        )

        # Stage 1: Pass 1 Sound-Alike repair
        corrected, repairs = Pass1PhoneticPipeline.process_pass1(raw_speech)

        self.assertIn("mural thickening", corrected)
        self.assertIn("pericolonic fat stranding", corrected)
        self.assertIn("pleomorphic adenoma", corrected)
        self.assertIn("traction bronchiectasis", corrected)

        # Stage 2: Macro expansion
        expanded = VoiceCommandInterceptor.process_text(corrected)
        final_text = expanded["text"]
        self.assertIn("No hypermetabolic osseous, pulmonary, hepatic, or peritoneal lesion", final_text)

    def test_report_structuring_and_metrics_preservation(self):
        """
        Verify that dictated findings from this case are structured into standard sections
        without hallucination, preserving exact SUVmax metrics (21.9 and 7.3).
        """
        dictated_text = (
            "Recently diagnosed carcinoma ascending colon for staging. "
            "FINDINGS: "
            "Physiological tracer uptake in brain myocardium and liver. "
            "Left parotid gland tiny nodule with SUVmax 7.3 measuring 0.7 by 0.8 cm likely pleomorphic adenoma. "
            "Bilateral reticular ground glass opacities with traction bronchiectasis consistent with interstitial lung disease. "
            "Circumferential mural thickening in ascending colon SUVmax 21.9 with pericolonic fat stranding. "
            "No distant metastasis. "
            "IMPRESSION: "
            "Metabolically active ascending colon primary neoplasm with no distant metastasis."
        )

        report = RadiologyEngine.process_dictation(dictated_text, "petct_fdg_whole_body")
        sections = report["sections"]

        self.assertIn("Whole Body", sections["examination"])
        self.assertIn("SUVmax 21.9", sections["findings"])
        self.assertIn("SUVmax 7.3", sections["findings"])
        self.assertIn("pleomorphic adenoma", sections["findings"])
        self.assertIn("interstitial lung disease", sections["findings"])
        self.assertIn("ascending colon primary neoplasm", sections["impression"])

        # Quality and safety validation
        quality_eval = ClinicalQualityChecker.analyze_transcript(dictated_text, "petct_fdg_whole_body")
        self.assertTrue(any(f["type"] == "CONFUSABLE_ALERT" for f in quality_eval["quality_flags"]))
        self.assertTrue(any(f["type"] == "LATERALITY_CONFIRMED" for f in quality_eval["quality_flags"]))

if __name__ == "__main__":
    unittest.main()
