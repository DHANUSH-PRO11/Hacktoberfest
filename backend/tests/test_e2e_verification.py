"""
Comprehensive End-to-End Verification Test Suite for AgroNex Agricultural Copilot
Covers all 10 Scenarios:
1. Workflow manifest
2. Text chat
3. Image diagnosis
4. Weather
5. Subsidies
6. Voice pipeline
7. Agricultural safety rules
8. Persistence
9. Agent trace
10. Security and resilience
"""

import io
import json
import os
import sys
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
from PIL import Image, ImageFilter
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app
from services.agent.agronex_agent import AgroNexAgent
from services.ai.disease_detector import DiseaseDetector
from services.weather_service import WeatherService
from config import local_db


def create_in_memory_leaf(width=224, height=224, blur=False, green=True) -> bytes:
    """Generates synthetic in-memory image bytes for controlled testing."""
    if green:
        # Create patterned green foliage
        arr = np.zeros((height, width, 3), dtype=np.uint8)
        arr[:, :, 0] = 30  # Red
        arr[:, :, 1] = 160  # High green
        arr[:, :, 2] = 40  # Blue
    else:
        # Grey non-leaf image
        arr = np.full((height, width, 3), 128, dtype=np.uint8)

    img = Image.fromarray(arr, mode="RGB")
    if blur:
        img = img.filter(ImageFilter.BoxBlur(15))

    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def create_in_memory_wav(duration_sec=1.0, sample_rate=16000) -> bytes:
    """Generates synthetic in-memory WAV audio bytes for controlled testing."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        n_frames = int(duration_sec * sample_rate)
        wav_file.writeframes(b"\x00\x00" * n_frames)
    return buf.getvalue()


class TestAgroNexE2EVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.agent = AgroNexAgent()
        cls.test_png_path = backend_dir / "test_tomato.png"

        # Locate or generate synthetic test WAV file so tests run reliably in CI
        candidate_paths = [
            backend_dir / "test_output.wav",
            backend_dir.parent / "test_output.wav"
        ]
        existing_wav = next((p for p in candidate_paths if p.exists()), None)
        if existing_wav:
            cls.test_wav_path = existing_wav
            cls._created_test_wav = False
        else:
            cls.test_wav_path = backend_dir / "test_output.wav"
            cls.test_wav_path.write_bytes(create_in_memory_wav())
            cls._created_test_wav = True

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_created_test_wav", False) and cls.test_wav_path and cls.test_wav_path.exists():
            try:
                cls.test_wav_path.unlink()
            except OSError:
                pass

    # =========================================================================
    # SCENARIO 1: Workflow Manifest
    # =========================================================================
    def test_01_workflow_manifest_structure_and_nodes(self):
        """Verifies GET /api/agent/workflow returns valid JSON and accurately reflects implemented nodes."""
        res = self.client.get("/api/agent/workflow")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "application/json")
        data = res.json()

        self.assertEqual(data["workflow_id"], "agronex-farming-copilot")
        self.assertEqual(data["version"], "1.0.0")
        self.assertIn("nodes", data)
        self.assertIn("safety_boundaries", data)
        self.assertIn("languages", data)

        manifest_node_ids = {node["id"] for node in data["nodes"]}
        expected_nodes = {
            "input_ingestion",
            "intent_routing",
            "disease_detection",
            "weather_lookup",
            "schemes_provider",
            "context_assembly",
            "agricultural_reasoning",
            "voice_synthesis",
            "persistence"
        }
        self.assertTrue(expected_nodes.issubset(manifest_node_ids), f"Missing nodes: {expected_nodes - manifest_node_ids}")

        # Cross-reference with .agentfoundry/workflow.json
        af_manifest_path = backend_dir.parent / ".agentfoundry" / "workflow.json"
        self.assertTrue(af_manifest_path.exists())
        with open(af_manifest_path, "r", encoding="utf-8") as f:
            af_json = json.load(f)
        af_node_ids = {n["id"] for n in af_json["nodes"]}
        self.assertTrue(expected_nodes.issubset(af_node_ids))

    # =========================================================================
    # SCENARIO 2: Text Chat
    # =========================================================================
    def test_02_text_chat_english_and_tamil(self):
        """Tests POST /api/agent/chat with English and Tamil queries, context handling, and error handling."""
        # English query
        en_res = self.client.post("/api/agent/chat", json={
            "message": "What is the optimal spacing and irrigation for tomato plants?",
            "language": "en"
        })
        self.assertEqual(en_res.status_code, 200)
        en_body = en_res.json()
        self.assertTrue(en_body["success"])
        self.assertEqual(en_body["language"], "en")
        self.assertGreater(len(en_body["recommendation"]), 20)

        # Tamil query
        ta_res = self.client.post("/api/agent/chat", json={
            "message": "தக்காளி செடிக்கு நீர் பாசனம் எவ்வாறு செய்ய வேண்டும்?",
            "language": "ta"
        })
        self.assertEqual(ta_res.status_code, 200)
        ta_body = ta_res.json()
        self.assertTrue(ta_body["success"])
        self.assertEqual(ta_body["language"], "ta")
        self.assertGreater(len(ta_body["recommendation"]), 20)

        # Diagnostic Context handling
        ctx_res = self.client.post("/api/agent/chat", json={
            "message": "Should I spray today?",
            "crop_hint": "Tomato",
            "language": "en",
            "context": {
                "crop": "Tomato",
                "condition": "Late blight",
                "confidence": 91.5,
                "status": "High confidence",
                "quality_status": "Passed"
            }
        })
        self.assertEqual(ctx_res.status_code, 200)
        ctx_body = ctx_res.json()
        self.assertTrue(ctx_body["success"])
        self.assertIsNotNone(ctx_body["crop_prediction"])
        self.assertEqual(ctx_body["crop_prediction"]["crop"], "Tomato")
        self.assertEqual(ctx_body["crop_prediction"]["condition"], "Late blight")
        self.assertIn("spray_advisory", ctx_body)

        # Malformed request validation (missing required 'message')
        bad_res = self.client.post("/api/agent/chat", json={"invalid_field": 123})
        self.assertEqual(bad_res.status_code, 422)

    # =========================================================================
    # SCENARIO 3: Image Diagnosis
    # =========================================================================
    def test_03_image_diagnosis_scenarios(self):
        """Tests POST /api/agent/run with valid image, non-image, blurry image, corrupt input, and uncertainty gate."""
        # 1. Valid leaf image (test_tomato.png)
        with open(self.test_png_path, "rb") as f:
            valid_bytes = f.read()

        valid_res = self.client.post(
            "/api/agent/run",
            files={"image": ("test_tomato.png", valid_bytes, "image/png")},
            data={"query": "Identify this leaf disease"}
        )
        self.assertEqual(valid_res.status_code, 200)
        valid_body = valid_res.json()
        self.assertTrue(valid_body["success"])
        self.assertIsNotNone(valid_body["crop_prediction"])
        pred = valid_body["crop_prediction"]
        self.assertIn("crop", pred)
        self.assertIn("condition", pred)
        self.assertIn("confidence", pred)
        self.assertEqual(pred["quality_status"], "Passed")
        self.assertIn("efficientnet_v2_disease_detector", valid_body["tools_called"])

        # 2. Non-image file (text file)
        text_bytes = b"This is plain text and not a leaf image."
        bad_file_res = self.client.post(
            "/api/agent/run",
            files={"image": ("sample.txt", text_bytes, "text/plain")}
        )
        self.assertEqual(bad_file_res.status_code, 400)
        self.assertIn("not an image", bad_file_res.json()["detail"].lower())

        # 3. Blurry image check
        blurry_bytes = create_in_memory_leaf(224, 224, blur=True, green=True)
        blur_res = self.client.post(
            "/api/agent/run",
            files={"image": ("blurry_leaf.jpg", blurry_bytes, "image/jpeg")}
        )
        self.assertEqual(blur_res.status_code, 200)
        blur_body = blur_res.json()
        self.assertTrue(blur_body["requires_expert_confirmation"])
        self.assertIn("Warning: Mild Blur", blur_body["crop_prediction"]["quality_status"])

        # 4. Corrupt binary disguised as image
        corrupt_bytes = b"CorruptBinaryDataNotAJPEGFile"
        corrupt_res = self.client.post(
            "/api/agent/run",
            files={"image": ("fake.jpg", corrupt_bytes, "image/jpeg")}
        )
        self.assertEqual(corrupt_res.status_code, 400)
        self.assertIn("not a valid or supported image", corrupt_res.json()["detail"].lower())

        # 5. Uncertainty Gate: Non-leaf grey image
        grey_bytes = create_in_memory_leaf(224, 224, blur=False, green=False)
        grey_res = self.client.post(
            "/api/agent/run",
            files={"image": ("grey_wall.jpg", grey_bytes, "image/jpeg")}
        )
        self.assertEqual(grey_res.status_code, 200)
        grey_body = grey_res.json()
        # Uncertainty rule triggers either low confidence (<60%) or low foliage
        self.assertTrue(
            grey_body["requires_expert_confirmation"]
            or grey_body["crop_prediction"]["status"] == "Uncertain"
            or grey_body["crop_prediction"]["quality_status"] != "Passed"
        )

    # =========================================================================
    # SCENARIO 4: Weather
    # =========================================================================
    def test_04_weather_scenarios(self):
        """Tests weather forecast endpoint with valid, missing, and invalid coordinates."""
        # 1. Valid coordinates (Coimbatore agricultural hub)
        res_valid = self.client.get("/api/weather/forecast?lat=11.0168&lon=76.9558")
        self.assertEqual(res_valid.status_code, 200)
        w_data = res_valid.json()
        self.assertTrue(w_data["success"])
        self.assertIn("current", w_data)
        self.assertIn("temperature", w_data["current"])
        self.assertIn("humidity", w_data["current"])
        self.assertIn("wind_speed", w_data["current"])
        self.assertIn("forecast", w_data)
        self.assertIn("hourly", w_data)

        # 2. Missing coordinates in /api/weather/forecast (FastAPI validation)
        res_missing = self.client.get("/api/weather/forecast")
        self.assertEqual(res_missing.status_code, 422)

        # 3. Missing coordinates in /api/agent/run (Agent defaults to regional coordinates)
        agent_weather_res = self.agent.run(query="What is the weather today?")
        self.assertTrue(agent_weather_res["success"])
        self.assertIn("open_meteo_weather_service", agent_weather_res["tools_called"])
        self.assertIsNotNone(agent_weather_res["weather_context"])

        # 4. Invalid coordinates in WeatherService (Gracefully rejected with validation error)
        ws = WeatherService()
        bad_coords_result = ws.get_weather(lat=999.0, lon=999.0)
        self.assertFalse(bad_coords_result["success"])
        self.assertIn("Invalid coordinates", bad_coords_result["error"])

    # =========================================================================
    # SCENARIO 5: Subsidies
    # =========================================================================
    def test_05_schemes_and_subsidies(self):
        """Verifies government schemes, filters, and authenticity of sources."""
        res = self.client.get("/api/schemes/")
        self.assertEqual(res.status_code, 200)
        schemes = res.json()
        self.assertGreaterEqual(len(schemes), 4)

        # Verify key government programs exist with valid official portals
        scheme_names = [s["name"] for s in schemes]
        self.assertTrue(any("PM-KISAN" in name for name in scheme_names))
        self.assertTrue(any("PMFBY" in name for name in scheme_names))
        self.assertTrue(any("KCC" in name or "Kisan Credit" in name for name in scheme_names))

        for scheme in schemes:
            self.assertTrue(scheme["source"].startswith("https://"), f"Insecure or invalid URL: {scheme['source']}")
            self.assertTrue(
                "gov.in" in scheme["source"],
                f"Source URL is not an official government portal: {scheme['source']}"
            )
            # Check bilingual support
            self.assertIn("name_ta", scheme)
            self.assertIn("benefits_ta", scheme)

        # Filter by search term
        search_res = self.client.get("/api/schemes/?search=drip")
        self.assertEqual(search_res.status_code, 200)
        filtered = search_res.json()
        self.assertGreaterEqual(len(filtered), 1)
        self.assertTrue("micro irrigation" in filtered[0]["category"].lower() or "irrigation" in filtered[0]["benefits"].lower())

    # =========================================================================
    # SCENARIO 6: Voice Pipeline
    # =========================================================================
    def test_06_voice_pipeline_and_quota_resilience(self):
        """Tests audio ingestion, STT/TTS routing, and graceful behavior under quota or network constraints."""
        if not self.test_wav_path or not self.test_wav_path.exists():
            self.test_wav_path = backend_dir / "test_output.wav"
            self.test_wav_path.write_bytes(create_in_memory_wav())

        self.assertTrue(self.test_wav_path.exists())
        with open(self.test_wav_path, "rb") as f:
            audio_bytes = f.read()

        # Ingestion via /api/agent/run
        res = self.client.post(
            "/api/agent/run",
            files={"audio": ("test_voice.wav", audio_bytes, "audio/wav")},
            data={"query": "Farm status inquiry", "language": "en"}
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])

        # Voice chat endpoint
        voice_res = self.client.post(
            "/api/assistant/voice",
            files={"file": ("recording.wav", audio_bytes, "audio/wav")},
            data={"language": "en"}
        )
        self.assertEqual(voice_res.status_code, 200)
        voice_body = voice_res.json()
        self.assertIn("reply", voice_body)
        self.assertIn("transcription", voice_body)

        # Test simulated end-to-end voice round-trip when Sarvam client responds
        mock_assistant = MagicMock()
        mock_assistant.speech_to_text.return_value = ("ta-IN", "தக்காளி இலை கருகுகிறது")
        mock_assistant.answer.return_value = "பாதிக்கப்பட்ட இலைகளை அகற்றவும்."
        mock_assistant.text_to_speech.return_value = "UklGRi4AAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA="

        mock_agent = AgroNexAgent(assistant=mock_assistant)
        agent_out = mock_agent.run(
            audio_bytes=audio_bytes,
            audio_filename="voice.wav",
            language="ta"
        )
        self.assertTrue(agent_out["success"])
        self.assertIn("sarvam_speech_to_text", agent_out["tools_called"])
        self.assertEqual(agent_out["transcription"], "தக்காளி இலை கருகுகிறது")
        self.assertIsNotNone(agent_out["audio_base64"])

    # =========================================================================
    # SCENARIO 7: Agricultural Safety Rules
    # =========================================================================
    def test_07_agricultural_safety_rules(self):
        """Validates spray window rules (rain > 60%, precip > 2mm, wind > 25km/h) and uncertainty triggers (< 60%)."""
        mock_ws = MagicMock()

        # 1. Rain probability > 60% -> DO NOT SPRAY
        mock_ws.get_weather.return_value = {
            "success": True,
            "current": {"precipitation": 0.0, "wind_speed": 10.0},
            "forecast": [{"precipitation_probability_mean": 75}],
            "hourly": [{"precipitation_probability": 75}]
        }
        agent_rain = AgroNexAgent(weather_service=mock_ws)
        res_rain = agent_rain.run(latitude=11.0, longitude=77.0)
        self.assertIn("DO NOT SPRAY", res_rain["spray_advisory"])
        self.assertIn("High chance of rainfall (>60%)", res_rain["spray_advisory"])

        # 2. Precipitation > 2 mm -> DO NOT SPRAY
        mock_ws.get_weather.return_value = {
            "success": True,
            "current": {"precipitation": 3.5, "wind_speed": 8.0},
            "forecast": [{"precipitation_probability_mean": 20}],
            "hourly": [{"precipitation_probability": 20}]
        }
        agent_precip = AgroNexAgent(weather_service=mock_ws)
        res_precip = agent_precip.run(latitude=11.0, longitude=77.0)
        self.assertIn("DO NOT SPRAY", res_precip["spray_advisory"])

        # 3. Wind speed > 25 km/h -> CAUTION SPRAYING
        mock_ws.get_weather.return_value = {
            "success": True,
            "current": {"precipitation": 0.0, "wind_speed": 32.0},
            "forecast": [{"precipitation_probability_mean": 10}],
            "hourly": [{"precipitation_probability": 10}]
        }
        agent_wind = AgroNexAgent(weather_service=mock_ws)
        res_wind = agent_wind.run(latitude=11.0, longitude=77.0)
        self.assertIn("CAUTION SPRAYING", res_wind["spray_advisory"])
        self.assertIn("High winds (>25 km/h)", res_wind["spray_advisory"])

        # 4. Safe weather -> SAFE SPRAY WINDOW
        mock_ws.get_weather.return_value = {
            "success": True,
            "current": {"precipitation": 0.0, "wind_speed": 12.0},
            "forecast": [{"precipitation_probability_mean": 15}],
            "hourly": [{"precipitation_probability": 15}]
        }
        agent_safe = AgroNexAgent(weather_service=mock_ws)
        res_safe = agent_safe.run(latitude=11.0, longitude=77.0)
        self.assertIn("SAFE SPRAY WINDOW", res_safe["spray_advisory"])

        # 5. Low-confidence diagnosis (<60%) -> requires_expert_confirmation = True
        mock_detector = MagicMock()
        mock_detector.predict.return_value = {
            "crop": "Tomato",
            "condition": "Early blight",
            "confidence": 0.42,
            "status": "Uncertain",
            "quality_status": "Passed"
        }
        agent_uncert = AgroNexAgent(detector=mock_detector)
        res_uncert = agent_uncert.run(image_bytes=b"fake_image_bytes")
        self.assertTrue(res_uncert["requires_expert_confirmation"])

        # 6. Quality degraded image -> requires_expert_confirmation = True regardless of confidence
        mock_detector.predict.return_value = {
            "crop": "Tomato",
            "condition": "Healthy",
            "confidence": 0.95,
            "status": "High confidence",
            "quality_status": "Warning: Low Light"
        }
        agent_qual = AgroNexAgent(detector=mock_detector)
        res_qual = agent_qual.run(image_bytes=b"fake_image_bytes")
        self.assertTrue(res_qual["requires_expert_confirmation"])

    # =========================================================================
    # SCENARIO 8: Persistence
    # =========================================================================
    def test_08_persistence_supabase_and_sqlite_fallback(self):
        """Verifies Supabase when configured, SQLite fallback, and accurate reporting."""
        # 1. Local SQLite insertion and retrieval
        test_msg = f"Soil moisture query {time.time()}"
        msg_id = local_db.save_chat_message("user", test_msg)
        self.assertIsNotNone(msg_id)
        history = local_db.get_recent_chat_history(limit=5)
        self.assertTrue(any(test_msg in h["message"] for h in history))

        crop_id = local_db.save_crop_analysis({
            "crop_type": "Tomato",
            "detected_disease": "Septoria leaf spot",
            "confidence": 0.88,
            "severity": "Moderate",
            "risk_level": "Medium"
        })
        self.assertIsNotNone(crop_id)
        analyses = local_db.get_recent_crop_analyses(limit=5)
        self.assertTrue(any(a["id"] == crop_id for a in analyses))

        # 2. Agent run with offline/None Supabase (should cleanly report sqlite_fallback)
        agent_res = self.agent.run(
            query="Verify local persistence",
            db_client=None
        )
        self.assertTrue(agent_res["success"])
        pers_node = next(n for n in agent_res["execution_trace"] if n["node"] == "persistence")
        self.assertEqual(pers_node["status"], "offline_fallback")
        self.assertEqual(pers_node["details"]["storage_backend"], "sqlite_fallback")
        self.assertEqual(agent_res["evidence_report"]["storage_backend"], "sqlite_fallback")

        # 3. Agent run with Supabase error (mock failure)
        mock_db = MagicMock()
        mock_db.table.side_effect = Exception("Supabase connection refused")
        agent_failover = self.agent.run(
            query="Verify Supabase failover",
            db_client=mock_db
        )
        self.assertTrue(agent_failover["success"])
        failover_node = next(n for n in agent_failover["execution_trace"] if n["node"] == "persistence")
        self.assertEqual(failover_node["status"], "offline_fallback")
        self.assertEqual(failover_node["details"]["storage_backend"], "sqlite_fallback")
        self.assertIn("Supabase connection refused", failover_node["details"]["error"])

    # =========================================================================
    # SCENARIO 9: Agent Trace
    # =========================================================================
    def test_09_agent_execution_trace_integrity(self):
        """Verifies dynamic, non-fabricated execution trace with per-node duration and details."""
        with open(self.test_png_path, "rb") as f:
            img_bytes = f.read()

        result = self.agent.run(
            query="Can I spray today for this disease?",
            image_bytes=img_bytes,
            image_filename="test_tomato.png",
            latitude=11.0168,
            longitude=76.9558,
            language="en"
        )
        self.assertTrue(result["success"])
        trace = result["execution_trace"]
        self.assertIsInstance(trace, list)
        self.assertGreaterEqual(len(trace), 6)

        executed_node_names = [n["node"] for n in trace]
        self.assertIn("input_ingestion", executed_node_names)
        self.assertIn("intent_routing", executed_node_names)
        self.assertIn("disease_detection", executed_node_names)
        self.assertIn("weather_lookup", executed_node_names)
        self.assertIn("context_assembly", executed_node_names)
        self.assertIn("agricultural_reasoning", executed_node_names)
        self.assertIn("voice_synthesis", executed_node_names)
        self.assertIn("persistence", executed_node_names)

        for step in trace:
            self.assertIn("node", step)
            self.assertIn("status", step)
            self.assertIn("duration_ms", step)
            self.assertIsInstance(step["duration_ms"], (int, float))
            self.assertIn("timestamp", step)
            self.assertIn("details", step)
            self.assertIsInstance(step["details"], dict)

        self.assertGreater(result["total_latency_ms"], 0.0)

    # =========================================================================
    # SCENARIO 10: Security and Resilience
    # =========================================================================
    def test_10_security_and_resilience(self):
        """Tests missing credentials, oversized uploads, provider timeout simulation, and unauthorized access."""
        # 1. Oversized image upload (>10 MB)
        oversized_image = b"0" * (11 * 1024 * 1024)
        res_large_img = self.client.post(
            "/api/agent/run",
            files={"image": ("large.jpg", oversized_image, "image/jpeg")}
        )
        self.assertEqual(res_large_img.status_code, 413)

        # 2. Oversized image on /api/crops/analyze (>10 MB)
        res_crops_large = self.client.post(
            "/api/crops/analyze",
            files={"file": ("large.jpg", oversized_image, "image/jpeg")}
        )
        self.assertEqual(res_crops_large.status_code, 413)

        # 3. Oversized audio on /api/assistant/voice (>10 MB)
        oversized_audio = b"0" * (11 * 1024 * 1024)
        res_large_audio = self.client.post(
            "/api/assistant/voice",
            files={"file": ("large.wav", oversized_audio, "audio/wav")}
        )
        self.assertEqual(res_large_audio.status_code, 413)

        # 4. Unauthorized access to protected route
        unauth_res = self.client.get("/api/auth/me")
        self.assertEqual(unauth_res.status_code, 401)

        # 5. Invalid token to protected route
        bad_token_res = self.client.get("/api/auth/me", headers={"Authorization": "Bearer InvalidTokenXYZ"})
        self.assertEqual(bad_token_res.status_code, 401)

        # 6. Provider timeout simulation (Service reports failure without inventing fake data)
        ws = WeatherService()
        ws._cache.clear()
        with patch.object(ws, "_fetch_open_meteo", side_effect=TimeoutError("Connection timed out")):
            timeout_res = ws.get_weather(11.0, 77.0)
            self.assertFalse(timeout_res["success"])
            self.assertFalse(timeout_res["data_available"])
            self.assertIn("error", timeout_res)


if __name__ == "__main__":
    unittest.main()
