"""
Local SQLite Fallback Database for AgroNex
Provides zero-setup persistence for users, profiles, and crop history
whenever Supabase Cloud credentials are not configured or offline.
"""

import sqlite3
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import logging

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "agronex.db"
DB_PATH = Path(os.getenv("DATABASE_PATH") or os.getenv("SQLITE_DB_PATH") or str(DEFAULT_DB_PATH))

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_local_db():
    conn = get_connection()
    try:
        with conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mobile TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                hashed_password TEXT NOT NULL,
                location TEXT,
                preferred_language TEXT DEFAULT 'en',
                created_at TEXT NOT NULL
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS farmer_profiles (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                name TEXT,
                mobile TEXT,
                farm_size REAL DEFAULT 0,
                primary_crop TEXT DEFAULT 'Paddy',
                location TEXT,
                preferred_language TEXT DEFAULT 'en',
                notify_weather INTEGER DEFAULT 1,
                notify_spray INTEGER DEFAULT 1,
                notify_schemes INTEGER DEFAULT 1,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """)
            # Safe migration for existing farmer_profiles tables
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(farmer_profiles)")
            cols = [col[1] for col in cur.fetchall()]
            if "notify_weather" not in cols:
                conn.execute("ALTER TABLE farmer_profiles ADD COLUMN notify_weather INTEGER DEFAULT 1;")
            if "notify_spray" not in cols:
                conn.execute("ALTER TABLE farmer_profiles ADD COLUMN notify_spray INTEGER DEFAULT 1;")
            if "notify_schemes" not in cols:
                conn.execute("ALTER TABLE farmer_profiles ADD COLUMN notify_schemes INTEGER DEFAULT 1;")

            conn.execute("""
            CREATE TABLE IF NOT EXISTS crop_analyses (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                crop_type TEXT NOT NULL,
                image_path TEXT,
                detected_disease TEXT NOT NULL,
                confidence REAL NOT NULL,
                severity TEXT DEFAULT 'Not determined',
                risk_level TEXT DEFAULT 'Not determined',
                quality_status TEXT DEFAULT 'Passed',
                weather_context TEXT,
                is_inconclusive INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """)
            # Safe migration for existing crop_analyses tables
            cur.execute("PRAGMA table_info(crop_analyses)")
            crop_cols = [col[1] for col in cur.fetchall()]
            if "quality_status" not in crop_cols:
                conn.execute("ALTER TABLE crop_analyses ADD COLUMN quality_status TEXT DEFAULT 'Passed';")
            if "weather_context" not in crop_cols:
                conn.execute("ALTER TABLE crop_analyses ADD COLUMN weather_context TEXT;")
            if "is_inconclusive" not in crop_cols:
                conn.execute("ALTER TABLE crop_analyses ADD COLUMN is_inconclusive INTEGER DEFAULT 0;")

            conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # Module 5: Database Indexes for Query Performance & History Retrieval
            conn.execute("CREATE INDEX IF NOT EXISTS idx_crop_analyses_created_at ON crop_analyses(created_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_crop_analyses_user_id ON crop_analyses(user_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_created_at ON chat_history(created_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history(user_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_farmer_profiles_user_id ON farmer_profiles(user_id);")
    finally:
        conn.close()

# Auto-initialize tables on module import
init_local_db()

# --- Users & Auth Helpers ---
def save_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_connection()
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            conn.execute("""
            INSERT INTO users (id, name, mobile, email, hashed_password, location, preferred_language, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                user_data["name"],
                user_data["mobile"],
                user_data.get("email"),
                user_data["hashed_password"],
                user_data.get("location"),
                user_data.get("preferred_language", "en"),
                now
            ))
            # Also create default farmer profile
            conn.execute("""
            INSERT INTO farmer_profiles (id, user_id, name, mobile, farm_size, primary_crop, location, preferred_language, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                user_id,
                user_data["name"],
                user_data["mobile"],
                2.5,
                "Paddy",
                user_data.get("location", "Tamil Nadu"),
                user_data.get("preferred_language", "en"),
                now
            ))
        return {
            "id": user_id,
            "name": user_data["name"],
            "mobile": user_data["mobile"],
            "email": user_data.get("email"),
            "location": user_data.get("location"),
            "preferred_language": user_data.get("preferred_language", "en")
        }
    finally:
        conn.close()

def find_user_by_identifier(identifier: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE mobile = ? OR email = ?", (identifier, identifier))
        row = cur.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()

def find_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, mobile, email, location, preferred_language, created_at FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()

# --- Farmer Profile Helpers ---
def get_or_create_profile(user_id: Optional[str] = None) -> Dict[str, Any]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        if user_id:
            cur.execute("SELECT * FROM farmer_profiles WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            if row:
                res = dict(row)
                res["notify_weather"] = bool(res.get("notify_weather", 1))
                res["notify_spray"] = bool(res.get("notify_spray", 1))
                res["notify_schemes"] = bool(res.get("notify_schemes", 1))
                return res

        cur.execute("SELECT * FROM farmer_profiles ORDER BY updated_at DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            res = dict(row)
            res["notify_weather"] = bool(res.get("notify_weather", 1))
            res["notify_spray"] = bool(res.get("notify_spray", 1))
            res["notify_schemes"] = bool(res.get("notify_schemes", 1))
            return res

        # Default farmer fallback
        return {
            "name": "Arun Kumar",
            "mobile": "9876543210",
            "location": "Coimbatore, Tamil Nadu",
            "farm_size": 3.5,
            "primary_crop": "Paddy, Tomato",
            "preferred_language": "ta",
            "notify_weather": True,
            "notify_spray": True,
            "notify_schemes": True
        }
    finally:
        conn.close()

def update_farmer_profile(profile_data: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            existing = None
            if user_id:
                cur = conn.cursor()
                cur.execute("SELECT id FROM farmer_profiles WHERE user_id = ?", (user_id,))
                existing = cur.fetchone()
            if not existing:
                cur = conn.cursor()
                cur.execute("SELECT id FROM farmer_profiles ORDER BY updated_at DESC LIMIT 1")
                existing = cur.fetchone()

            nw = 1 if profile_data.get("notify_weather") is True else (0 if profile_data.get("notify_weather") is False else None)
            ns = 1 if profile_data.get("notify_spray") is True else (0 if profile_data.get("notify_spray") is False else None)
            nc = 1 if profile_data.get("notify_schemes") is True else (0 if profile_data.get("notify_schemes") is False else None)

            if existing:
                prof_id = existing["id"]
                conn.execute("""
                UPDATE farmer_profiles
                SET name = COALESCE(?, name),
                    mobile = COALESCE(?, mobile),
                    farm_size = COALESCE(?, farm_size),
                    primary_crop = COALESCE(?, primary_crop),
                    location = COALESCE(?, location),
                    preferred_language = COALESCE(?, preferred_language),
                    notify_weather = COALESCE(?, notify_weather),
                    notify_spray = COALESCE(?, notify_spray),
                    notify_schemes = COALESCE(?, notify_schemes),
                    updated_at = ?
                WHERE id = ?
                """, (
                    profile_data.get("name"),
                    profile_data.get("mobile"),
                    profile_data.get("farm_size"),
                    profile_data.get("primary_crop"),
                    profile_data.get("location"),
                    profile_data.get("preferred_language"),
                    nw,
                    ns,
                    nc,
                    now,
                    prof_id
                ))
            else:
                prof_id = str(uuid.uuid4())
                conn.execute("""
                INSERT INTO farmer_profiles (id, user_id, name, mobile, farm_size, primary_crop, location, preferred_language, notify_weather, notify_spray, notify_schemes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    prof_id,
                    user_id,
                    profile_data.get("name", "Farmer"),
                    profile_data.get("mobile", "9876543210"),
                    profile_data.get("farm_size", 2.0),
                    profile_data.get("primary_crop", "Tomato"),
                    profile_data.get("location", "Tamil Nadu"),
                    profile_data.get("preferred_language", "en"),
                    1 if nw is None or nw == 1 else 0,
                    1 if ns is None or ns == 1 else 0,
                    1 if nc is None or nc == 1 else 0,
                    now
                ))
        return get_or_create_profile(user_id)
    finally:
        conn.close()

# --- Crop Analysis History Helpers ---
def save_crop_analysis(record: Dict[str, Any]) -> str:
    conn = get_connection()
    rec_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            conn.execute("""
            INSERT INTO crop_analyses (
                id, user_id, crop_type, image_path, detected_disease, confidence,
                severity, risk_level, quality_status, weather_context, is_inconclusive, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rec_id,
                record.get("user_id"),
                record.get("crop_type", "Unknown"),
                record.get("image_path"),
                record.get("detected_disease", "Unknown"),
                float(record.get("confidence", 0.0)),
                record.get("severity", "Not determined"),
                record.get("risk_level", "Not determined"),
                record.get("quality_status", "Passed"),
                record.get("weather_context"),
                1 if record.get("is_inconclusive") else 0,
                now
            ))
        return rec_id
    finally:
        conn.close()

def get_recent_crop_analyses(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM crop_analyses ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def get_crop_stats(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Computes genuine real-time KPI metrics from actual database records."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if user_id:
            cur.execute("SELECT detected_disease, confidence, quality_status, is_inconclusive FROM crop_analyses WHERE user_id = ?", (user_id,))
        else:
            cur.execute("SELECT detected_disease, confidence, quality_status, is_inconclusive FROM crop_analyses")
        rows = cur.fetchall()
        total_scans = len(rows)
        healthy_count = sum(1 for r in rows if "healthy" in (r["detected_disease"] or "").lower())
        inconclusive_count = sum(1 for r in rows if bool(r["is_inconclusive"]) or (r["quality_status"] and r["quality_status"] != "Passed") or float(r["confidence"] or 0) < 0.60)
        condition_alerts = sum(1 for r in rows if "healthy" not in (r["detected_disease"] or "").lower() and not bool(r["is_inconclusive"]) and float(r["confidence"] or 0) >= 0.60)
        return {
            "total_scans": total_scans,
            "healthy_count": healthy_count,
            "condition_alerts": condition_alerts,
            "inconclusive_count": inconclusive_count
        }
    finally:
        conn.close()

def delete_crop_analysis(record_id: str) -> bool:
    """Deletes a crop analysis record from local database by ID and cleans up local thumbnail if applicable."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT image_path FROM crop_analyses WHERE id = ?", (record_id,))
        row = cur.fetchone()
        image_path = row["image_path"] if row and "image_path" in row.keys() else None

        with conn:
            cur.execute("DELETE FROM crop_analyses WHERE id = ?", (record_id,))
            deleted = cur.rowcount > 0

        # Safely remove local thumbnail from uploads directory if present
        if deleted and image_path and not str(image_path).startswith("http"):
            try:
                local_file = Path(image_path)
                if not local_file.is_absolute():
                    local_file = Path(__file__).resolve().parent.parent / image_path
                if local_file.exists() and local_file.is_file():
                    local_file.unlink()
            except Exception as e:
                logger.debug(f"Thumbnail cleanup notice for {image_path}: {e}")

        return deleted
    finally:
        conn.close()

# --- Chat History Helpers ---
def save_chat_message(role: str, message: str, user_id: Optional[str] = None) -> str:
    """Saves a user or AI chat message into local SQLite chat_history."""
    conn = get_connection()
    rec_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            conn.execute("""
            INSERT INTO chat_history (id, user_id, role, message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (rec_id, user_id, role, message, now))
        return rec_id
    finally:
        conn.close()

def get_recent_chat_history(user_id: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Retrieves recent chat history records from local SQLite."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if user_id:
            cur.execute("SELECT * FROM chat_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?", (user_id, limit, offset))
        else:
            cur.execute("SELECT * FROM chat_history ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

# Backward-compatible alias for assistant router
get_chat_history = get_recent_chat_history

def clear_chat_history(user_id: Optional[str] = None) -> bool:
    """Clears chat messages from local SQLite."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            if user_id:
                cur.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
            else:
                cur.execute("DELETE FROM chat_history")
            return True
    finally:
        conn.close()



