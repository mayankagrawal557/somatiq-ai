"""
Comprehensive Test Suite for Somatiq AI Voice V1.1 Upgrades:
- Upgrade 1: Persistent Cloud Storage with Automatic Local Fallback (db_service.py + SQL migration)
- Upgrade 2: 'One-Shot' Smart AI Structuring Mode (POST /api/smart-structure, Alt+S, Gender Safety)
- Upgrade 3: Visual AI Diff Highlighting & Sign-Off Workflow
- Upgrade 4: Hospital Pre-Printed Letterhead Calibration Engine
"""

import os
import unittest
import json
from fastapi.testclient import TestClient

from backend.main import app
from backend.db_service import DatabaseService
from backend.smart_structurer import (
    SmartStructurer,
    detect_patient_gender,
    prune_gender_inappropriate_content
)
from backend.phonetic_pipeline import Pass1PhoneticPipeline
from backend.phonetic_corrector import PhoneticCorrector


class TestV11Upgrades(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # -------------------------------------------------------------
    # UPGRADE 1: Persistent Cloud Storage with Local Fallback
    # -------------------------------------------------------------
    def test_upgrade1_schema_file_exists(self):
        """Verifies that supabase_v1_1_schema.sql exists and contains required tables."""
        schema_path = os.path.join(os.path.dirname(__file__), "..", "supabase_v1_1_schema.sql")
        self.assertTrue(os.path.exists(schema_path), "supabase_v1_1_schema.sql must exist in root")
        with open(schema_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("custom_lexicon", content)
        self.assertIn("custom_macros", content)
        self.assertIn("saved_reports", content)
        self.assertIn("letterhead_settings", content)

    def test_upgrade1_db_service_fallback_and_lexicon(self):
        """Tests local SQLite fallback and CRUD for custom lexicon."""
        res = DatabaseService.add_lexicon_term("flair hyper intense", "FLAIR hyperintense", "MRI")
        self.assertIsNotNone(res.get("id"))
        self.assertEqual(res["misheard_phrase"], "flair hyper intense")
        self.assertEqual(res["correct_term"], "FLAIR hyperintense")

        terms = DatabaseService.get_lexicon_terms()
        self.assertGreaterEqual(len(terms), 1)
        found = any(t["correct_term"] == "FLAIR hyperintense" for t in terms)
        self.assertTrue(found)

        deleted = DatabaseService.delete_lexicon_term("FLAIR hyperintense")
        self.assertTrue(deleted)

    def test_upgrade1_db_service_macros(self):
        """Tests custom macro creation and persistence."""
        m = DatabaseService.add_macro("normal chest", "Both lung fields are clear with no focal consolidation.", "Chest")
        self.assertEqual(m["trigger_phrase"], "normal chest")

        macros = DatabaseService.get_macros()
        self.assertTrue(any(i["trigger_phrase"] == "normal chest" for i in macros))

        deleted = DatabaseService.delete_macro("normal chest")
        self.assertTrue(deleted)

    def test_upgrade1_db_service_saved_reports(self):
        """Tests saved reports persistence with final html and patient summary."""
        rep = DatabaseService.save_report({
            "patient_name": "Test Patient",
            "age_gender": "50Y / F",
            "modality": "PET-CT",
            "template_key": "petct_fdg_whole_body",
            "raw_transcript": "No hypermetabolic nodal metastasis.",
            "final_report_html": "<p>Normal scan.</p>",
            "patient_summary": "Your whole body scan is normal with no abnormal activity.",
            "status": "FINALIZED"
        })
        self.assertIsNotNone(rep.get("id"))
        self.assertEqual(rep["patient_name"], "Test Patient")
        self.assertEqual(rep["status"], "FINALIZED")

        reports = DatabaseService.get_saved_reports(limit=5)
        self.assertGreaterEqual(len(reports), 1)

    def test_upgrade1_startup_lexicon_sync(self):
        """Tests that DatabaseService.load_lexicon_into_engine loads terms into Pass1."""
        DatabaseService.add_lexicon_term("plural fusion test", "pleural effusion test", "Chest")
        loaded_count = DatabaseService.load_lexicon_into_engine()
        self.assertGreaterEqual(loaded_count, 1)

        # Check in Pass1PhoneticPipeline
        corrected, repairs = Pass1PhoneticPipeline.process_pass1("Patient has plural fusion test on left side")
        self.assertIn("pleural effusion test", corrected)
        
        # Cleanup
        DatabaseService.delete_lexicon_term("pleural effusion test")
        Pass1PhoneticPipeline.delete_rule_by_term("pleural effusion test")

    # -------------------------------------------------------------
    # UPGRADE 2: "One-Shot" Smart AI Structuring Mode (Alt + S)
    # -------------------------------------------------------------
    def test_upgrade2_gender_detection(self):
        """Verifies gender detection from demographics string."""
        self.assertEqual(detect_patient_gender("45Y / M"), "M")
        self.assertEqual(detect_patient_gender("32Y / F"), "F")
        self.assertEqual(detect_patient_gender("Male, 62 Years"), "M")
        self.assertEqual(detect_patient_gender("Female 28"), "F")
        self.assertIsNone(detect_patient_gender("Age 40"))

    def test_upgrade2_gender_safety_pruning_female(self):
        """Verifies that male organs are stripped when patient is Female."""
        raw_template = (
            "<p>Liver and spleen are normal.</p>\n"
            "<p>Prostate gland is normal in size and attenuation.</p>\n"
            "<p>Urinary bladder is normal.</p>"
        )
        cleaned, pruned = prune_gender_inappropriate_content(raw_template, "F")
        self.assertNotIn("Prostate", cleaned)
        self.assertIn("Liver", cleaned)
        self.assertIn("Urinary bladder", cleaned)
        self.assertGreaterEqual(len(pruned), 1)

    def test_upgrade2_gender_safety_pruning_male(self):
        """Verifies that female organs are stripped when patient is Male."""
        raw_template = (
            "<p>Liver is normal.</p>\n"
            "<p>Uterus and adnexa appear unremarkable.</p>\n"
            "<p>Kidneys are normal.</p>"
        )
        cleaned, pruned = prune_gender_inappropriate_content(raw_template, "M")
        self.assertNotIn("Uterus", cleaned)
        self.assertIn("Liver", cleaned)
        self.assertIn("Kidneys", cleaned)
        self.assertGreaterEqual(len(pruned), 1)

    def test_upgrade2_smart_structure_endpoint(self):
        """Tests the POST /api/smart-structure endpoint."""
        payload = {
            "template_key": "usg_abdomen",
            "current_template_html": "<p><strong>FINDINGS:</strong></p><p>Gallbladder is well distended with normal wall thickness; no calculus, sludge, or mass lesion.</p><p>Prostate gland is normal.</p>",
            "raw_dictation": "14mm calculus in GB neck with mild acoustic shadowing",
            "patient_age_gender": "35Y / Female",
            "modality": "Ultrasound"
        }
        res = self.client.post("/api/smart-structure", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data.get("status"), "success")
        self.assertIn("merged_report_html", data)
        self.assertIn("patient_summary_en", data)
        self.assertIn("patient_summary_hinglish", data)
        self.assertIn("impression", data)

        # Diff highlight tag check
        self.assertIn('<mark class="ai-diff-highlight" data-source="ai-merge">', data["merged_report_html"])
        # Gender safety check: Prostate stripped for Female patient
        self.assertNotIn("Prostate gland", data["merged_report_html"])

    # -------------------------------------------------------------
    # UPGRADE 3: Visual AI Diff Highlighting & Sign-Off Workflow
    # -------------------------------------------------------------
    def test_upgrade3_css_styles_exist(self):
        """Verifies soft amber and soft cyan styles exist in style.css."""
        css_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "style.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        self.assertIn(".ai-diff-highlight", css)
        self.assertIn("rgba(245, 158, 11", css)
        self.assertIn(".phonetic-diff-highlight", css)
        self.assertIn("rgba(6, 182, 212", css)

    def test_upgrade3_print_css_strips_highlights(self):
        """Verifies @media print strips diff highlight backgrounds completely."""
        print_css_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "print.css")
        with open(print_css_path, "r", encoding="utf-8") as f:
            print_css = f.read()
        self.assertIn(".ai-diff-highlight", print_css)
        self.assertIn("background: transparent !important", print_css)
        self.assertIn("border: none !important", print_css)

    def test_upgrade3_html_components_exist(self):
        """Verifies pending badge, next edit, and accept all buttons exist in index.html."""
        html_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn("aiEditsPendingBadge", html)
        self.assertIn("btnNextEdit", html)
        self.assertIn("btnAcceptAllEdits", html)
        self.assertIn("unverifiedEditsModal", html)

    # -------------------------------------------------------------
    # UPGRADE 4: Hospital Pre-Printed Letterhead Calibration Engine
    # -------------------------------------------------------------
    def test_upgrade4_letterhead_endpoints(self):
        """Tests GET and POST /api/letterhead-settings."""
        # Get defaults
        res = self.client.get("/api/letterhead-settings")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("top_margin_mm", data)
        self.assertIn("bottom_margin_mm", data)

        # Save customized margins
        save_res = self.client.post("/api/letterhead-settings", json={
            "preprinted_letterhead": True,
            "top_margin_mm": 55,
            "bottom_margin_mm": 35,
            "include_summary_page2": True
        })
        self.assertEqual(save_res.status_code, 200)
        saved = save_res.json()
        self.assertTrue(saved["preprinted_letterhead"])
        self.assertEqual(saved["top_margin_mm"], 55)
        self.assertEqual(saved["bottom_margin_mm"], 35)
        self.assertTrue(saved["include_summary_page2"])

        # Re-fetch to ensure persistence
        check_res = self.client.get("/api/letterhead-settings")
        self.assertEqual(check_res.status_code, 200)
        check_data = check_res.json()
        self.assertTrue(check_data["preprinted_letterhead"])
        self.assertEqual(check_data["top_margin_mm"], 55)

    def test_upgrade4_html_letterhead_modal(self):
        """Verifies letterhead calibration modal and sliders exist in index.html."""
        html_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn("letterheadModal", html)
        self.assertIn("chkPreprintedLetterhead", html)
        self.assertIn("rngTopMargin", html)
        self.assertIn("rngBottomMargin", html)
        self.assertIn("chkIncludeSummaryPage2", html)
        self.assertIn("printPage2Summary", html)


if __name__ == "__main__":
    unittest.main()
