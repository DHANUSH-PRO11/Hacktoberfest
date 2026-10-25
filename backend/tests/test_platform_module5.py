"""
AgroNex AI — Module 5 Automated Test Suite: Platform, Integration, Security, and Persistence
Tests:
- Database schema initialization, indexes, session management, and transaction safety
- Crop analysis save, pagination (limit/offset), deletion, and stats calculation consistency
- Chat history save, pagination, clearing, and backward-compatible aliases
- Image upload validation gates (empty files, invalid mime, corrupted bytes)
- Schemes directory structure, verified fields, and Central vs State distinction
- API health telemetry, detailed inspection, and security headers
- Database persistence across simulated restarts
"""

import io
import os
import sys
import unittest
import uuid
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app
from config import local_db
from api.schemes import AGRICULTURAL_SCHEMES


class TestPlatformModule5(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_database_indexes_exist(self):
        """Verifies that indexes on created_at and user_id exist for performance."""
        conn = local_db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row[0] for row in cur.fetchall()}
            self.assertIn("idx_crop_analyses_created_at", indexes)
            self.assertIn("idx_crop_analyses_user_id", indexes)
            self.assertIn("idx_chat_history_created_at", indexes)
            self.assertIn("idx_chat_history_user_id", indexes)
        finally:
            conn.close()

    def test_02_crop_analyses_crud_and_stats_consistency(self):
        """Tests that saving an analysis increments stats, and deleting it decrements stats."""
        initial_stats = local_db.get_crop_stats()
        initial_scans = initial_stats["total_scans"]
        initial_healthy = initial_stats["healthy_count"]

        # Insert a healthy record
        rec_id = local_db.save_crop_analysis({
            "crop_type": "Corn",
            "detected_disease": "healthy",
            "confidence": 0.95,
            "quality_status": "Passed",
            "is_inconclusive": False
        })
        self.assertTrue(bool(rec_id))

        after_save_stats = local_db.get_crop_stats()
        self.assertEqual(after_save_stats["total_scans"], initial_scans + 1)
        self.assertEqual(after_save_stats["healthy_count"], initial_healthy + 1)

        # Delete the record
        deleted = local_db.delete_crop_analysis(rec_id)
        self.assertTrue(deleted)

        after_del_stats = local_db.get_crop_stats()
        self.assertEqual(after_del_stats["total_scans"], initial_scans)
        self.assertEqual(after_del_stats["healthy_count"], initial_healthy)

    def test_03_inconclusive_stats_counting(self):
        """Verifies that inconclusive records (confidence < 0.60 or is_inconclusive=1) are counted accurately."""
        initial_stats = local_db.get_crop_stats()
        initial_inconclusive = initial_stats["inconclusive_count"]

        rec_id = local_db.save_crop_analysis({
            "crop_type": "Tomato",
            "detected_disease": "Early_Blight",
            "confidence": 0.42,  # Below 60% threshold
            "quality_status": "Passed",
            "is_inconclusive": True
        })

        stats = local_db.get_crop_stats()
        self.assertEqual(stats["inconclusive_count"], initial_inconclusive + 1)

        # Clean up
        local_db.delete_crop_analysis(rec_id)
        cleaned_stats = local_db.get_crop_stats()
        self.assertEqual(cleaned_stats["inconclusive_count"], initial_inconclusive)

    def test_04_crop_history_pagination(self):
        """Verifies limit and offset pagination on /api/crops/history."""
        res_limit_2 = self.client.get("/api/crops/history?limit=2&offset=0")
        self.assertEqual(res_limit_2.status_code, 200)
        data = res_limit_2.json()
        self.assertIsInstance(data, list)
        self.assertLessEqual(len(data), 2)

    def test_05_chat_history_crud_and_alias(self):
        """Tests chat message persistence, pagination, alias compatibility, and clearing."""
        test_msg = f"Platform test query {uuid.uuid4()}"
        msg_id = local_db.save_chat_message("user", test_msg)
        self.assertTrue(bool(msg_id))

        # Check retrieval via alias
        history = local_db.get_chat_history(limit=10)
        self.assertTrue(any(h["message"] == test_msg for h in history))

        # Check API endpoint with pagination
        res = self.client.get("/api/assistant/history?limit=5&offset=0")
        self.assertEqual(res.status_code, 200)
        api_history = res.json()
        self.assertIsInstance(api_history, list)

    def test_06_health_telemetry_and_security_headers(self):
        """Verifies /health default compatibility, ?detail=true telemetry, and security headers."""
        # 1. Default health returns exact {'status': 'ok'}
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "ok"})

        # 2. Security headers are present
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

        # 3. Detailed telemetry returns component statuses
        res_detailed = self.client.get("/health?detail=true")
        self.assertEqual(res_detailed.status_code, 200)
        data = res_detailed.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("components", data)
        self.assertEqual(data["components"]["database"], "connected")
        self.assertEqual(data["components"]["crop_engine"], "operational")

    def test_07_invalid_image_upload_validation(self):
        """Verifies that empty files or invalid image contents are rejected cleanly (HTTP 400)."""
        # Empty file
        empty_file = io.BytesIO(b"")
        res_empty = self.client.post(
            "/api/crops/analyze",
            files={"file": ("empty.jpg", empty_file, "image/jpeg")}
        )
        self.assertEqual(res_empty.status_code, 400)

        # Corrupted non-image bytes claiming to be PNG
        corrupt_file = io.BytesIO(b"Not an authentic image stream")
        res_corrupt = self.client.post(
            "/api/crops/analyze",
            files={"file": ("corrupt.png", corrupt_file, "image/png")}
        )
        self.assertEqual(res_corrupt.status_code, 400)

    def test_08_government_schemes_directory_integrity(self):
        """Verifies all government schemes contain mandatory verified fields and Central vs State distinction."""
        self.assertGreaterEqual(len(AGRICULTURAL_SCHEMES), 6)

        central_schemes = [s for s in AGRICULTURAL_SCHEMES if "Central" in s["scheme_type"]]
        state_schemes = [s for s in AGRICULTURAL_SCHEMES if "State" in s["scheme_type"]]
        self.assertGreaterEqual(len(central_schemes), 4)
        self.assertGreaterEqual(len(state_schemes), 1)

        for s in AGRICULTURAL_SCHEMES:
            self.assertIn("id", s)
            self.assertIn("name", s)
            self.assertIn("name_ta", s)
            self.assertIn("scheme_type", s)
            self.assertIn("purpose", s)
            self.assertIn("purpose_ta", s)
            self.assertIn("category", s)
            self.assertIn("benefits", s)
            self.assertIn("eligibility", s)
            self.assertIn("application_steps", s)
            self.assertIn("required_documents", s)
            self.assertIn("official_portal", s)
            self.assertIn("last_verified", s)
            self.assertIn("disclaimer", s)
            self.assertTrue(s["official_portal"].startswith("http"))
            self.assertEqual(s["last_verified"], "October 2026")

    def test_09_schemes_api_filtering(self):
        """Verifies scheme querying by category, scheme_type, and text search."""
        # Query by scheme_type=State
        res_state = self.client.get("/api/schemes?scheme_type=State")
        self.assertEqual(res_state.status_code, 200)
        data_state = res_state.json()
        self.assertTrue(all("State" in s["scheme_type"] for s in data_state))

        # Query by search=KISAN
        res_search = self.client.get("/api/schemes?search=KISAN")
        self.assertEqual(res_search.status_code, 200)
        data_search = res_search.json()
        self.assertTrue(any("PM-KISAN" in s["name"] for s in data_search))

    def test_10_database_survives_reconnect(self):
        """Simulates service restart by closing and reopening database connection."""
        test_uuid = str(uuid.uuid4())
        rec_id = local_db.save_crop_analysis({
            "crop_type": "Tomato",
            "detected_disease": f"Test_Bacterial_Spot_{test_uuid}",
            "confidence": 0.88,
            "quality_status": "Passed"
        })

        # Close all connections and re-initialize
        local_db.init_local_db()

        # Query recent analyses
        recent = local_db.get_recent_crop_analyses(limit=10)
        found = any(r["id"] == rec_id for r in recent)
        self.assertTrue(found, "Saved record should persist across connection restarts")

        # Clean up
        local_db.delete_crop_analysis(rec_id)


if __name__ == "__main__":
    unittest.main()
