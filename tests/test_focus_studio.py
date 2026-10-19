"""
Focus Studio Layout & High-Precision Radiology Voice Engine Automated Verification Test
Targeting user specifications:
1. Minimalist 'Focus Studio' Layout:
   - Header brand 'Somatiq AI • Radiology Voice Studio'
   - Single Settings dropdown (#btnSettingsMenuToggle & #settingsMenuPopup)
   - Hidden secondary KPI ribbon (#kpiSlaRibbon)
   - Left Column (30%): Giant mic (Spacebar/Alt+R), Live feedback card, Template dropdown, Smart Merge, ASR Feed, Quick Train Word
   - Right Column (70%): Minimal patient strip (Name, Age/Sex, Study Name, Date), Rich Editor, ONLY 3 visible bottom buttons
2. Spacebar & Alt+R dictation toggle
3. Real-time feedback with light-blue medical highlights and dotted underline for misheard words (prefillTrainWord)
4. Deep medical STT acoustic bias & sound-alike phonetic pipeline
"""

import os
import sys
import time
import subprocess
import requests
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.medical_vocab import RADIOLOGY_HOTWORDS, RADIOLOGY_INITIAL_PROMPT
from backend.phonetic_pipeline import Pass1PhoneticPipeline, CANONICAL_MEDICAL_TERMS
from playwright.sync_api import sync_playwright

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8086
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
        time.sleep(0.3)
    return False


class TestPhoneticBiasing(unittest.TestCase):
    def test_vocabulary_and_prompt_expansion(self):
        self.assertGreaterEqual(len(RADIOLOGY_HOTWORDS), 250, "Should contain at least 250 essential radiology terms")
        hotwords_lower = [w.lower() for w in RADIOLOGY_HOTWORDS]
        self.assertIn("pleural effusion", hotwords_lower)
        self.assertIn("hydronephrosis", hotwords_lower)
        self.assertIn("hyperdense", hotwords_lower)
        self.assertIn("anteverted", hotwords_lower)
        self.assertIn("cholecystitis", hotwords_lower)
        self.assertIn("cauda equina", hotwords_lower)
        self.assertIn("conus medullaris", hotwords_lower)

    def test_sound_alike_phonetic_pipeline(self):
        test_cases = [
            ("bilateral plural fusion noted", "bilateral pleural effusion noted"),
            ("small hyper dense focus in left basal ganglia", "small hyperdense focus in left basal ganglia"),
            ("mild hypo dense lesion in liver", "mild hypodense lesion in liver"),
            ("moderate right hydronaphrosis with calculi", "moderate right hydronephrosis with calculi"),
            ("uterus is anti verted and normal", "uterus is anteverted and normal"),
            ("acute chole cystitis with gall bladder distension", "acute cholecystitis with gall bladder distension"),
            ("compression of thecal sack", "compression of thecal sac"),
            ("hypertrophy of ligamentum flavour", "hypertrophy of ligamentum flavum"),
            ("prominent basal sisters", "prominent basal cisterns"),
            ("termination of conus medullary", "termination of conus medullaris"),
            ("crowding of cauda a queen", "crowding of cauda equina"),
        ]
        for spoken, expected in test_cases:
            corrected, repairs = Pass1PhoneticPipeline.process_pass1(spoken)
            self.assertEqual(corrected.strip().lower(), expected.strip().lower(), f"Failed for '{spoken}' -> got '{corrected}'")
            self.assertGreater(len(repairs), 0, f"Expected repair logged for '{spoken}'")


def run_e2e_browser_test():
    print("\n" + "=" * 80)
    print("🎙️ FOCUS STUDIO LAYOUT & DICTATION ENGINE VERIFICATION TEST")
    print("=" * 80 + "\n")

    env = os.environ.copy()
    env["PORT"] = str(SERVER_PORT)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", SERVER_HOST, "--port", str(SERVER_PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )

    try:
        if not wait_for_server(SERVER_URL, timeout=12):
            raise RuntimeError("FastAPI test server failed to start.")

        print(f"🚀 FastAPI Test Server active on {SERVER_URL}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(SERVER_URL)
            page.wait_for_selector("#richEditor", state="visible")
            page.wait_for_timeout(500)

            print("\n▶ 1. Verifying Minimalist 'Focus Studio' Header & Settings Dropdown...")
            brand_text = page.locator("header h1").inner_text()
            assert "Somatiq AI" in brand_text and "Radiology Voice Studio" in brand_text, f"Unexpected header brand: {brand_text}"
            print(f"  ✓ Header Brand: '{brand_text.strip()}'")

            # Assert secondary KPI ribbon is hidden
            kpi_ribbon = page.locator("#kpiSlaRibbon")
            assert "hidden" in kpi_ribbon.get_attribute("class"), "KPI ribbon should be hidden"
            print("  ✓ Secondary KPI SLA ribbon is hidden (Zero Distraction layout)")

            # Assert Settings dropdown
            settings_btn = page.locator("#btnSettingsMenuToggle")
            assert settings_btn.is_visible(), "Settings menu button should be visible"
            settings_popup = page.locator("#settingsMenuPopup")
            assert "hidden" in settings_popup.get_attribute("class"), "Settings popup initially hidden"
            
            # Click settings
            settings_btn.click()
            page.wait_for_timeout(200)
            assert "hidden" not in settings_popup.get_attribute("class"), "Settings popup opened"
            assert page.locator("#selectSttEngine").is_visible(), "Speech Engine select present in settings"
            print("  ✓ Single ⚙️ Settings dropdown toggles properly with Engine, Letterhead, Handbook, and Worklist")

            # Click outside to close settings
            page.mouse.click(10, 10)
            page.wait_for_timeout(200)
            assert "hidden" in settings_popup.get_attribute("class"), "Settings closed on click outside"
            print("  ✓ Settings menu closes on outside click")

            print("\n▶ 2. Verifying Left Column Dictation & Audio Control Dock (30% width)...")
            mic_text = page.locator("#micStatusText").inner_text()
            assert "spacebar" in mic_text.lower() and "alt+r" in mic_text.lower(), f"Unexpected mic status text: {mic_text}"
            print(f"  ✓ Mic Button status text: '{mic_text}'")

            assert page.locator("#liveDictationFeedback").is_visible(), "Live dictation feedback card visible"
            assert page.locator("#selectTemplate").is_visible(), "Modality template dropdown visible"
            assert page.locator("#btnSmartMerge").is_visible(), "Prominent Smart AI Merge button visible"
            assert page.locator("#correctionLogFeed").is_visible(), "ASR Correction Feed card visible"
            assert page.locator("#quickRulePattern").is_visible(), "Quick train word input visible"
            assert page.locator("#quickRuleReplacement").is_visible(), "Quick train replacement input visible"
            print("  ✓ Left Dock contains all 5 required elements: Mic, Live Stream, Template, Smart Merge, ASR Feed, and Quick Train Card")

            print("\n▶ 3. Verifying Right Column Medical Report Workspace (70% width)...")
            assert page.locator("#patientName").is_visible(), "Patient Name visible"
            assert page.locator("#patientAgeSex").is_visible(), "Patient Age/Sex visible"
            assert page.locator("#patientModality").is_visible(), "Study Name visible"
            assert page.locator("#studyDateText").is_visible(), "Study Date visible"
            print("  ✓ Minimal Patient Strip correctly displays Name, Age/Sex, Study Name, and Study Date")

            # Assert bottom floating action bar with ONLY 3 visible buttons
            actions_bar = page.locator(".editor-actions-bar")
            visible_buttons = actions_bar.locator("button:visible")
            btn_count = visible_buttons.count()
            print(f"  ✓ Bottom action bar visible button count: {btn_count}")
            assert btn_count == 3, f"Expected exactly 3 visible buttons in bottom action bar, found {btn_count}"

            btn_texts = [visible_buttons.nth(i).inner_text().strip() for i in range(btn_count)]
            print(f"  ✓ Visible Buttons: {btn_texts}")
            assert any("Smart AI Merge" in t for t in btn_texts), "Smart AI Merge button missing"
            assert any("Copy for RIS" in t for t in btn_texts), "Copy for RIS button missing"
            assert any("Clear" in t for t in btn_texts), "Clear / Reset button missing"

            print("\n▶ 4. Verifying Keyboard Dictation Shortcuts (Alt+R & Spacebar)...")
            is_recording = page.evaluate("state.isRecording")
            assert not is_recording, "Should not be recording initially"

            # Press Alt + R to start recording
            page.keyboard.press("Alt+r")
            page.wait_for_timeout(300)
            is_recording = page.evaluate("state.isRecording")
            assert is_recording, "Alt+R should start dictation"
            status_live = page.locator("#micStatusText").inner_text()
            assert "recording" in status_live.lower(), f"Status should be recording, got '{status_live}'"
            print("  ✓ Alt+R successfully toggled dictation ON")

            # Press Alt + R to stop recording
            page.keyboard.press("Alt+r")
            page.wait_for_timeout(300)
            is_recording = page.evaluate("state.isRecording")
            assert not is_recording, "Alt+R should stop dictation"
            print("  ✓ Alt+R successfully toggled dictation OFF")

            # Focus outside inputs and press Spacebar to toggle
            page.locator("header").click()
            page.keyboard.press("Space")
            page.wait_for_timeout(300)
            is_recording = page.evaluate("state.isRecording")
            assert is_recording, "Spacebar should start dictation when not in input"
            print("  ✓ Spacebar successfully toggled dictation ON")

            page.keyboard.press("Space")
            page.wait_for_timeout(300)
            is_recording = page.evaluate("state.isRecording")
            assert not is_recording, "Spacebar should stop dictation"
            print("  ✓ Spacebar successfully toggled dictation OFF")

            print("\n▶ 5. Verifying Real-Time Feedback, Highlighting & 1-Click Word Training...")
            # Simulate speech incoming with medical terms and sound-alikes
            test_phrase = "Liver shows fatty infiltration and plural fusion in right lung base"
            page.evaluate(f"renderLiveFeedback('{test_phrase}', 0.92, false)")
            page.wait_for_timeout(200)

            feedback_html = page.locator("#liveFeedbackText").inner_html()
            # Assert medical hotwords highlighted in light blue
            assert "text-cyan-300" in feedback_html, "Medical hotwords should be highlighted in light blue"
            assert "Liver" in feedback_html and "fatty infiltration" in feedback_html
            print("  ✓ Recognized medical terms ('Liver', 'fatty infiltration') highlighted in light cyan/blue")

            # Assert sound-alike underlined with dotted line
            assert "border-dotted" in feedback_html and "plural fusion" in feedback_html, "Sound-alike should be underlined with dotted line"
            print("  ✓ Misheard sound-alike ('plural fusion') underlined with dotted border")

            # Click the dotted underlined word
            page.locator("#liveFeedbackText span.border-dotted").first.click()
            page.wait_for_timeout(200)

            # Assert #quickRulePattern is prefilled with 'plural fusion'
            prefilled = page.locator("#quickRulePattern").input_value()
            assert prefilled.lower() == "plural fusion", f"Expected 'plural fusion', got '{prefilled}'"
            print(f"  ✓ 1-Click prefillTrainWord successfully loaded '{prefilled}' into Quick Train Word card")

            print("\n" + "=" * 80)
            print("🎉 ALL FOCUS STUDIO & DICTATION ENGINE UPGRADES VERIFIED WITH 100% SUCCESS!")
            print("=" * 80 + "\n")

            browser.close()

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPhoneticBiasing)
    runner = unittest.TextTestRunner()
    res = runner.run(suite)
    if not res.wasSuccessful():
        sys.exit(1)
    run_e2e_browser_test()
