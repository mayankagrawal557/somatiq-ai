"""
Automated End-to-End Verification Test for Somatiq AI Voice V1.1
Tests complete workflow:
1. Opens application at http://localhost:8000 and monitors console errors.
2. Selects "Ultrasound Whole Abdomen" (usg_abdomen) from dropdown.
3. Sets Patient Age/Gender to "28Y / Female".
4. Injects test dictation: "Liver is 16.8 cm with grade 2 fatty infiltration, gall bladder shows a 14 mm calculus in the neck, rest is normal."
5. Triggers "Smart AI Merge (Alt+S)" and asserts:
   - Network POST /api/smart-structure returns HTTP 200 with valid payload.
   - <mark class="ai-diff-highlight"> elements appear inside report editor.
   - "Prostate" is completely absent from Female abdomen report.
   - Clinical Safety Checks counter updates with pending AI edits.
   - Triggering "Accept All Edits" unwraps all <mark> tags and shows "Verified by Clinician".
   - Opening "Letterhead Setup", toggling "Print on Pre-Printed Letterhead", and saving applies custom margins and hides header banner in print styles.
"""

import sys
import io
import time
import subprocess
import requests

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from playwright.sync_api import sync_playwright

def run_e2e():
    print("=" * 70)
    print("STARTING SOMATIQ AI V1.1 AUTOMATED END-TO-END VERIFICATION")
    print("=" * 70)

    server_process = None
    # 1. Check if server is running or start it
    try:
        r = requests.get("http://localhost:8000/api/health", timeout=1)
        print(f"[*] Local FastAPI server already running (status: {r.status_code})")
    except Exception:
        print("[*] Starting local FastAPI server on http://localhost:8000...")
        server_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        # Wait for server to come up
        for _ in range(30):
            time.sleep(0.5)
            try:
                r = requests.get("http://localhost:8000/api/health", timeout=1)
                if r.status_code == 200:
                    print(f"[*] Server successfully started and healthy! (Health: {r.json()})")
                    break
            except Exception:
                pass
        else:
            print("[!] Server failed to start in time.")
            if server_process:
                server_process.kill()
            sys.exit(1)

    console_logs = []
    console_errors = []

    try:
        with sync_playwright() as p:
            print("[*] Launching Chromium browser...")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Track console messages
            def on_console(msg):
                console_logs.append(f"[{msg.type}] {msg.text}")
                if msg.type in ["error"]:
                    console_errors.append(msg.text)
            page.on("console", on_console)

            # Step 1: Open app & verify no console errors
            print("[1] Opening http://localhost:8000...")
            page.goto("http://localhost:8000", wait_until="networkidle")
            page.wait_for_selector("#richEditor")
            title = page.title()
            print(f"    Page loaded: '{title}'")
            if console_errors:
                print(f"    [WARN] Console errors detected: {console_errors}")
            else:
                print("    ✓ Zero console errors on initial load.")

            # Step 2: Select Ultrasound Whole Abdomen & set Patient Age/Gender to '28Y / Female'
            print("[2] Selecting 'Ultrasound Whole Abdomen' (usg_abdomen) & setting Demographics...")
            page.select_option("#selectTemplate", "usg_abdomen")
            page.wait_for_timeout(400) # Allow template change to populate editor
            
            # Fill patient age/gender
            page.fill("#patientAgeSex", "28Y / Female")
            page.wait_for_timeout(200)

            modality_val = page.input_value("#patientModality")
            print(f"    ✓ Modality: '{modality_val}', Patient: '{page.input_value('#patientAgeSex')}'")

            # Step 3: Inject test dictation string
            test_dictation = "Liver is 16.8 cm with grade 2 fatty infiltration, gall bladder shows a 14 mm calculus in the neck, rest is normal."
            print(f"[3] Injecting test dictation into editor:\n    \"{test_dictation}\"")
            
            # Place dictation in richEditor
            page.evaluate(f"""() => {{
                const ed = document.getElementById('richEditor');
                ed.innerText = "{test_dictation}";
                ed.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}""")
            page.wait_for_timeout(300)

            # Step 4: Trigger Smart AI Merge (Alt+S) & inspect network response
            print("[4] Triggering Smart AI Merge (POST /api/smart-structure)...")
            
            # Set up response listener
            with page.expect_response(lambda response: "/api/smart-structure" in response.url) as response_info:
                # Trigger click on Smart AI Merge button
                page.click("#btnSmartMerge")
            
            merge_response = response_info.value
            print(f"    ✓ Network Response Status: {merge_response.status}")
            assert merge_response.status == 200, f"Expected 200, got {merge_response.status}"
            
            resp_json = merge_response.json()
            print(f"    ✓ Smart Structure Engine: '{resp_json.get('engine')}'")
            print(f"    ✓ Patient Summary (EN): '{resp_json.get('patient_summary_en')[:80]}...'")
            print(f"    ✓ Gender Pruned Organs: {resp_json.get('gender_pruned')}")

            page.wait_for_timeout(800) # Allow DOM update

            # Step 5: Assertions
            print("[5] Running Clinical & DOM Assertions...")
            editor_html = page.inner_html("#richEditor")
            editor_text = page.inner_text("#richEditor")

            # Assertion A: <mark class="ai-diff-highlight"> elements exist
            mark_count = page.evaluate("() => document.querySelectorAll('#richEditor mark.ai-diff-highlight').length")
            print(f"    [A] AI diff highlight marks in editor: {mark_count}")
            assert mark_count > 0, "Expected at least one <mark class='ai-diff-highlight'> in richEditor!"
            print("        ✓ <mark class='ai-diff-highlight'> elements confirmed.")

            # Assertion B: 'Prostate' is NOT present in Female abdomen report
            has_prostate = "prostate" in editor_text.lower()
            print(f"    [B] 'Prostate' present in Female abdomen report: {has_prostate}")
            assert not has_prostate, "Safety violation: 'Prostate' organ should NOT be present in female patient report!"
            print("        ✓ Gender safety check passed: Prostate is absent.")

            # Assertion C: Clinical Safety Checks counter updates with pending AI edits
            safety_badge_visible = page.is_visible("#aiEditsPendingBadge")
            pending_count_text = page.inner_text("#pendingEditsCount")
            print(f"    [C] Safety banner visible: {page.is_visible('#safetyFlagsContainer')}, Pending badge: {safety_badge_visible}, Count: '{pending_count_text}'")
            assert safety_badge_visible, "Expected aiEditsPendingBadge to be visible!"
            assert int(pending_count_text) >= 1, f"Expected pending count >= 1, got {pending_count_text}"
            print(f"        ✓ Live pending edits badge showing: ⚠️ {pending_count_text} AI Edits Pending Review.")

            # Assertion D: Accept All Edits unwraps marks and clears highlights
            print("[D] Testing 'Accept All Edits' click & shortcut workflow...")
            page.click("#btnAcceptAllEdits")
            page.wait_for_timeout(300)

            remaining_marks = page.evaluate("() => document.querySelectorAll('#richEditor mark').length")
            verified_visible = page.is_visible("#clinicianVerifiedBadge")
            print(f"    Remaining marks in editor: {remaining_marks}")
            print(f"    'Verified by Clinician' badge visible: {verified_visible}")
            assert remaining_marks == 0, f"Expected 0 remaining marks after acceptAllEdits, found {remaining_marks}"
            assert verified_visible, "Expected clinicianVerifiedBadge to be visible after accepting edits!"
            print("        ✓ All marks cleanly unwrapped, Clinical Safety Check verified by Clinician.")

            # Test Keyboard Shortcuts: Tab navigation and Ctrl+Enter
            print("[D.2] Testing Keyboard Shortcuts (Tab & Ctrl+Enter)...")
            page.evaluate("""() => {
                const ed = document.getElementById('richEditor');
                ed.innerHTML = '<p>Normal liver. <mark class="ai-diff-highlight">Calculus in GB.</mark> Normal spleen. <mark class="ai-diff-highlight">Free fluid in pelvis.</mark></p>';
                ed.dispatchEvent(new Event('input', { bubbles: true }));
            }""")
            page.wait_for_timeout(200)
            
            # Press Tab inside editor
            page.focus("#richEditor")
            page.keyboard.press("Tab")
            page.wait_for_timeout(200)
            has_focus_ring = page.evaluate("() => document.querySelectorAll('#richEditor mark.current-focus').length")
            print(f"        ✓ Tab navigation highlighted active edit: {has_focus_ring > 0}")
            assert has_focus_ring > 0, "Expected .current-focus on mark after Tab press!"

            # Press Ctrl+Enter to accept all
            page.keyboard.press("Control+Enter")
            page.wait_for_timeout(200)
            marks_after_ctrl_enter = page.evaluate("() => document.querySelectorAll('#richEditor mark').length")
            assert marks_after_ctrl_enter == 0, f"Expected 0 marks after Ctrl+Enter, got {marks_after_ctrl_enter}"
            print("        ✓ Ctrl+Enter cleanly accepted and unwrapped all AI marks.")

            # Assertion E: Letterhead Setup & Calibration Modal
            print("[E] Testing Hospital Pre-Printed Letterhead Calibration...")
            page.click("button:has-text('Letterhead Setup')")
            page.wait_for_selector("#letterheadModal:not(.hidden)")
            print("    ✓ Letterhead Setup modal opened.")

            # Toggle Pre-printed letterhead ON
            page.check("#chkPreprintedLetterhead")
            
            # Set top margin to 52mm and bottom to 38mm
            page.fill("#rngTopMargin", "52")
            page.evaluate("() => document.getElementById('rngTopMargin').dispatchEvent(new Event('input'))")
            page.fill("#rngBottomMargin", "38")
            page.evaluate("() => document.getElementById('rngBottomMargin').dispatchEvent(new Event('input'))")
            page.check("#chkIncludeSummaryPage2")
            page.wait_for_timeout(200)

            # Click Save & Apply Calibration
            page.click("button:has-text('Save & Apply Calibration')")
            page.wait_for_timeout(500)

            # Check dynamic print styles injected into DOM
            print_styles = page.evaluate("() => document.getElementById('dynamicLetterheadStyle') ? document.getElementById('dynamicLetterheadStyle').textContent : ''")
            print(f"    Dynamic Print CSS:\n    {print_styles.strip()}")

            assert "display: none !important" in print_styles, "Expected header to be hidden in print styles!"
            assert "padding-top: 52mm" in print_styles, "Expected padding-top: 52mm in print styles!"
            assert "padding-bottom: 38mm" in print_styles, "Expected padding-bottom: 38mm in print styles!"
            assert "print-page2-summary" in print_styles, "Expected page-2 summary rule in print styles!"
            print("        ✓ Pre-printed hospital letterhead calibration confirmed with exact mm margins and hidden banner.")

            print("=" * 70)
            print("ALL 5 END-TO-END VERIFICATION CHECKS PASSED (100% SUCCESS)!")
            print("=" * 70)

            browser.close()

    finally:
        if server_process:
            print("[*] Terminating test server process...")
            server_process.terminate()
            server_process.wait()

if __name__ == "__main__":
    run_e2e()
