"""
Automated Test Suite for Nuclear Medicine, PET-CT & Theranostics Module
Tests:
1. All 18 Target Templates Loaded in Registry
2. Nuclear Medicine Sound-Alike Interceptions (<30ms)
3. Nuclear Medicine Spoken Voice Macros (normal bone scan, normal brain pet, normal dtpa)
4. SUVmax numerical voice command formatting
5. Gemini / Deterministic Structured Drafts for Nuclear Medicine Services
"""

import unittest
from backend.radiology_engine import TEMPLATES, RadiologyEngine
from backend.nuclear_med_vocab import NUCLEAR_MED_TEMPLATES, NUCLEAR_MED_HOTWORDS
from backend.phonetic_corrector import PhoneticCorrector
from backend.voice_commands import VoiceCommandInterceptor

class TestNuclearMedicineTheranostics(unittest.TestCase):

    def test_all_18_services_registered(self):
        """Verify all 18 target Nuclear Medicine, PET-CT, and Theranostics services exist in TEMPLATES."""
        target_services = [
            # Category 1: PET-CT
            "petct_fdg_whole_body", "petct_psma", "petct_dotanoc", "petct_brain", "petct_cardiac",
            # Category 2: Gamma Camera / SPECT
            "spect_bone_scan", "spect_renal_dtpa", "spect_renal_dmsa", "spect_thyroid",
            "spect_cardiac_perfusion", "spect_lung_vq", "spect_hida", "spect_brain",
            # Category 3: Theranostics
            "thera_radioiodine_i131", "thera_lu177_psma", "thera_lu177_dotatate",
            "thera_ac225_psma", "thera_bone_pain_palliation", "thera_radiosynovectomy"
        ]
        for service_id in target_services:
            self.assertIn(service_id, TEMPLATES, f"Service {service_id} missing from TEMPLATES")
            self.assertIn(service_id, NUCLEAR_MED_TEMPLATES)

    def test_nuclear_medicine_phonetic_sound_alikes(self):
        """Verify real-time interception of nuclear medicine sound-alikes."""
        cases = [
            ("patient scheduled for f d g pet ct", "patient scheduled for FDG PET-CT"),
            ("plasma pet scan for prostate", "PSMA PET-CT scan for prostate"),
            ("dot a knock pet for neuroendocrine tumor", "DOTANOC pet for neuroendocrine tumor"),
            ("daughter tate scan", "DOTATATE scan"),
            ("f d g avid mass noted", "FDG-avid mass noted"),
            ("photo penic defect in liver", "photopenic defect in liver"),
            ("deauville score 2", "Deauville score 2"),
            ("d t p a renal scan", "DTPA renal scan"),
            ("hide a scan shows patent cbd", "HIDA scan shows patent cbd"),
            ("brain spec reveals hypoperfusion", "Brain SPECT reveals hypoperfusion"),
            ("loo 177 therapy cycle 1", "Lu-177 therapy cycle 1"),
            ("actinium 225 alpha therapy", "Ac-225 alpha therapy"),
            ("radio sin o vectomy of right knee", "Radiosynovectomy of right knee")
        ]
        for input_text, expected in cases:
            corrected, corrections = PhoneticCorrector.correct_text(input_text)
            self.assertEqual(corrected.lower(), expected.lower())
            self.assertTrue(len(corrections) > 0)

    def test_nuclear_medicine_macros(self):
        """Verify spoken macros expand to standardized nuclear medicine clinical paragraphs."""
        # 1. Normal Bone Scan
        res1 = VoiceCommandInterceptor.process_text("normal bone scan")
        self.assertTrue(res1["macro_applied"])
        self.assertIn("99mTc-MDP bone scintigraphy shows normal symmetrical tracer uptake", res1["text"])

        # 2. Normal Brain PET
        res2 = VoiceCommandInterceptor.process_text("normal brain pet")
        self.assertTrue(res2["macro_applied"])
        self.assertIn("Physiological symmetrical FDG uptake is noted", res2["text"])

        # 3. Normal DTPA
        res3 = VoiceCommandInterceptor.process_text("normal dtpa left")
        self.assertTrue(res3["macro_applied"])
        self.assertIn("prompt cortical uptake, and unobstructed drainage", res3["text"])

    def test_suvmax_voice_command_formatting(self):
        """Verify spoken SUVmax number triggers format as (SUVmax: X.X)."""
        input_text = "spiculated lung mass with suvmax 8 point 4 noted"
        res = VoiceCommandInterceptor.process_text(input_text)
        self.assertIn("(SUVmax: 8.4)", res["text"])

        input_text2 = "hilar node with suvmax 5.2 noted"
        res2 = VoiceCommandInterceptor.process_text(input_text2)
        self.assertIn("(SUVmax: 5.2)", res2["text"])

    def test_theranostics_report_generation(self):
        """Verify Theranostics report structures Lu-177 therapy administration and post-therapy findings."""
        dictation = (
            "Administered 7.4 GBq Lu-177 PSMA. Patient tolerated therapy with no acute reaction. "
            "Post-therapy whole body scan confirms intense tracer avidity in prostate bed and pelvic nodes. "
            "Physiological excretion via kidneys into urinary bladder."
        )
        draft = RadiologyEngine.process_dictation(
            dictated_text=dictation,
            template_id="thera_lu177_psma"
        )
        self.assertEqual(draft["template_id"], "thera_lu177_psma")
        self.assertIn("Lu-177 PSMA", draft["sections"]["findings"])
        self.assertIn("7.4 GBq", draft["sections"]["findings"])

if __name__ == "__main__":
    unittest.main()
