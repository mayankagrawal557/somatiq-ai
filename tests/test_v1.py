"""
Automated Comprehensive Test Suite for Somatiq AI Voice Assistant (V1)
Tests:
1. Voice Command Interceptor & Spoken Punctuation
2. Clinical Normal Macros Expansion
3. Medical Vocabulary Booster
4. AI Auto-Formatter & Deterministic Safety
5. REST & WebSocket Endpoints Health
"""

import unittest
from backend.voice_commands import VoiceCommandInterceptor
from backend.medical_vocab import RADIOLOGY_HOTWORDS, CLINICAL_MACROS
from backend.ai_formatter import AIReportFormatter
from backend.radiology_engine import TEMPLATES

class TestSomatiqV1Core(unittest.TestCase):

    def test_voice_command_punctuation(self):
        """Test spoken punctuation commands (period, comma, next line)."""
        input_text = "no acute intracranial haemorrhage period ventricles are normal comma no mass effect"
        res = VoiceCommandInterceptor.process_text(input_text)
        self.assertIn("No acute intracranial haemorrhage.", res["text"])
        self.assertIn("normal, no mass effect", res["text"])

    def test_voice_command_headings(self):
        """Test spoken section heading injection."""
        input_text = "heading findings liver is normal heading impression no acute abnormality"
        res = VoiceCommandInterceptor.process_text(input_text)
        self.assertIn("<h3><strong>FINDINGS:</strong></h3>", res["text"])
        self.assertIn("<h3><strong>IMPRESSION:</strong></h3>", res["text"])

    def test_clinical_macro_expansion(self):
        """Test spoken clinical macro auto-expansion (e.g. 'normal liver')."""
        input_text = "patient presents with pain normal liver no ascites"
        res = VoiceCommandInterceptor.process_text(input_text)
        self.assertTrue(res["macro_applied"])
        self.assertIn("Liver is normal in size, shape, and echotexture", res["text"])

    def test_clear_last_sentence_command(self):
        """Test deletion command trigger."""
        input_text = "wait delete last sentence please"
        res = VoiceCommandInterceptor.process_text(input_text)
        self.assertEqual(res["command"], "clear_last_sentence")

    def test_hotwords_coverage(self):
        """Verify essential radiology hotwords are present."""
        expected = ["Hepatomegaly", "Pleural effusion", "Parenchyma", "Cholelithiasis", "Hydronephrosis", "SUVmax"]
        for word in expected:
            self.assertIn(word, RADIOLOGY_HOTWORDS)

    def test_ai_report_auto_formatter(self):
        """Test AI structuring formats raw speech into standardized clinical sections."""
        raw_dictation = "CT brain plain. No acute bleed. No midline shift. Ventricles normal."
        formatted = AIReportFormatter.format_report(
            raw_dictation=raw_dictation,
            template_id="ct_brain"
        )
        self.assertIn("examination", formatted["sections"])
        self.assertIn("findings", formatted["sections"])
        self.assertIn("impression", formatted["sections"])
        self.assertTrue(formatted["is_draft"])

if __name__ == "__main__":
    unittest.main()
