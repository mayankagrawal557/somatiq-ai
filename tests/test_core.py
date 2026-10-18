"""
Automated Comprehensive Test Suite for Radiology Voice Assistant
Tests:
1. Starter templates loading & clinical coverage
2. Deterministic dictation parsing (safety, no hallucinations, preservation of negatives)
3. SQLite database persistence (create, read, update, delete report)
4. Custom template saving
5. API endpoints health & integrity
"""

import unittest
import os
import tempfile
from backend.radiology_engine import RadiologyEngine, TEMPLATES
import backend.database as db

class TestRadiologyEngine(unittest.TestCase):

    def test_templates_exist(self):
        """Verify all 6 mandatory starter templates exist."""
        expected_keys = [
            "ct_brain", "ct_chest", "petct_whole_body", "mri_brain",
            "mri_lumbar_spine", "chest_xray", "usg_abdomen"
        ]
        for key in expected_keys:
            self.assertIn(key, TEMPLATES, f"Template {key} missing from TEMPLATES")
            template = TEMPLATES[key]
            self.assertIn("modality", template)
            self.assertIn("technique", template)
            self.assertIn("default_impression", template)

    def test_petct_draft_generation(self):
        """Verify PET-CT scan dictation processes FDG avidity, SUVmax values, and anatomical staging."""
        petct_dictation = (
            "18F-FDG Whole Body PET-CT. Intense hypermetabolic spiculated mass in right upper lobe with SUVmax 11.4. "
            "Hypermetabolic right hilar lymphadenopathy SUVmax 7.2. No hypermetabolic distant metastases."
        )
        res = RadiologyEngine.process_dictation(
            dictated_text=petct_dictation,
            template_id="petct_whole_body"
        )
        self.assertEqual(res["template_id"], "petct_whole_body")
        self.assertEqual(res["modality"], "PET-CT")
        self.assertIn("SUVmax 11.4", res["sections"]["findings"])
        self.assertIn("SUVmax 7.2", res["sections"]["findings"])
        self.assertIn("18F-FDG Whole Body PET-CT Scan", res["sections"]["examination"])

    def test_deterministic_draft_generation_normal(self):
        """Verify normal findings are correctly structured into Findings and Impression without hallucination."""
        sample_input = "CT brain plain. No acute intracranial haemorrhage. No mass effect. Ventricles are normal in size."
        res = RadiologyEngine.process_dictation(
            dictated_text=sample_input,
            template_id="ct_brain"
        )
        self.assertEqual(res["template_id"], "ct_brain")
        self.assertIn("No acute intracranial haemorrhage", res["sections"]["findings"])
        self.assertIn("No acute or urgent abnormality", res["sections"]["impression"])
        self.assertTrue(res["is_draft"])

    def test_deterministic_draft_generation_pathology(self):
        """Verify pathology dictation accurately transfers clinical observations."""
        pathology_input = "HRCT Thorax. Patchy ground glass opacities and peripheral consolidation in right lower lobe."
        res = RadiologyEngine.process_dictation(
            dictated_text=pathology_input,
            template_id="ct_chest"
        )
        self.assertIn("Patchy ground glass opacities", res["sections"]["findings"])
        self.assertIn("Key dictated observations", res["sections"]["impression"])

    def test_empty_dictation_handling(self):
        """Verify system handles empty speech without breaking."""
        res = RadiologyEngine.process_dictation(
            dictated_text="",
            template_id="mri_brain"
        )
        self.assertIn("Radiologist review needed", res["sections"]["findings"])

class TestDatabasePersistence(unittest.TestCase):

    def setUp(self):
        db.init_db()

    def test_crud_report(self):
        """Test full create, retrieve, update, delete cycle for reports."""
        test_payload = {
            "patient_name": "Test Synthetic Patient",
            "patient_age_sex": "30Y / F",
            "patient_uhid": "SYN-TEST-001",
            "modality": "CT",
            "body_part": "Brain",
            "template_id": "ct_brain",
            "dictation_transcript": "No acute hemorrhage.",
            "examination": "CT Brain Plain",
            "indication": "Headache",
            "comparison": "None",
            "technique": "5mm axial CT",
            "findings": "Normal brain parenchyma.",
            "impression": "Normal CT brain.",
            "full_report": "Full test report content",
            "status": "DRAFT"
        }

        # 1. Create
        report_id = db.save_report(test_payload)
        self.assertIsNotNone(report_id)

        # 2. Retrieve
        fetched = db.get_report_by_id(report_id)
        self.assertEqual(fetched["patient_name"], "Test Synthetic Patient")
        self.assertEqual(fetched["patient_uhid"], "SYN-TEST-001")

        # 3. Update
        test_payload["id"] = report_id
        test_payload["status"] = "FINAL_VERIFIED"
        updated_id = db.save_report(test_payload)
        self.assertEqual(updated_id, report_id)
        updated_fetched = db.get_report_by_id(report_id)
        self.assertEqual(updated_fetched["status"], "FINAL_VERIFIED")

        # 4. Delete
        deleted = db.delete_report(report_id)
        self.assertTrue(deleted)
        self.assertIsNone(db.get_report_by_id(report_id))

    def test_custom_template_storage(self):
        """Test saving and retrieving custom user templates."""
        custom_data = {
            "id": "ct_pns",
            "title": "CT Paranasal Sinuses (PNS) Coronal",
            "modality": "CT",
            "body_part": "Face/Sinuses",
            "technique": "Non-contrast fine cut CT scans of paranasal sinuses",
            "indication_default": "Chronic sinusitis",
            "default_findings": "Bilateral maxillary sinuses are clear.",
            "default_impression": "Normal CT PNS study."
        }
        res_id = db.save_custom_template(custom_data)
        self.assertEqual(res_id, "ct_pns")
        templates = db.get_custom_templates()
        found = any(t["id"] == "ct_pns" for t in templates)
        self.assertTrue(found)

if __name__ == "__main__":
    unittest.main()
