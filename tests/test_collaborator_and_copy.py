import unittest
from fastapi.testclient import TestClient

from backend.main import app
from backend.clinical_collaborator_service import (
    scrub_pii,
    verify_clinical_safety,
    ClinicalCollaboratorService,
    CollaboratorRequest,
    CollaboratorResponse
)

client = TestClient(app)


class TestClinicalCollaboratorAndCopy(unittest.TestCase):

    def test_pii_scrubber(self):
        sample = (
            "Patient Mr. Ramesh Kumar, phone +91 9876543210, "
            "Aadhaar 1234 5678 9012, email patient@hospital.com, "
            "UHID SYN-849201 reported for scan."
        )
        scrubbed = scrub_pii(sample)
        self.assertNotIn("Ramesh Kumar", scrubbed)
        self.assertNotIn("9876543210", scrubbed)
        self.assertNotIn("1234 5678 9012", scrubbed)
        self.assertNotIn("patient@hospital.com", scrubbed)
        self.assertNotIn("SYN-849201", scrubbed)
        self.assertIn("[REDACTED_PHONE]", scrubbed)
        self.assertIn("[REDACTED_AADHAAR]", scrubbed)
        self.assertIn("[REDACTED_EMAIL]", scrubbed)
        self.assertIn("[REDACTED_UHID]", scrubbed)

    def test_clinical_safety_measurements(self):
        source = "Liver measures 16.8 cm. Gallbladder shows a 14 mm calculus."
        valid_ai = "14 mm calculus with hepatomegaly 16.8 cm."
        hallucinated_ai = "14 mm calculus with a new 25 mm cyst."

        self.assertTrue(verify_clinical_safety(source, valid_ai))
        self.assertFalse(verify_clinical_safety(source, hallucinated_ai))

    def test_clinical_safety_laterality(self):
        source = "Right kidney calculus of 8 mm. Left kidney is normal."
        valid_ai = "Right renal calculus."
        self.assertTrue(verify_clinical_safety(source, valid_ai))

        # Only right kidney in source, but AI outputs left kidney calculus
        source_only_right = "Right kidney shows an 8 mm calculus with moderate hydronephrosis."
        inverted_ai = "Left kidney shows an 8 mm calculus."
        self.assertFalse(verify_clinical_safety(source_only_right, inverted_ai))

    def test_collaborator_differentials(self):
        req = CollaboratorRequest(
            action="differentials",
            modality="USG",
            study_name="Ultrasound Whole Abdomen",
            age_gender="28Y / Female",
            clinical_history="Pain right hypochondrium for 3 days",
            findings_html="Gallbladder shows a 14 mm calculus in the neck with acoustic shadowing. Liver is 16.8 cm with grade 2 fatty change."
        )
        res = ClinicalCollaboratorService.execute(req)
        self.assertIsInstance(res, CollaboratorResponse)
        self.assertEqual(res.action, "differentials")
        self.assertIn(res.triage_status, ["ROUTINE", "ATTENTION", "CRITICAL_PANIC"])
        self.assertTrue(len(res.items) > 0)
        self.assertTrue(res.laterality_and_number_check_passed)

    def test_collaborator_concise_impression(self):
        req = CollaboratorRequest(
            action="concise_impression",
            modality="USG",
            study_name="Ultrasound Whole Abdomen",
            age_gender="28Y / Female",
            clinical_history="Right upper quadrant pain",
            findings_html="Gallbladder neck calculus of 14 mm. Liver shows fatty infiltration."
        )
        res = ClinicalCollaboratorService.execute(req)
        self.assertIsInstance(res, CollaboratorResponse)
        self.assertIsNotNone(res.suggested_impression_html)
        self.assertTrue("calculus" in res.suggested_impression_html.lower() or "fatty" in res.suggested_impression_html.lower() or "chole" in res.suggested_impression_html.lower())

    def test_collaborator_critical_alert_detection(self):
        # Scan with panic finding: tension pneumothorax
        req = CollaboratorRequest(
            action="critical_alert",
            modality="CT",
            study_name="CT Chest",
            age_gender="55Y / Male",
            clinical_history="Acute dyspnea",
            findings_html="Large right-sided tension pneumothorax with mediastinal shift to the left."
        )
        res = ClinicalCollaboratorService.execute(req)
        self.assertEqual(res.triage_status, "CRITICAL_PANIC")
        self.assertTrue(any("URGENT" in item.title or "tension pneumothorax" in item.detail.lower() or "pneumothorax" in item.title.lower() for item in res.items))

    def test_collaborator_endpoint_post(self):
        payload = {
            "action": "history_check",
            "modality": "USG",
            "study_name": "Ultrasound Whole Abdomen",
            "age_gender": "28Y / Female",
            "clinical_history": "Right flank pain",
            "findings_html": "Liver normal. Right kidney calculus 6 mm."
        }
        response = client.post("/api/clinical-collaborator", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action"], "history_check")
        self.assertIn("triage_status", data)
        self.assertIn("items", data)
        self.assertIn("summary_title", data)
        self.assertIn("laterality_and_number_check_passed", data)


if __name__ == "__main__":
    unittest.main()
