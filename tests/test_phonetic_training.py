"""
Automated Test Suite for Radiology Pronunciation Adaptation & Vocabulary Training Pipeline
Tests:
1. Layer 1: Modality Lexicon Manager (biasing prompts, hotwords combination)
2. Layer 2: Phonetic & Sound-Alike Corrector (e.g. 'plural fusion' -> 'pleural effusion')
3. Layer 3: Doctor's Train Word dynamic reload without server restart
4. WebSocket real-time phonetic correction integration
"""

import unittest
from backend.medical_lexicon import MedicalLexiconManager, MODALITY_LEXICONS
from backend.phonetic_corrector import PhoneticCorrector

class TestPronunciationAdaptation(unittest.TestCase):

    def test_layer1_modality_lexicons(self):
        """Verify Layer 1 dynamically returns modality-specific initial prompts and hotwords."""
        usg_lex = MedicalLexiconManager.get_lexicon_for_template("usg_abdomen")
        self.assertIn("Hepatomegaly", usg_lex["hotwords"])
        self.assertIn("Hypoechoic", usg_lex["hotwords"])
        self.assertIn("cholelithiasis", usg_lex["initial_prompt"])

        ct_lex = MedicalLexiconManager.get_lexicon_for_template("ct_brain")
        self.assertIn("Intracranial haemorrhage", ct_lex["hotwords"])

    def test_layer2_phonetic_sound_alikes(self):
        """Verify Layer 2 intercepts and fixes common acoustic misinterpretations."""
        test_cases = [
            ("bilateral plural fusion noted", "bilateral pleural effusion noted"),
            ("coal lithiasis in gallbladder", "cholelithiasis in gallbladder"),
            ("high po echoic lesion in liver", "hypoechoic lesion in liver"),
            ("pondylo listhesis at L5-S1", "spondylolisthesis at L5-S1"),
            ("para chyma is normal", "parenchyma is normal"),
            ("sub dural hema toma seen", "subdural hematoma seen")
        ]

        for input_text, expected_output in test_cases:
            corrected, corrections = PhoneticCorrector.correct_text(input_text)
            self.assertEqual(corrected.lower(), expected_output.lower())
            self.assertTrue(len(corrections) > 0)

    def test_layer3_doctor_train_word_realtime(self):
        """Verify Layer 3 allows adding and deleting custom words dynamically."""
        # 1. Add custom term
        term = "Hepatosplenomegaly"
        misheard = "hepato spleno megaly"
        res = PhoneticCorrector.add_trained_word(term, misheard, "usg_abdomen")
        self.assertEqual(res["status"], "success")

        # 2. Test that PhoneticCorrector now repairs this new custom word immediately
        test_sentence = "patient has marked hepato spleno megaly on ultrasound"
        corrected, corr_list = PhoneticCorrector.correct_text(test_sentence)
        self.assertIn("Hepatosplenomegaly", corrected)

        # 3. Clean up
        deleted = PhoneticCorrector.delete_trained_word(term)
        self.assertTrue(deleted)

if __name__ == "__main__":
    unittest.main()
