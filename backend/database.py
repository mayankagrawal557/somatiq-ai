"""
Database manager for Radiology Voice Assistant.
Stores report history, custom templates, and audit logs locally in SQLite.
Uses synthetic patient records for zero HIPAA/privacy leakage.
"""

import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(__file__), "radiology.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Reports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT,
            patient_age_sex TEXT,
            patient_uhid TEXT,
            modality TEXT,
            body_part TEXT,
            template_id TEXT,
            dictation_transcript TEXT,
            examination TEXT,
            indication TEXT,
            comparison TEXT,
            technique TEXT,
            findings TEXT,
            impression TEXT,
            full_report TEXT,
            status TEXT DEFAULT 'DRAFT',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Safe column additions for handbook audit fields
    for col_def in [
        ("original_transcript", "TEXT"),
        ("normalized_transcript", "TEXT"),
        ("uncertain_terms", "TEXT"),
        ("quality_flags", "TEXT"),
        ("report_sections", "TEXT"),
        ("provenance", "TEXT"),
        ("human_approval", "TEXT")
    ]:
        try:
            cursor.execute(f"ALTER TABLE reports ADD COLUMN {col_def[0]} {col_def[1]}")
        except sqlite3.OperationalError:
            pass  # column already exists
    
    # Custom templates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_templates (
            id TEXT PRIMARY KEY,
            title TEXT,
            modality TEXT,
            body_part TEXT,
            technique TEXT,
            indication_default TEXT,
            default_findings TEXT,
            default_impression TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

def save_report(data: Dict[str, Any]) -> int:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    def to_json_str(val):
        if val is None:
            return ""
        if isinstance(val, (dict, list)):
            return json.dumps(val)
        return str(val)

    orig_tx = data.get("original_transcript", data.get("dictation_transcript", ""))
    norm_tx = data.get("normalized_transcript", data.get("dictation_transcript", ""))
    unc_terms = to_json_str(data.get("uncertain_terms", []))
    q_flags = to_json_str(data.get("quality_flags", []))
    rep_secs = to_json_str(data.get("report_sections", data.get("sections", {})))
    prov = to_json_str(data.get("provenance", {}))
    h_app = to_json_str(data.get("human_approval", {}))

    report_id = data.get("id")
    if report_id:
        cursor.execute("""
            UPDATE reports SET
                patient_name = ?,
                patient_age_sex = ?,
                patient_uhid = ?,
                modality = ?,
                body_part = ?,
                template_id = ?,
                dictation_transcript = ?,
                examination = ?,
                indication = ?,
                comparison = ?,
                technique = ?,
                findings = ?,
                impression = ?,
                full_report = ?,
                status = ?,
                updated_at = ?,
                original_transcript = ?,
                normalized_transcript = ?,
                uncertain_terms = ?,
                quality_flags = ?,
                report_sections = ?,
                provenance = ?,
                human_approval = ?
            WHERE id = ?
        """, (
            data.get("patient_name", "Synthetic Patient"),
            data.get("patient_age_sex", "45Y / M"),
            data.get("patient_uhid", "SYN-987654"),
            data.get("modality", "CT"),
            data.get("body_part", "Brain"),
            data.get("template_id", "ct_brain"),
            data.get("dictation_transcript", ""),
            data.get("examination", ""),
            data.get("indication", ""),
            data.get("comparison", ""),
            data.get("technique", ""),
            data.get("findings", ""),
            data.get("impression", ""),
            data.get("full_report", ""),
            data.get("status", "DRAFT"),
            now,
            orig_tx,
            norm_tx,
            unc_terms,
            q_flags,
            rep_secs,
            prov,
            h_app,
            report_id
        ))
        conn.commit()
        conn.close()
        return report_id
    else:
        cursor.execute("""
            INSERT INTO reports (
                patient_name, patient_age_sex, patient_uhid, modality, body_part,
                template_id, dictation_transcript, examination, indication,
                comparison, technique, findings, impression, full_report, status, created_at, updated_at,
                original_transcript, normalized_transcript, uncertain_terms, quality_flags, report_sections, provenance, human_approval
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("patient_name", "Synthetic Patient"),
            data.get("patient_age_sex", "45Y / M"),
            data.get("patient_uhid", "SYN-987654"),
            data.get("modality", "CT"),
            data.get("body_part", "Brain"),
            data.get("template_id", "ct_brain"),
            data.get("dictation_transcript", ""),
            data.get("examination", ""),
            data.get("indication", ""),
            data.get("comparison", ""),
            data.get("technique", ""),
            data.get("findings", ""),
            data.get("impression", ""),
            data.get("full_report", ""),
            data.get("status", "DRAFT"),
            now,
            now,
            orig_tx,
            norm_tx,
            unc_terms,
            q_flags,
            rep_secs,
            prov,
            h_app
        ))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return new_id

def get_all_reports() -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    reports = [dict(row) for row in rows]
    conn.close()
    return reports

def get_report_by_id(report_id: int) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_report(report_id: int) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def save_custom_template(data: Dict[str, Any]) -> str:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO custom_templates (
            id, title, modality, body_part, technique, indication_default, default_findings, default_impression
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("id"),
        data.get("title"),
        data.get("modality"),
        data.get("body_part"),
        data.get("technique"),
        data.get("indication_default"),
        data.get("default_findings"),
        data.get("default_impression")
    ))
    conn.commit()
    conn.close()
    return data.get("id")

def get_custom_templates() -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM custom_templates ORDER BY created_at DESC")
    rows = cursor.fetchall()
    templates = [dict(row) for row in rows]
    conn.close()
    return templates
