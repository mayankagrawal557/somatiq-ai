"""
Unit and Integration Tests for Step 3 Teleradiology Worklist & SLA Service.
"""

import unittest
from fastapi.testclient import TestClient
from backend.main import app
from backend.worklist_service import WorklistService, CreateStudyRequest, UpdateStudyStatusRequest


class TestWorklistService(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        # Reset studies to clean seeds for each test
        WorklistService.save_all_studies(WorklistService._get_seed_studies())

    def test_get_worklist_sorting_and_stats(self):
        """Verify worklist returns seeded studies with STAT first and valid KPIs."""
        response = self.client.get("/api/worklist")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("studies", data)
        self.assertIn("stats", data)
        studies = data["studies"]
        stats = data["stats"]

        self.assertGreaterEqual(len(studies), 5)
        # Verify first study is STAT
        self.assertEqual(studies[0]["priority"], "STAT")
        self.assertEqual(studies[0]["patient_name"], "Rajveer Singh")
        self.assertEqual(studies[0]["template_key"], "ct_brain")

        # Verify stats presence
        self.assertIn("stat_pending", stats)
        self.assertIn("queue_pending", stats)
        self.assertIn("signed_today", stats)
        self.assertIn("avg_tat_minutes", stats)

    def test_create_study_auto_sla(self):
        """Verify adding a study assigns proper modality/priority SLA targets."""
        payload = {
            "patient_name": "Kavita Rao",
            "age_gender": "38Y / Female",
            "patient_phone": "9812345678",
            "modality": "X-RAY",
            "template_key": "chest_xray",
            "study_name": "Chest X-Ray PA View",
            "clinical_history": "Cough with mild hemoptysis",
            "priority": "STAT"
        }
        res = self.client.post("/api/worklist", json=payload)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        study = body["study"]

        self.assertEqual(study["patient_name"], "Kavita Rao")
        self.assertEqual(study["priority"], "STAT")
        # X-RAY base 12 mins / 2 = 6 mins for STAT
        self.assertEqual(study["sla_target_minutes"], 6)
        self.assertTrue(study["uhid"].startswith("SOM-"))

    def test_update_status_and_signing(self):
        """Verify updating status to SIGNED records signed_at timestamp and final report."""
        # Get first study
        worklist_res = self.client.get("/api/worklist").json()
        target_id = worklist_res["studies"][0]["id"]

        patch_payload = {
            "status": "SIGNED",
            "final_report_html": "<p><b>IMPRESSION:</b> No acute intracranial abnormality.</p>",
            "patient_summary": "Scan shows no acute stroke or bleed."
        }
        patch_res = self.client.patch(f"/api/worklist/{target_id}/status", json=patch_payload)
        self.assertEqual(patch_res.status_code, 200)
        updated = patch_res.json()["study"]

        self.assertEqual(updated["status"], "SIGNED")
        self.assertIsNotNone(updated["signed_at"])
        self.assertIn("IMPRESSION", updated["final_report_html"])
        self.assertEqual(updated["patient_summary"], "Scan shows no acute stroke or bleed.")

    def test_whatsapp_dispatch_and_url(self):
        """Verify WhatsApp dispatch generates standard clinical message and valid wa.me link."""
        worklist_res = self.client.get("/api/worklist").json()
        study_id = worklist_res["studies"][0]["id"]

        send_payload = {
            "recipient_type": "both",
            "base_url": "http://localhost:8000"
        }
        res = self.client.post(f"/api/worklist/{study_id}/send-whatsapp", json=send_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertTrue(data["success"])
        self.assertIn("https://wa.me/91", data["whatsapp_web_url"])
        self.assertIn("/report/view/", data["report_url"])
        self.assertIn("DEPARTMENT OF RADIOLOGY", data["message_preview"])

    def test_public_report_view_html(self):
        """Verify public report view endpoint returns clean, printable letterhead HTML."""
        worklist_res = self.client.get("/api/worklist").json()
        study = worklist_res["studies"][0]

        res = self.client.get(f"/report/view/{study['id']}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))
        html = res.text

        self.assertIn("DEPARTMENT OF RADIOLOGY & IMAGING", html)
        self.assertIn(study["patient_name"], html)
        self.assertIn(study["uhid"], html)
        self.assertIn("Digitally Signed", html)
        self.assertIn("window.print()", html)


if __name__ == "__main__":
    unittest.main()
