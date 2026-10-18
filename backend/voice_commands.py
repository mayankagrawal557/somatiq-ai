"""
Voice Command Interceptor & Spoken Formatting Parser
Parses dictated punctuation, HTML layout tags, section headings, and clinical macros in real-time.
"""

import re
from typing import Dict, Any, Tuple
from backend.medical_vocab import CLINICAL_MACROS

class VoiceCommandInterceptor:
    """
    Translates spoken vocal commands into structured editor formatting and macro expansions.
    """

    @classmethod
    def process_text(cls, text: str) -> Dict[str, Any]:
        """
        Parses raw dictated text and applies:
        - Punctuation commands ('period', 'full stop', 'comma', 'colon', 'question mark')
        - Formatting commands ('next line', 'new paragraph')
        - Section headings ('heading findings', 'heading impression', 'heading technique')
        - Clinical macros ('normal liver', 'normal kidneys', etc.)
        - Deletion triggers ('clear last sentence')
        """
        if not text:
            return {"text": "", "command": None, "macro_applied": False}

        command_triggered = None
        working_text = text

        # Check for undo/deletion command
        if re.search(r'\b(clear last sentence|delete last sentence|undo that)\b', working_text, re.IGNORECASE):
            return {
                "text": "",
                "command": "clear_last_sentence",
                "macro_applied": False
            }

        # Expand clinical macros first (sorted by length descending so multi-word like 'normal brain pet' matches before 'normal brain')
        macro_applied = False
        sorted_macros = sorted(CLINICAL_MACROS.items(), key=lambda item: len(item[0]), reverse=True)
        for macro_key, macro_val in sorted_macros:
            pattern = re.compile(rf'\b{re.escape(macro_key)}\b', re.IGNORECASE)
            if pattern.search(working_text):
                working_text = pattern.sub(macro_val, working_text)
                macro_applied = True

        # Headings
        working_text = re.sub(r'\bheading findings\b', '<br><h3><strong>FINDINGS:</strong></h3>', working_text, flags=re.IGNORECASE)
        working_text = re.sub(r'\bheading impression\b', '<br><h3><strong>IMPRESSION:</strong></h3>', working_text, flags=re.IGNORECASE)
        working_text = re.sub(r'\bheading technique\b', '<br><h3><strong>TECHNIQUE:</strong></h3>', working_text, flags=re.IGNORECASE)
        working_text = re.sub(r'\bheading indication\b', '<br><h3><strong>CLINICAL INDICATION:</strong></h3>', working_text, flags=re.IGNORECASE)
        working_text = re.sub(r'\bheading comparison\b', '<br><h3><strong>COMPARISON:</strong></h3>', working_text, flags=re.IGNORECASE)
        working_text = re.sub(r'\bheading dosimetry\b', '<br><h3><strong>DOSIMETRY & PRE-MEDICATION:</strong></h3>', working_text, flags=re.IGNORECASE)
        working_text = re.sub(r'\bheading post therapy scan\b', '<br><h3><strong>POST-THERAPY SCINTIGRAPHY:</strong></h3>', working_text, flags=re.IGNORECASE)

        # Spoken Layout
        working_text = re.sub(r'\b(new paragraph|next paragraph)\b', '</p><p>', working_text, flags=re.IGNORECASE)
        working_text = re.sub(r'\b(next line|new line)\b', '<br>', working_text, flags=re.IGNORECASE)

        # Nuclear Medicine specific formatting: "suvmax 8 point 4" -> "(SUVmax: 8.4)" or "suvmax 8.4" -> "(SUVmax: 8.4)"
        working_text = re.sub(
            r'\bsuvmax\s+(\d+)\s+point\s+(\d+)\b',
            r'(SUVmax: \1.\2)',
            working_text,
            flags=re.IGNORECASE
        )
        working_text = re.sub(
            r'\bsuvmax\s+(\d+(?:\.\d+)?)\b',
            r'(SUVmax: \1)',
            working_text,
            flags=re.IGNORECASE
        )

        # Spoken Punctuation
        working_text = re.sub(r'\b(full stop|period)\b', '.', working_text, flags=re.IGNORECASE)
        working_text = re.sub(r'\bcomma\b', ',', working_text, flags=re.IGNORECASE)
        working_text = re.sub(r'\bcolon\b', ':', working_text, flags=re.IGNORECASE)
        working_text = re.sub(r'\bsemicolon\b', ';', working_text, flags=re.IGNORECASE)
        working_text = re.sub(r'\bquestion mark\b', '?', working_text, flags=re.IGNORECASE)
        working_text = re.sub(r'\bhyphen|dash\b', '-', working_text, flags=re.IGNORECASE)

        # Clean spacing around punctuation (protect decimals like 8.4)
        working_text = re.sub(r'\s+([,;:?])', r'\1', working_text)
        working_text = re.sub(r'(?<!\d)\s+\.(?!\d)', '.', working_text)
        working_text = re.sub(r'([,;:?])(?=[^\s<])', r'\1 ', working_text)
        working_text = re.sub(r'(?<!\d)\.(?!\d)(?=[^\s<])', '. ', working_text)

        # Capitalize after periods (not decimals)
        def cap_match(match):
            return match.group(1) + match.group(2).upper()
        working_text = re.sub(r'((?<!\d)\.\s+)([a-z])', cap_match, working_text)
        
        # Capitalize first character
        if working_text and working_text[0].islower():
            working_text = working_text[0].upper() + working_text[1:]

        return {
            "text": working_text.strip(),
            "command": command_triggered,
            "macro_applied": macro_applied
        }
