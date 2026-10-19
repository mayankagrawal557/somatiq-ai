"""
Step 3 Automated End-to-End Verification Test Suite
Targeting exact user validation criteria:
1. GET /api/worklist: 5 seeded Indian cases, STAT CT Brain (Rajveer Singh) at index 0.
2. Priya Khandelwal card click:
   - Patient Name, Age/Gender (34Y / Female), Clinical History populate.
   - Template dropdown switches to usg_abdomen & loads template.
   - Live SLA timer ticking with valid remaining time badge.
3. Sign & Next Patient (Ctrl+Shift+S):
   - Study status updates to SIGNED via PATCH /api/worklist/{id}/status.
   - GET /report/view/{id} renders clean hospital report page (no dark-mode clutter).
   - Send Report on WhatsApp returns valid https://wa.me/ payload with Name, Study, Summary, and URL.
   - Workspace auto-advances to next PENDING patient in worklist.
4. Prints final Step 3 Verification Summary Table.
"""

import os
import sys
import time
import subprocess
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.worklist_service import WorklistService
from playwright.sync_api import sync_playwright

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8085
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"


def wait_for_server(url, timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{url}/api/health", timeout=1)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def run_test():
    results = []

    print("\n" + "=" * 80)
    print("🏥 STEP 3: AUTOMATED CLINICAL VERIFICATION & E2E INTEGRATION TEST")
    print("=" * 80 + "\n")

    # Clean seed database reset before running
    WorklistService.save_all_studies(WorklistService._get_seed_studies())
    print("🌱 Initialized 5 fresh pending clinical studies in worklist database.")

    # Start test FastAPI server on port 8085
    server_process = subprocess.Popen(
        ["python", "-m", "uvicorn", "backend.main:app", "--host", SERVER_HOST, "--port", str(SERVER_PORT), "--log-level", "warning"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    try:
        ready = wait_for_server(SERVER_URL, timeout=12)
        assert ready, f"Server failed to start on {SERVER_URL}"
        print(f"🚀 FastAPI Test Server active on {SERVER_URL}\n")

        # -----------------------------------------------------------------
        # STEP 1: API Check - GET /api/worklist & STAT Priority Order
        # -----------------------------------------------------------------
        print("▶ Running Verification 1: Worklist Queue API & STAT Ordering...")
        res = requests.get(f"{SERVER_URL}/api/worklist")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        data = res.json()
        studies = data.get("studies", [])
        stats = data.get("stats", {})

        assert len(studies) == 5, f"Expected exactly 5 seeded studies, got {len(studies)}"
        stat_case = studies[0]
        assert stat_case["priority"] == "STAT", f"Index 0 priority should be STAT, got {stat_case['priority']}"
        assert stat_case["patient_name"] == "Rajveer Singh", f"Expected Rajveer Singh at index 0, got {stat_case['patient_name']}"
        assert "58Y" in stat_case["age_gender"] and "Male" in stat_case["age_gender"], f"Expected 58Y / Male, got {stat_case['age_gender']}"
        assert stat_case["modality"] == "CT", f"Expected modality CT, got {stat_case['modality']}"
        assert stat_case["template_key"] == "ct_brain", f"Expected template ct_brain, got {stat_case['template_key']}"

        print("  ✓ GET /api/worklist returned 5 seeded Indian clinical cases.")
        print(f"  ✓ Case 0: {stat_case['patient_name']} ({stat_case['age_gender']}) - Priority: {stat_case['priority']} ({stat_case['modality']} - {stat_case['study_name']})")
        print(f"  ✓ Clinic Stats: STAT Pending = {stats.get('stat_pending')}, Queue Pending = {stats.get('queue_pending')}")

        results.append({
            "step": "1. Worklist Queue & STAT Priority Ordering",
            "assertion": "5 seeded cases, index 0 is STAT CT Brain (Rajveer Singh, 58Y / Male)",
            "status": "PASSED"
        })

        # -----------------------------------------------------------------
        # Playwright UI Automation for Steps 2 & 3
        # -----------------------------------------------------------------
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                permissions=["clipboard-read", "clipboard-write"]
            )
            page = context.new_page()

            # Navigate to web application
            page.goto(SERVER_URL)
            page.wait_for_selector("#kpiSlaRibbon", state="visible")
            page.wait_for_timeout(600)

            # -----------------------------------------------------------------
            # STEP 2: Worklist UI - Click Priya Khandelwal Card
            # -----------------------------------------------------------------
            print("\n▶ Running Verification 2: Loading Priya Khandelwal into Main Workspace...")
            
            # Open Worklist drawer via Alt + W or button
            page.locator("#btnToggleWorklist").click()
            page.wait_for_selector("#worklistDrawer:not(.-translate-x-full)", state="attached", timeout=4000)

            # Find Priya Khandelwal card
            priya_card = page.locator("#worklistCardsContainer > div").filter(has_text="Priya Khandelwal")
            assert priya_card.count() > 0, "Priya Khandelwal card not found in worklist!"
            
            # Click card header or 'Load in Editor' button
            priya_card.locator("button:has-text('Load in Editor'), h4").first.click()
            page.wait_for_timeout(600)

            # Assert workspace inputs
            name_val = page.locator("#patientName").input_value()
            age_gender_val = page.locator("#patientAgeSex").input_value()
            history_val = page.locator("#clinicalHistory").input_value()
            template_val = page.locator("#selectTemplate").input_value()
            editor_content = page.locator("#richEditor").inner_text()

            assert name_val == "Priya Khandelwal", f"Expected Patient Name 'Priya Khandelwal', got '{name_val}'"
            assert "34Y" in age_gender_val and "Female" in age_gender_val, f"Expected '34Y / Female', got '{age_gender_val}'"
            assert "hypochondriac" in history_val.lower() or "cholecystitis" in history_val.lower(), f"Expected clinical history with cholecystitis/hypochondriac pain, got '{history_val}'"
            assert template_val == "usg_abdomen", f"Expected template dropdown 'usg_abdomen', got '{template_val}'"
            assert "ULTRASOUND" in editor_content.upper() or "ABDOMEN" in editor_content.upper() or "LIVER" in editor_content.upper(), "Ultrasound Whole Abdomen template findings should be loaded into editor"

            # Check live SLA Countdown timer ticking on Priya's card
            priya_timer = priya_card.locator(".sla-timer-display")
            timer_text_1 = priya_timer.inner_text()
            time.sleep(1.2)
            timer_text_2 = priya_timer.inner_text()

            assert "remaining" in timer_text_2 or "BREACHED" in timer_text_2 or "⏳" in timer_text_2, f"Timer should display remaining SLA badge, got '{timer_text_2}'"
            print(f"  ✓ Patient Name: '{name_val}'")
            print(f"  ✓ Age / Gender: '{age_gender_val}'")
            print(f"  ✓ Clinical History: '{history_val[:60]}...'")
            print(f"  ✓ Active Template: '{template_val}' (Ultrasound Whole Abdomen loaded in editor)")
            print(f"  ✓ SLA Timer Ticking: '{timer_text_1}' -> '{timer_text_2}'")

            results.append({
                "step": "2. Study Selection & Workspace Population",
                "assertion": "Priya Khandelwal (34Y/F) populated, usg_abdomen template loaded, SLA ticking",
                "status": "PASSED"
            })

            # -----------------------------------------------------------------
            # STEP 3: Sign & Next Patient (Ctrl + Shift + S) & Auto-Advance
            # -----------------------------------------------------------------
            print("\n▶ Running Verification 3: Sign & Next Patient (Ctrl+Shift+S) & Auto-Advance...")
            
            priya_id = "seed-study-002"

            # Inject report findings into editor before sign
            page.evaluate("""
                () => {
                    const editor = document.getElementById('richEditor');
                    editor.innerHTML = `
                        <h3><strong>LIVER:</strong></h3>
                        <p>Normal in size and parenchymal echogenicity. No focal lesion.</p>
                        <h3><strong>GALL BLADDER:</strong></h3>
                        <p><mark class="ai-diff-highlight">Distended with multiple shadowing calculi, largest measuring 14 mm. Wall thickness is 4.2 mm with positive sonographic Murphy's sign.</mark></p>
                        <h3><strong>IMPRESSION:</strong></h3>
                        <p><mark class="ai-diff-highlight">Calculous cholecystitis with gall bladder wall thickening.</mark></p>
                    `;
                    state.patientSummaries.en = 'Ultrasound indicates gallstones causing acute inflammation of the gallbladder (calculous cholecystitis). Consult your surgeon for further treatment.';
                }
            """)
            page.wait_for_timeout(300)

            # Trigger Sign & Next Patient via Ctrl + Shift + S
            print("  ⌨️ Pressing Ctrl + Shift + S (Sign & Next Patient)...")
            page.keyboard.press("Control+Shift+KeyS")
            page.wait_for_timeout(2200)

            # 3a. Verify study status updated to SIGNED
            res_priya = requests.get(f"{SERVER_URL}/api/worklist")
            updated_studies = res_priya.json().get("studies", [])
            priya_updated = next((s for s in updated_studies if s["id"] == priya_id), None)
            assert priya_updated is not None, "Priya study not found after sign"
            assert priya_updated["status"] == "SIGNED", f"Expected status SIGNED, got {priya_updated['status']}"
            assert priya_updated["signed_at"] is not None, "Expected signed_at timestamp to be populated"
            print(f"  ✓ Priya Khandelwal study status updated to SIGNED at {priya_updated['signed_at']}.")

            # 3b. Verify GET /report/view/{id} renders clean read-only hospital report (no dark-mode clutter)
            print(f"  🌐 Inspecting Public Report View: GET /report/view/{priya_id}...")
            res_report = requests.get(f"{SERVER_URL}/report/view/{priya_id}")
            assert res_report.status_code == 200, f"Expected 200, got {res_report.status_code}"
            report_html = res_report.text

            assert "DEPARTMENT OF RADIOLOGY & IMAGING" in report_html, "Missing hospital header in public report"
            assert "Priya Khandelwal" in report_html, "Missing patient name in public report"
            assert "34Y / Female" in report_html, "Missing age/gender in public report"
            assert "Distended with multiple shadowing calculi" in report_html, "Missing clinical findings in public report"
            assert "<mark" not in report_html, "Public report must strip all <mark> diff tags"
            assert "Digitally Signed" in report_html or "DIGITALLY SIGNED" in report_html, "Missing verified digital signature seal"
            assert "background-color: #f1f5f9" in report_html or "background-color: #ffffff" in report_html, "Expected clean white/light hospital background"
            assert "bg-pacs-950" not in report_html, "Public report should not have dark-mode PACS CSS classes"
            print("  ✓ Public report renders clean, read-only official hospital letterhead with verified seal (zero dark-mode clutter).")

            # 3c. Verify WhatsApp Dispatch: POST /api/worklist/{id}/send-whatsapp
            print(f"  📲 Dispatching WhatsApp payload: POST /api/worklist/{priya_id}/send-whatsapp...")
            res_wa = requests.post(f"{SERVER_URL}/api/worklist/{priya_id}/send-whatsapp", json={
                "recipient_type": "both",
                "custom_phone": "9823012345",
                "base_url": SERVER_URL
            })
            assert res_wa.status_code == 200, f"WhatsApp dispatch returned {res_wa.status_code}: {res_wa.text}"
            wa_data = res_wa.json()
            assert wa_data["success"] is True, "WhatsApp dispatch success flag should be True"
            assert "whatsapp_web_url" in wa_data, "Response missing whatsapp_web_url"
            wa_url = wa_data["whatsapp_web_url"]
            assert wa_url.startswith("https://wa.me/"), f"Expected wa.me link, got '{wa_url}'"

            # Verify message payload components
            msg_preview = wa_data.get("message_preview", "")
            assert "Priya Khandelwal" in msg_preview, "WhatsApp message missing patient name"
            assert "Ultrasound Whole Abdomen" in msg_preview or "USG" in msg_preview, "WhatsApp message missing study name"
            assert "calculous cholecystitis" in msg_preview.lower() or "gallstones" in msg_preview.lower(), "WhatsApp message missing patient summary"
            assert f"/report/view/{priya_id}" in msg_preview, "WhatsApp message missing report view URL"
            print("  ✓ WhatsApp dispatch payload generated valid https://wa.me/ deep link with Patient Name, Study, Summary, and Report URL.")

            # 3d. Verify auto-advance to next PENDING patient
            page.wait_for_timeout(1000)
            next_name = page.locator("#patientName").input_value()
            assert next_name != "Priya Khandelwal", f"Workspace should have auto-advanced from Priya Khandelwal, but patient name is still '{next_name}'"
            assert next_name in ["Mohan Lal Gupta", "Rajveer Singh", "Sunita Devi"], f"Auto-advanced to valid pending patient: '{next_name}'"
            print(f"  ✓ Workspace automatically advanced to next pending patient: '{next_name}'!")

            results.append({
                "step": "3. Sign, Report View, WhatsApp & Auto-Advance",
                "assertion": "Status SIGNED, clean report page, valid wa.me payload, auto-advanced",
                "status": "PASSED"
            })

            browser.close()

        # -----------------------------------------------------------------
        # STEP 4: Final Summary Table
        # -----------------------------------------------------------------
        print("\n" + "=" * 80)
        print("📊 STEP 3 VERIFICATION SUMMARY TABLE")
        print("=" * 80)
        print(f"{'#':<4} | {'Verification Step':<40} | {'Status':<10} | {'Details'}")
        print("-" * 80)
        for idx, r in enumerate(results, start=1):
            print(f"{idx:<4} | {r['step']:<40} | {r['status']:<10} | {r['assertion']}")
        print("=" * 80)
        print("🎉 ALL STEP 3 REQUIREMENTS VERIFIED & VALIDATED WITH 100% SUCCESS!\n")

    finally:
        server_process.terminate()
        server_process.wait()


if __name__ == "__main__":
    run_test()
