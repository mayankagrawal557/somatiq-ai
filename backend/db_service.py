"""
Somatiq AI V1.1 - Database Persistence Layer
Supports Supabase PostgreSQL with seamless automatic fallback to local SQLite & JSON.
Ensures custom pronunciation lexicon, macros, and saved reports survive container restarts.
"""

import os
import json
import sqlite3
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger("somatiq.db_service")

# Local SQLite DB location
DB_FILE = os.path.join(os.path.dirname(__file__), "radiology.db")
CUSTOM_RULES_FILE = os.path.join(os.path.dirname(__file__), "custom_rules.json")
CUSTOM_VOCAB_FILE = os.path.join(os.path.dirname(__file__), "custom_vocab.json")

# Supabase Credentials from Environment
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip() or os.getenv("SUPABASE_SERVICE_KEY", "").strip()

# Try importing supabase client
supabase_client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client, Client
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized successfully.")
    except Exception as e:
        logger.warning(f"Could not initialize supabase-py client ({e}). Will use REST or local SQLite fallback.")


class DatabaseService:
    """
    Unified Data Persistence Layer for Somatiq AI Voice V1.1.
    Gracefully toggles between Supabase PostgreSQL and local SQLite/JSON.
    """

    @classmethod
    def is_supabase_enabled(cls) -> bool:
        return bool(SUPABASE_URL and SUPABASE_KEY)

    @classmethod
    def get_connection(cls) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_local_db(cls):
        """Initializes SQLite schema matching Supabase V1.1 schema."""
        conn = cls.get_connection()
        cursor = conn.cursor()

        # 1. Custom Lexicon table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_lexicon (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                misheard_phrase TEXT NOT NULL,
                correct_term TEXT NOT NULL,
                modality TEXT DEFAULT 'all',
                doctor_id TEXT DEFAULT 'default_doctor',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lexicon_misheard ON custom_lexicon (misheard_phrase)")

        # 2. Custom Macros table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_macros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger_phrase TEXT NOT NULL UNIQUE,
                expansion_text TEXT NOT NULL,
                modality TEXT DEFAULT 'all',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 3. Saved Reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT DEFAULT 'Synthetic Patient',
                age_gender TEXT DEFAULT '45Y / M',
                modality TEXT DEFAULT 'CT',
                template_key TEXT DEFAULT 'ct_brain',
                raw_transcript TEXT,
                final_report_html TEXT,
                patient_summary TEXT,
                status TEXT DEFAULT 'DRAFT',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 4. Letterhead Settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS letterhead_settings (
                id TEXT PRIMARY KEY,
                preprinted_letterhead INTEGER DEFAULT 0,
                top_margin_mm INTEGER DEFAULT 45,
                bottom_margin_mm INTEGER DEFAULT 30,
                include_summary_page2 INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Ensure default letterhead setting exists
        cursor.execute("""
            INSERT OR IGNORE INTO letterhead_settings (id, preprinted_letterhead, top_margin_mm, bottom_margin_mm, include_summary_page2)
            VALUES ('default_hospital', 0, 45, 30, 0)
        """)

        conn.commit()
        conn.close()

    # -------------------------------------------------------------
    # REST Helper for Supabase when supabase-py is not installed
    # -------------------------------------------------------------
    @classmethod
    def _supabase_request(cls, endpoint: str, method: str = "GET", data: Any = None, params: Dict[str, Any] = None) -> Optional[Any]:
        if not cls.is_supabase_enabled():
            return None
        import requests
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{endpoint.lstrip('/')}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        try:
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers, params=params, timeout=5)
            elif method.upper() == "POST":
                resp = requests.post(url, headers=headers, json=data, timeout=5)
            elif method.upper() == "DELETE":
                resp = requests.delete(url, headers=headers, params=params, timeout=5)
            elif method.upper() == "PATCH":
                resp = requests.patch(url, headers=headers, json=data, params=params, timeout=5)
            else:
                return None
            if resp.status_code in [200, 201, 204]:
                return resp.json() if resp.text else []
            logger.warning(f"Supabase REST error [{resp.status_code}]: {resp.text}")
            return None
        except Exception as e:
            logger.warning(f"Supabase REST request exception: {e}")
            return None

    # -------------------------------------------------------------
    # CUSTOM LEXICON CRUD
    # -------------------------------------------------------------
    @classmethod
    def add_lexicon_term(cls, misheard_phrase: str, correct_term: str, modality: str = "all", doctor_id: str = "default_doctor") -> Dict[str, Any]:
        misheard_clean = misheard_phrase.strip()
        correct_clean = correct_term.strip()

        # 1. Supabase attempt
        if cls.is_supabase_enabled():
            payload = {
                "misheard_phrase": misheard_clean,
                "correct_term": correct_clean,
                "modality": modality,
                "doctor_id": doctor_id
            }
            if supabase_client:
                try:
                    res = supabase_client.table("custom_lexicon").insert(payload).execute()
                    if res.data:
                        cls._save_local_lexicon(misheard_clean, correct_clean, modality, doctor_id)
                        return res.data[0]
                except Exception as e:
                    logger.warning(f"Supabase client insert failed: {e}. Falling back to REST/SQLite.")
            
            res_rest = cls._supabase_request("custom_lexicon", method="POST", data=payload)
            if res_rest and len(res_rest) > 0:
                cls._save_local_lexicon(misheard_clean, correct_clean, modality, doctor_id)
                return res_rest[0]

        # 2. Local SQLite fallback
        return cls._save_local_lexicon(misheard_clean, correct_clean, modality, doctor_id)

    @classmethod
    def _save_local_lexicon(cls, misheard_phrase: str, correct_term: str, modality: str = "all", doctor_id: str = "default_doctor") -> Dict[str, Any]:
        cls.init_local_db()
        conn = cls.get_connection()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO custom_lexicon (misheard_phrase, correct_term, modality, doctor_id, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (misheard_phrase, correct_term, modality, doctor_id, now))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {
            "id": new_id,
            "misheard_phrase": misheard_phrase,
            "correct_term": correct_term,
            "modality": modality,
            "doctor_id": doctor_id,
            "created_at": now
        }

    @classmethod
    def get_lexicon_terms(cls) -> List[Dict[str, Any]]:
        if cls.is_supabase_enabled():
            if supabase_client:
                try:
                    res = supabase_client.table("custom_lexicon").select("*").order("created_at", desc=True).execute()
                    if res.data is not None:
                        return res.data
                except Exception as e:
                    logger.warning(f"Supabase client select failed: {e}")
            res_rest = cls._supabase_request("custom_lexicon", method="GET", params={"order": "created_at.desc"})
            if res_rest is not None and isinstance(res_rest, list):
                return res_rest

        # Local SQLite fallback
        cls.init_local_db()
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM custom_lexicon ORDER BY created_at DESC")
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    @classmethod
    def delete_lexicon_term(cls, term_or_phrase: str) -> bool:
        term_clean = term_or_phrase.strip().lower()
        deleted = False

        if cls.is_supabase_enabled():
            if supabase_client:
                try:
                    supabase_client.table("custom_lexicon").delete().or_(
                        f"correct_term.ilike.{term_clean},misheard_phrase.ilike.{term_clean}"
                    ).execute()
                    deleted = True
                except Exception as e:
                    logger.warning(f"Supabase client delete failed: {e}")
            else:
                cls._supabase_request("custom_lexicon", method="DELETE", params={
                    "or": f"(correct_term.ilike.{term_clean},misheard_phrase.ilike.{term_clean})"
                })
                deleted = True

        # Local SQLite
        cls.init_local_db()
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM custom_lexicon
            WHERE LOWER(correct_term) = ? OR LOWER(misheard_phrase) = ?
        """, (term_clean, term_clean))
        if cursor.rowcount > 0:
            deleted = True
        conn.commit()
        conn.close()
        return deleted

    # -------------------------------------------------------------
    # CUSTOM MACROS CRUD
    # -------------------------------------------------------------
    @classmethod
    def add_macro(cls, trigger_phrase: str, expansion_text: str, modality: str = "all") -> Dict[str, Any]:
        trigger_clean = trigger_phrase.strip()
        expansion_clean = expansion_text.strip()
        now = datetime.now(timezone.utc).isoformat()

        if cls.is_supabase_enabled():
            payload = {
                "trigger_phrase": trigger_clean,
                "expansion_text": expansion_clean,
                "modality": modality
            }
            if supabase_client:
                try:
                    res = supabase_client.table("custom_macros").upsert(payload).execute()
                    if res.data:
                        return res.data[0]
                except Exception as e:
                    logger.warning(f"Supabase macro upsert failed: {e}")
            res_rest = cls._supabase_request("custom_macros", method="POST", data=payload)
            if res_rest and len(res_rest) > 0:
                return res_rest[0]

        # SQLite Fallback
        cls.init_local_db()
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO custom_macros (trigger_phrase, expansion_text, modality, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(trigger_phrase) DO UPDATE SET
                expansion_text=excluded.expansion_text,
                modality=excluded.modality
        """, (trigger_clean, expansion_clean, modality, now))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {
            "id": new_id,
            "trigger_phrase": trigger_clean,
            "expansion_text": expansion_clean,
            "modality": modality,
            "created_at": now
        }

    @classmethod
    def get_macros(cls) -> List[Dict[str, Any]]:
        if cls.is_supabase_enabled():
            if supabase_client:
                try:
                    res = supabase_client.table("custom_macros").select("*").order("created_at", desc=True).execute()
                    if res.data is not None:
                        return res.data
                except Exception as e:
                    logger.warning(f"Supabase macro select failed: {e}")
            res_rest = cls._supabase_request("custom_macros", method="GET", params={"order": "created_at.desc"})
            if res_rest is not None and isinstance(res_rest, list):
                return res_rest

        cls.init_local_db()
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM custom_macros ORDER BY created_at DESC")
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    @classmethod
    def delete_macro(cls, trigger_phrase: str) -> bool:
        t_clean = trigger_phrase.strip().lower()
        if cls.is_supabase_enabled():
            if supabase_client:
                try:
                    supabase_client.table("custom_macros").delete().ilike("trigger_phrase", t_clean).execute()
                except Exception as e:
                    logger.warning(f"Supabase macro delete error: {e}")
            else:
                cls._supabase_request("custom_macros", method="DELETE", params={"trigger_phrase": f"ilike.{t_clean}"})

        cls.init_local_db()
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM custom_macros WHERE LOWER(trigger_phrase) = ?", (t_clean,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    # -------------------------------------------------------------
    # SAVED REPORTS CRUD
    # -------------------------------------------------------------
    @classmethod
    def save_report(cls, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stores finalized or draft report:
        { id, patient_name, age_gender, modality, template_key, raw_transcript, final_report_html, patient_summary, status, created_at }
        """
        patient_name = report_data.get("patient_name", "Synthetic Patient")
        age_gender = report_data.get("age_gender") or report_data.get("patient_age_sex", "45Y / M")
        modality = report_data.get("modality", "CT")
        template_key = report_data.get("template_key") or report_data.get("template_id", "ct_brain")
        raw_transcript = report_data.get("raw_transcript") or report_data.get("dictation_transcript", "")
        final_report_html = report_data.get("final_report_html") or report_data.get("full_report", "")
        patient_summary = report_data.get("patient_summary", "")
        status = report_data.get("status", "DRAFT")
        now = datetime.now(timezone.utc).isoformat()

        payload = {
            "patient_name": patient_name,
            "age_gender": age_gender,
            "modality": modality,
            "template_key": template_key,
            "raw_transcript": raw_transcript,
            "final_report_html": final_report_html,
            "patient_summary": patient_summary,
            "status": status,
            "created_at": now
        }

        # Supabase
        if cls.is_supabase_enabled():
            if supabase_client:
                try:
                    res = supabase_client.table("saved_reports").insert(payload).execute()
                    if res.data:
                        cls._save_local_report(payload)
                        return res.data[0]
                except Exception as e:
                    logger.warning(f"Supabase save_report client failed: {e}")
            res_rest = cls._supabase_request("saved_reports", method="POST", data=payload)
            if res_rest and len(res_rest) > 0:
                cls._save_local_report(payload)
                return res_rest[0]

        # SQLite
        return cls._save_local_report(payload)

    @classmethod
    def _save_local_report(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        cls.init_local_db()
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO saved_reports (
                patient_name, age_gender, modality, template_key,
                raw_transcript, final_report_html, patient_summary, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payload.get("patient_name"),
            payload.get("age_gender"),
            payload.get("modality"),
            payload.get("template_key"),
            payload.get("raw_transcript"),
            payload.get("final_report_html"),
            payload.get("patient_summary"),
            payload.get("status"),
            payload.get("created_at")
        ))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        saved = dict(payload)
        saved["id"] = new_id
        return saved

    @classmethod
    def get_saved_reports(cls, limit: int = 50) -> List[Dict[str, Any]]:
        if cls.is_supabase_enabled():
            if supabase_client:
                try:
                    res = supabase_client.table("saved_reports").select("*").order("created_at", desc=True).limit(limit).execute()
                    if res.data is not None:
                        return res.data
                except Exception as e:
                    logger.warning(f"Supabase get_saved_reports failed: {e}")
            res_rest = cls._supabase_request("saved_reports", method="GET", params={"order": "created_at.desc", "limit": str(limit)})
            if res_rest is not None and isinstance(res_rest, list):
                return res_rest

        cls.init_local_db()
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM saved_reports ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    # -------------------------------------------------------------
    # LETTERHEAD SETTINGS CRUD
    # -------------------------------------------------------------
    @classmethod
    def save_letterhead_settings(cls, settings: Dict[str, Any]) -> Dict[str, Any]:
        preprinted = bool(settings.get("preprinted_letterhead", False))
        top_mm = int(settings.get("top_margin_mm", 45))
        bottom_mm = int(settings.get("bottom_margin_mm", 30))
        include_summary = bool(settings.get("include_summary_page2", False))
        now = datetime.now(timezone.utc).isoformat()

        payload = {
            "id": "default_hospital",
            "preprinted_letterhead": preprinted,
            "top_margin_mm": top_mm,
            "bottom_margin_mm": bottom_mm,
            "include_summary_page2": include_summary,
            "updated_at": now
        }

        if cls.is_supabase_enabled():
            if supabase_client:
                try:
                    supabase_client.table("letterhead_settings").upsert(payload).execute()
                except Exception as e:
                    logger.warning(f"Supabase letterhead upsert failed: {e}")
            else:
                cls._supabase_request("letterhead_settings", method="POST", data=payload)

        cls.init_local_db()
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO letterhead_settings (id, preprinted_letterhead, top_margin_mm, bottom_margin_mm, include_summary_page2, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                preprinted_letterhead=excluded.preprinted_letterhead,
                top_margin_mm=excluded.top_margin_mm,
                bottom_margin_mm=excluded.bottom_margin_mm,
                include_summary_page2=excluded.include_summary_page2,
                updated_at=excluded.updated_at
        """, ("default_hospital", int(preprinted), top_mm, bottom_mm, int(include_summary), now))
        conn.commit()
        conn.close()
        return payload

    @classmethod
    def get_letterhead_settings(cls) -> Dict[str, Any]:
        if cls.is_supabase_enabled():
            if supabase_client:
                try:
                    res = supabase_client.table("letterhead_settings").select("*").eq("id", "default_hospital").execute()
                    if res.data and len(res.data) > 0:
                        return res.data[0]
                except Exception as e:
                    logger.warning(f"Supabase get letterhead failed: {e}")
            res_rest = cls._supabase_request("letterhead_settings", method="GET", params={"id": "eq.default_hospital"})
            if res_rest and len(res_rest) > 0:
                return res_rest[0]

        cls.init_local_db()
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM letterhead_settings WHERE id = 'default_hospital'")
        row = cursor.fetchone()
        conn.close()
        if row:
            d = dict(row)
            d["preprinted_letterhead"] = bool(d.get("preprinted_letterhead", 0))
            d["include_summary_page2"] = bool(d.get("include_summary_page2", 0))
            return d
        return {
            "id": "default_hospital",
            "preprinted_letterhead": False,
            "top_margin_mm": 45,
            "bottom_margin_mm": 30,
            "include_summary_page2": False
        }

    # -------------------------------------------------------------
    # STARTUP SYNC: Load Lexicon into In-Memory Pass-1 Engine
    # -------------------------------------------------------------
    @classmethod
    def load_lexicon_into_engine(cls):
        """
        On server startup, loads all saved custom_lexicon rules from Supabase
        (or local SQLite / custom_rules.json / custom_vocab.json fallback)
        into the in-memory Pass-1 Phonetic (<5ms) replacement engine.
        """
        cls.init_local_db()
        from backend.phonetic_pipeline import Pass1PhoneticPipeline
        from backend.phonetic_corrector import PhoneticCorrector

        # 1. Fetch from Supabase or SQLite
        lexicon_entries = cls.get_lexicon_terms()
        loaded_count = 0

        for entry in lexicon_entries:
            misheard = entry.get("misheard_phrase", "").strip()
            correct = entry.get("correct_term", "").strip()
            modality = entry.get("modality", "all")
            if correct:
                if misheard:
                    Pass1PhoneticPipeline.add_custom_rule(misheard, correct, modality)
                    PhoneticCorrector.add_trained_word(correct, misheard, modality)
                else:
                    Pass1PhoneticPipeline.add_hotword(correct)
                    PhoneticCorrector.add_trained_word(correct, "", modality)
                loaded_count += 1

        # 2. Also ensure local custom_rules.json and custom_vocab.json are loaded
        try:
            vocab = PhoneticCorrector.load_custom_vocab()
            for tw in vocab.get("trained_words", []):
                term = tw.get("term", "").strip()
                misheard = tw.get("misheard", "").strip()
                modality = tw.get("modality", "all")
                if term and misheard:
                    Pass1PhoneticPipeline.add_custom_rule(misheard, term, modality)
        except Exception as e:
            logger.warning(f"Failed syncing local vocab JSON: {e}")

        logger.info(f"Loaded {loaded_count} persistent custom lexicon rules into in-memory Pass-1 engine.")
        return loaded_count
