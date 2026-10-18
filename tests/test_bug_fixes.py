"""
Unit and Integration Tests for Production & Integration Bug Fixes:
1. GET /api/templates returns body_part, header_fields, radiopharmaceutical, sections
2. GET /api/trained-words, POST /api/train-word, DELETE /api/trained-words API and pipeline sync
3. clean_editor_boilerplate & RadiologyEngine boilerplate stripping
4. STT Engine unconfigured handling and audio upload error contract
"""

import unittest
from fastapi.testclient import TestClient
from backend.main import app
from backend.radiology_engine import RadiologyEngine, clean_editor_boilerplate, TEMPLATES
from backend.phonetic_pipeline import Pass1PhoneticPipeline
from backend.stt_engine import SpeechToTextEngine

class TestBugFixes(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_get_templates_includes_body_part_and_header_fields(self):
        """Bug 2 Verification: Verify GET /api/templates returns body_part, header_fields, and sections."""
        resp = self.client.get("/api/templates")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("starter_templates", data)
        templates = data["starter_templates"]
        self.assertGreater(len(templates), 10)

        # Inspect PET-CT FDG whole body template
        petct = next((t for t in templates if t["id"] == "petct_fdg_whole_body"), None)
        self.assertIsNotNone(petct)
        self.assertIn("body_part", petct)
        self.assertNotEqual(petct["body_part"], "undefined")
        self.assertIn("header_fields", petct)
        self.assertIsInstance(petct["header_fields"], list)
        self.assertGreater(len(petct["header_fields"]), 0)
        self.assertIn("radiopharmaceutical", petct)
        self.assertIn("sections", petct)

    def test_trained_words_api_and_pipeline_sync(self):
        """Bug 1 Verification: Verify /api/trained-words GET/POST/DELETE syncs with Pass1PhoneticPipeline."""
        # 1. Validation test: empty term should return 400
        resp_bad = self.client.post("/api/train-word", json={"term": "   ", "misheard": "something"})
        self.assertEqual(resp_bad.status_code, 400)

        # 2. Add trained word with misheard alias
        test_term = "18F-Flurpiridaz"
        test_misheard = "floor peer eye dazz"
        resp_add = self.client.post("/api/train-word", json={
            "term": test_term,
            "misheard": test_misheard,
            "modality": "petct"
        })
        self.assertEqual(resp_add.status_code, 200)

        # Verify GET /api/trained-words returns it
        resp_get = self.client.get("/api/trained-words")
        self.assertEqual(resp_get.status_code, 200)
        trained_list = resp_get.json().get("trained_words", [])
        self.assertTrue(any(w.get("term") == test_term for w in trained_list))

        # Verify Pass1PhoneticPipeline immediately fixes it in live Pass-1
        repaired, changes = Pass1PhoneticPipeline.process_pass1(f"Evaluation using {test_misheard} PET scan.")
        self.assertIn(test_term, repaired)

        # 3. Add trained word WITHOUT misheard (should add to hotwords for biasing)
        solo_term = "Florbetapir"
        resp_solo = self.client.post("/api/train-word", json={
            "term": solo_term,
            "misheard": "",
            "modality": "petct"
        })
        self.assertEqual(resp_solo.status_code, 200)
        rules_data = Pass1PhoneticPipeline.load_custom_rules()
        self.assertIn(solo_term, rules_data.get("hotwords", []))

        # 4. DELETE /api/trained-words removes from both vocab and custom rules / hotwords
        resp_del = self.client.request("DELETE", "/api/trained-words", json={"term": test_term})
        self.assertEqual(resp_del.status_code, 200)

        resp_del_solo = self.client.request("DELETE", "/api/trained-words", json={"term": solo_term})
        self.assertEqual(resp_del_solo.status_code, 200)

        # Confirm removal from rules
        rules_after = Pass1PhoneticPipeline.load_custom_rules()
        self.assertNotIn(solo_term, rules_after.get("hotwords", []))
        self.assertFalse(any(r.get("replacement") == test_term for r in rules_after.get("custom_rules", [])))

    def test_clean_editor_boilerplate_stripping(self):
        """Bug 4 Verification: Verify template boilerplate and placeholders are stripped from FINDINGS."""
        template = TEMPLATES["petct_fdg_whole_body"]
        editor_boilerplate_input = (
            "EXAMINATION:\n"
            "Whole Body FDG PET-CT\n\n"
            "EXAMINATION PARAMETERS:\n"
            "• Radiopharmaceutical: 18F-FDG\n\n"
            "TECHNIQUE:\n"
            "Whole body PET-CT from vertex to mid-thigh.\n\n"
            "CLINICAL INDICATION:\n"
            "Carcinoma lung restaging.\n\n"
            "COMPARISON:\n"
            "None.\n\n"
            "FINDINGS:\n"
            "[Dictate or click AI Auto-Format to populate specific observations]\n"
            "Intense hypermetabolic solitary pulmonary nodule in right upper lobe SUVmax 11.2.\n"
            "No hypermetabolic mediastinal or hilar lymphadenopathy.\n\n"
            "IMPRESSION:\n"
            "[Draft pending review]\n"
            "Solitary FDG-avid right upper lobe lung mass suspicious for primary bronchogenic carcinoma.\n"
        )

        cleaned = clean_editor_boilerplate(editor_boilerplate_input, template)
        
        # Placeholders and pre-filled header text should NOT be present in cleaned findings
        self.assertNotIn("[Dictate or click AI Auto-Format", cleaned)
        self.assertNotIn("[Draft pending review]", cleaned)
        self.assertNotIn("EXAMINATION PARAMETERS", cleaned)

        # Actual dictated findings and impression MUST be retained
        self.assertIn("Intense hypermetabolic solitary pulmonary nodule in right upper lobe SUVmax 11.2", cleaned)
        self.assertIn("Solitary FDG-avid right upper lobe lung mass", cleaned)

        # Run full process_dictation with the editor content
        report = RadiologyEngine.process_dictation(editor_boilerplate_input, "petct_fdg_whole_body")
        self.assertNotIn("[Dictate or click AI Auto-Format", report["sections"]["findings"])
        self.assertNotIn("[Draft pending review]", report["sections"]["impression"])
        self.assertIn("SUVmax 11.2", report["sections"]["findings"])
        self.assertIn("primary bronchogenic carcinoma", report["sections"]["impression"])

    def test_audio_upload_error_handling_when_unconfigured(self):
        """Bug 5 Verification: If STT engine is unconfigured, transcribe_audio returns 422 with helpful error."""
        import os
        # Temporarily unset GROQ and GEMINI API keys
        groq_save = os.environ.pop("GROQ_API_KEY", None)
        gemini_save = os.environ.pop("GEMINI_API_KEY", None)
        google_save = os.environ.pop("GOOGLE_API_KEY", None)

        try:
            # Empty dummy WAV bytes
            dummy_wav = b"RIFF" + b"\x00" * 200
            files = {"file": ("test.wav", dummy_wav, "audio/wav")}
            resp = self.client.post("/api/transcribe-audio", files=files)
            # Should return 422 with actionable message if local whisper is not loaded
            if resp.status_code == 422:
                data = resp.json()
                self.assertIn("detail", data)
                self.assertIn("GROQ_API_KEY or GEMINI_API_KEY", data["detail"])
            else:
                # If local faster-whisper is installed and loaded, it returns 200 with transcription
                self.assertEqual(resp.status_code, 200)
        finally:
            if groq_save:
                os.environ["GROQ_API_KEY"] = groq_save
            if gemini_save:
                os.environ["GEMINI_API_KEY"] = gemini_save
            if google_save:
                os.environ["GOOGLE_API_KEY"] = google_save

if __name__ == "__main__":
    unittest.main()
