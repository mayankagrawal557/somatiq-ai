"""
Automated Test Suite for Method 1 & Method 2 Zero-Training Accuracy Pipeline
Tests:
1. Method 1: Dynamic Contextual Decoder Biasing (Modality profiles, natural-prose prompts, anti-hallucination configs)
2. Method 2 (Pass 1): Sub-5ms Deterministic Sound-Alike Dictionary + SUVmax Regex Normalizer
3. Method 2 (Pass 1): Metaphone & Fuzzy Matcher for single long words (len >= 7, ratio >= 78)
4. Method 2 (Pass 2): Gemini 2.5 Flash low-latency Contextual Repair & Structuring
5. Live Custom Rules Persistence (/api/custom-rule into custom_rules.json)
"""

import unittest
import time
from backend.context_biasing import ContextBiasingEngine, WHISPER_ANTI_HALLUCINATION_CONFIG
from backend.phonetic_pipeline import Pass1PhoneticPipeline, simple_metaphone, simple_similarity
from backend.llm_post_corrector import LLMPostCorrector

class TestMethod1And2Pipeline(unittest.TestCase):

    def test_method1_context_biasing_profiles(self):
        """Verify Method 1 returns natural-prose initial prompts and hotwords for all categories."""
        # PET-CT
        petct_prompt = ContextBiasingEngine.get_initial_prompt("petct_fdg_whole_body")
        self.assertIn("Clinical PET-CT Report", petct_prompt)
        self.assertIn("SUVmax 8.4", petct_prompt)
        petct_hotwords = ContextBiasingEngine.get_hotwords_string("petct_fdg_whole_body")
        self.assertIn("SUVmax", petct_hotwords)
        self.assertIn("DOTANOC", petct_hotwords)

        # Gamma Camera / SPECT
        spect_prompt = ContextBiasingEngine.get_initial_prompt("spect_bone_scan")
        self.assertIn("Gamma Camera Scintigraphy Report", spect_prompt)
        self.assertIn("photopenic defect", spect_prompt)

        # Theranostics
        thera_prompt = ContextBiasingEngine.get_initial_prompt("thera_lu177_psma")
        self.assertIn("Therapeutic Nuclear Medicine Report", thera_prompt)
        self.assertIn("Lu-177 PSMA", thera_prompt)

        # Anti-hallucination configuration check
        config = ContextBiasingEngine.get_anti_hallucination_config()
        self.assertFalse(config["condition_on_previous_text"])
        self.assertEqual(config["no_speech_threshold"], 0.6)

    def test_method2_pass1_sound_alike_speed_and_accuracy(self):
        """Verify Pass 1 executes deterministically in <5ms and fixes all target sound-alikes."""
        cases = [
            ("patient scheduled for daughter knock scan", "patient scheduled for DOTANOC scan"),
            ("plasma pet reveals focal uptake", "PSMA PET-CT reveals focal uptake"),
            ("spiculated nodule with suvmax 8 point 4", "spiculated nodule with (SUVmax: 8.4)"),
            ("suv maximum 11.2", "(SUVmax: 11.2)"),
            ("hide a scan reveals normal excretion", "HIDA Scan reveals normal excretion"),
            ("brain spec shows symmetric perfusion", "Brain SPECT shows symmetric perfusion"),
            ("d t p a renogram shows prompt drainage", "DTPA renogram shows prompt drainage"),
            ("d m s a cortical scan", "DMSA cortical scan"),
            ("e c scan for tubular function", "EC Scan for tubular function"),
            ("loo 177 psma cycle 2", "Lu-177 psma cycle 2"),
            ("a c 225 targeted alpha therapy", "Ac-225 targeted alpha therapy"),
            ("i 131 post thyroidectomy", "I-131 post thyroidectomy"),
            ("radio sin o vectomy of knee", "Radiosynovectomy of knee"),
            ("photo panic defect in liver", "photopenic defect in liver"),
            ("bilateral plural fusion", "bilateral pleural effusion"),
            ("coal lithiasis in gallbladder", "cholelithiasis in gallbladder"),
            ("high po echoic lesion", "hypoechoic lesion"),
            ("para chyma is normal", "parenchyma is normal"),
            ("pondylo listhesis at L5-S1", "spondylolisthesis at L5-S1")
        ]

        start_time = time.time()
        for input_text, expected in cases:
            corrected, repairs = Pass1PhoneticPipeline.process_pass1(input_text)
            self.assertEqual(corrected.lower(), expected.lower())
            self.assertTrue(len(repairs) > 0)
        elapsed_ms = (time.time() - start_time) * 1000.0 / len(cases)
        # Verify sub-5ms latency per sentence
        self.assertLess(elapsed_ms, 5.0, f"Pass-1 latency was {elapsed_ms:.2f}ms, expected < 5ms")

    def test_method2_pass1_metaphone_fuzzy_fallback(self):
        """Verify phonetic metaphone fuzzy matcher snaps misheard words len >= 7 to canonical terms."""
        # 'hepatosplenomegally' with double l -> 'hepatosplenomegaly'
        res, repairs = Pass1PhoneticPipeline.process_pass1("marked hepatosplenomegally observed")
        self.assertIn("hepatosplenomegaly", res)

        # 'cholelithiazis' with z -> 'cholelithiasis'
        res2, repairs2 = Pass1PhoneticPipeline.process_pass1("evidence of cholelithiazis noted")
        self.assertIn("cholelithiasis", res2)

    def test_custom_rule_persistence(self):
        """Verify adding and saving custom rules to custom_rules.json."""
        rule_res = Pass1PhoneticPipeline.add_custom_rule("sestamibi scan test", "99mTc-Sestamibi Scan", "SPECT")
        self.assertEqual(rule_res["status"], "success")

        # Test that pipeline instantly corrects it without restart
        corrected, repairs = Pass1PhoneticPipeline.process_pass1("patient requires sestamibi scan test today")
        self.assertIn("99mTc-Sestamibi Scan", corrected)

    def test_method2_pass2_llm_post_corrector_fallback(self):
        """Verify Pass 2 LLM post-corrector handles input and returns valid structure with or without API key."""
        res = LLMPostCorrector.repair_sentence_contextual("FDG avid liver mass", "petct_fdg_whole_body")
        self.assertIn("corrected_text", res)
        self.assertIn("repairs_made", res)

if __name__ == "__main__":
    unittest.main()
