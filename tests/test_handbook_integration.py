"""
Unit & Integration Tests for Nuclear Medicine Terminology Handbook Integration
Uses standard library unittest (zero dependencies).
Tests:
1. Vocabulary JSON and CSV file structure, completeness, and categories
2. Context biasing and phrase hints injection
3. Phonetic pipeline normalization without changing clinical meaning
4. Protected confusable safety (no cross-substitution of F-18 vs I-131, Ga-68 vs Lu-177, etc.)
5. ClinicalQualityChecker (laterality, negation, measurements, activity units)
6. Handbook Section 8 Synthetic Sample Dictations (Examples A, B, C, D, E)
"""

import os
import json
import unittest

from backend.quality_safety_checker import ClinicalQualityChecker, HANDBOOK_VOCAB_PATH
from backend.phonetic_pipeline import Pass1PhoneticPipeline
from backend.context_biasing import ContextBiasingEngine
from backend.radiology_engine import RadiologyEngine
from backend.llm_post_corrector import LLMPostCorrector

class TestHandbookIntegration(unittest.TestCase):

    def test_handbook_vocabulary_file_exists_and_structured(self):
        self.assertTrue(os.path.exists(HANDBOOK_VOCAB_PATH), "Vocabulary JSON file missing")
        with open(HANDBOOK_VOCAB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("handbook_metadata", data)
        self.assertIn("sections", data)
        sections = data["sections"]
        self.assertIn("pet_ct", sections)
        self.assertIn("gamma_camera_spect", sections)
        self.assertIn("therapeutic_theranostics", sections)
        self.assertIn("high_risk_confusables", sections)
        self.assertIn("abbreviations_and_units", sections)

        # Check companion CSV
        csv_path = os.path.join(os.path.dirname(HANDBOOK_VOCAB_PATH), "nuclear_medicine_handbook_vocab.csv")
        self.assertTrue(os.path.exists(csv_path), "Vocabulary CSV companion file missing")

    def test_context_biasing_phrase_hints(self):
        # PET/CT profile
        pet_profile = ContextBiasingEngine.get_profile("petct_fdg_whole_body")
        self.assertIn("18F-FDG", pet_profile["hotwords"])
        self.assertIn("SUVmax", pet_profile["hotwords"])
        self.assertIn("DOTATATE", pet_profile["hotwords"])

        # SPECT profile
        spect_profile = ContextBiasingEngine.get_profile("spect_bone_scan")
        self.assertIn("99mTc-MDP", spect_profile["hotwords"])
        self.assertIn("MAG3", spect_profile["hotwords"])
        self.assertIn("Sestamibi", spect_profile["hotwords"])

        # Theranostics profile
        thera_profile = ContextBiasingEngine.get_profile("thera_lu177_psma")
        self.assertIn("Lu-177", thera_profile["hotwords"])
        self.assertIn("I-131", thera_profile["hotwords"])
        self.assertIn("MBq", thera_profile["hotwords"])
        self.assertIn("GBq", thera_profile["hotwords"])

    def test_protected_confusables_never_cross_substituted(self):
        # Custom rule attempt to substitute high-risk confusables must be rejected
        res = Pass1PhoneticPipeline.add_custom_rule("f-18", "i-131")
        self.assertEqual(res.get("status"), "error")

        res = Pass1PhoneticPipeline.add_custom_rule("ga-68", "lu-177")
        self.assertEqual(res.get("status"), "error")

        res = Pass1PhoneticPipeline.add_custom_rule("pet", "spect")
        self.assertEqual(res.get("status"), "error")

        res = Pass1PhoneticPipeline.add_custom_rule("right", "left")
        self.assertEqual(res.get("status"), "error")

    def test_handbook_example_a_fdg_petct(self):
        """
        Example A — FDG PET/CT:
        Dictation: 'FDG PET CT from skull base to mid thighs. Mildly increased uptake in the described right hilar lymph node. SUV max is 3.2. Please correlate with the diagnostic CT and clinical history.'
        Expected: Preserve tracer, scan coverage, right-sided location, SUVmax value, and uncertainty. Never invent cancer diagnosis.
        """
        raw_dictation = "FDG PET CT from skull base to mid thighs. Mildly increased uptake in the described right hilar lymph node. SUV max is 3.2. Please correlate with the diagnostic CT and clinical history."
        norm_text, repairs = Pass1PhoneticPipeline.process_pass1(raw_dictation)

        self.assertIn("SUVmax is 3.2", norm_text)

        analysis = ClinicalQualityChecker.analyze_transcript(norm_text, "petct_fdg_whole_body")
        flag_types = [f["type"] for f in analysis["quality_flags"]]
        self.assertIn("LATERALITY_CONFIRMED", flag_types)
        self.assertIn("NEGATION_POLARITY_GUARD", flag_types)

        report = RadiologyEngine.process_dictation(raw_dictation, "petct_fdg_whole_body")
        sections = report["sections"]
        self.assertTrue("FDG PET CT" in sections["findings"] or "FDG" in sections["findings"])
        self.assertIn("right hilar lymph node", sections["findings"])
        self.assertTrue("3.2" in sections["findings"])
        self.assertNotIn("cancer diagnosis", report["full_formatted_text"].lower())

    def test_handbook_example_b_bone_scintigraphy(self):
        """
        Example B — Bone scintigraphy:
        Dictation: 'Technetium ninety-nine MDP whole body bone scan. Mild degenerative-pattern uptake in the bilateral knees. No additional focal abnormal uptake is described.'
        Expected: Normalize isotope spelling (99mTc-MDP). Preserve 'bilateral knees'. Do not add findings elsewhere.
        """
        raw_dictation = "Technetium ninety-nine MDP whole body bone scan. Mild degenerative-pattern uptake in the bilateral knees. No additional focal abnormal uptake is described."
        norm_text, repairs = Pass1PhoneticPipeline.process_pass1(raw_dictation)

        self.assertIn("99mTc-MDP", norm_text)
        self.assertIn("bilateral knees", norm_text)

        analysis = ClinicalQualityChecker.analyze_transcript(norm_text, "spect_bone_scan")
        flag_types = [f["type"] for f in analysis["quality_flags"]]
        self.assertIn("LATERALITY_CONFIRMED", flag_types)

        report = RadiologyEngine.process_dictation(raw_dictation, "spect_bone_scan")
        self.assertIn("bilateral knees", report["sections"]["findings"])

    def test_handbook_example_c_renal_scintigraphy(self):
        """
        Example C — Renal scintigraphy:
        Dictation: 'MAG three renogram. Differential renal function is right forty-eight percent and left fifty-two percent.'
        Expected: Normalize to MAG3. Verify values total 100% as a quality check without altering dictated values.
        """
        raw_dictation = "MAG three renogram. Differential renal function is right forty-eight percent and left fifty-two percent."
        norm_text, repairs = Pass1PhoneticPipeline.process_pass1(raw_dictation)

        self.assertIn("MAG3", norm_text)
        self.assertIn("48%", norm_text)
        self.assertIn("52%", norm_text)

        analysis = ClinicalQualityChecker.analyze_transcript(norm_text, "spect_renal_dtpa")
        split_check = analysis["split_function_check"]
        self.assertIsNotNone(split_check)
        self.assertEqual(split_check["right_pct"], 48.0)
        self.assertEqual(split_check["left_pct"], 52.0)
        self.assertEqual(split_check["total_sum"], 100.0)
        self.assertTrue(split_check["is_balanced"])

    def test_handbook_example_d_therapeutic_report(self):
        """
        Example D — Therapeutic report:
        Dictation: 'Post therapy imaging following lutetium one hundred seventy-seven PSMA treatment. Please refer to the treatment record for administered activity.'
        Expected: Normalize 177Lu-PSMA. Preserves therapy name, administered activity left unspecified unless in verified record.
        """
        raw_dictation = "Post therapy imaging following lutetium one hundred seventy-seven PSMA treatment. Please refer to the treatment record for administered activity."
        norm_text, repairs = Pass1PhoneticPipeline.process_pass1(raw_dictation)

        self.assertIn("177Lu-PSMA", norm_text)

        analysis = ClinicalQualityChecker.analyze_transcript(norm_text, "thera_lu177_psma")
        has_ga_lu = any(f.get("type") == "CONFUSABLE_ALERT" and "Ga-68 vs Lu-177" in f.get("pair") for f in analysis["quality_flags"])
        self.assertTrue(has_ga_lu)

    def test_handbook_example_e_uncertain_laterality(self):
        """
        Example E — Uncertain speech:
        Audio says: 'left paratracheal node but laterality is unclear.'
        Expected: Mark laterality as uncertain and request human confirmation. Never silently choose left or right.
        """
        raw_dictation = "left paratracheal node but laterality is unclear."
        norm_text, _ = Pass1PhoneticPipeline.process_pass1(raw_dictation)

        analysis = ClinicalQualityChecker.analyze_transcript(norm_text, "petct_fdg_whole_body")
        flag_types = [f["type"] for f in analysis["quality_flags"]]
        self.assertIn("LATERALITY_UNCERTAIN", flag_types)
        self.assertTrue(analysis["human_review_required"])

        uncertain_categories = [u["category"] for u in analysis["uncertain_terms"]]
        self.assertIn("Laterality Uncertainty", uncertain_categories)

    def test_activity_units_verification(self):
        text_gbq = "Administered activity was 7.4 GBq of Lu-177."
        analysis = ClinicalQualityChecker.analyze_transcript(text_gbq, "thera_lu177_psma")
        flag_types = [f["type"] for f in analysis["quality_flags"]]
        self.assertIn("ACTIVITY_UNIT_CHECK", flag_types)

if __name__ == "__main__":
    unittest.main()
