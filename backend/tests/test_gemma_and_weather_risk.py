"""
Unit & Integration Tests for Gemma 4 Multimodal Assistant, Open-Meteo Weather Risk Intelligence,
and Agricultural Pathology Safety Guardrails.
"""

import io
import sys
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app
from services.ai.gemma_assistant import GemmaMultimodalAssistant
from services.weather_service import WeatherService


client = TestClient(app)

def create_synthetic_image(format="JPEG", size=(224, 224), green=True) -> bytes:
    """Generates synthetic in-memory image bytes in specified format."""
    arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    if green:
        arr[:, :, 0] = 35   # Red
        arr[:, :, 1] = 165  # High Green foliage
        arr[:, :, 2] = 45   # Blue
    else:
        arr[:, :, :] = 128  # Gray non-leaf

    img = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


class TestGemmaAndWeatherRisk(unittest.TestCase):

    def setUp(self):
        self.gemma = GemmaMultimodalAssistant()
        self.weather = WeatherService()

    def test_gemma_structured_explanation_english(self):
        """Test Gemma 4 generates complete structured explanation in English."""
        context = {
            "crop": "Tomato",
            "condition": "Early_blight",
            "confidence": 0.92,
            "quality_status": "Passed"
        }
        weather_ctx = {
            "current": {"temperature": 27.0, "humidity": 82.0},
            "forecast": [{"precipitation_probability_mean": 65}]
        }
        res = self.gemma.explain_leaf_symptoms(
            crop_context=context,
            weather_context=weather_ctx,
            language="en"
        )
        self.assertIn("observations", res)
        self.assertIn("possible_causes", res)
        self.assertIn("recommended_next_steps", res)
        self.assertIn("weather_risk_factor", res)
        self.assertIn("why_recommendations", res)
        self.assertIn("uncertainty_warnings", res)
        self.assertIn("expert_consultation_triggers", res)
        self.assertTrue(len(res["recommended_next_steps"]) >= 3)
        # Ensure uncertainty warning explicitly distinguishes prediction from lab diagnosis
        self.assertTrue("certified" in res["uncertainty_warnings"].lower() or "diagnosis" in res["uncertainty_warnings"].lower())

    def test_gemma_structured_explanation_tamil(self):
        """Test Gemma 4 generates authentic Tamil structured response."""
        context = {
            "crop": "Tomato",
            "condition": "Late_blight",
            "confidence": 0.88,
            "quality_status": "Passed"
        }
        res = self.gemma.explain_leaf_symptoms(
            crop_context=context,
            language="ta"
        )
        self.assertEqual(res["language"], "ta")
        self.assertIn("observations", res)
        self.assertIn("recommended_next_steps", res)
        self.assertTrue(any("இலை" in step for step in res["recommended_next_steps"]))

    def test_gemma_healthy_leaf_reasoning(self):
        """Test Gemma 4 correctly identifies healthy leaf conditions without alarms."""
        context = {
            "crop": "Tomato",
            "condition": "healthy",
            "confidence": 0.95,
            "quality_status": "Passed"
        }
        res = self.gemma.explain_leaf_symptoms(crop_context=context, language="en")
        self.assertIn("chlorophyll", res["observations"].lower())
        self.assertIn("healthy", res["possible_causes"].lower())

    def test_weather_environmental_risk_assessment(self):
        """Test Open-Meteo environmental risk synthesis and disclaimer."""
        weather_mock = {
            "current": {"temperature": 26.0, "humidity": 88.0, "wind_speed": 14.0, "precipitation": 2.5},
            "hourly": [{"precipitation_probability": 70}]
        }
        risk = self.weather.get_environmental_risk(
            weather_data=weather_mock,
            crop="Tomato",
            condition="Late_blight",
            language="en"
        )
        self.assertEqual(risk["risk_level"], "High")
        self.assertEqual(risk["relative_humidity_pct"], 88.0)
        # Must clearly include scientific disclaimer that weather alone does not prove infection
        self.assertIn("do not prove", risk["scientific_disclaimer"].lower())

    def test_weather_environmental_risk_tamil(self):
        """Test Open-Meteo environmental risk synthesis in Tamil."""
        weather_mock = {
            "current": {"temperature": 29.0, "humidity": 70.0, "wind_speed": 10.0, "precipitation": 0.0},
            "hourly": [{"precipitation_probability": 15}]
        }
        risk = self.weather.get_environmental_risk(
            weather_data=weather_mock,
            crop="Paddy",
            condition="Blast",
            language="ta"
        )
        self.assertIn("குறிப்பு", risk["scientific_disclaimer"])

    def test_api_crops_analyze_jpeg(self):
        """Test crop diagnosis with JPEG leaf image."""
        img_bytes = create_synthetic_image("JPEG")
        resp = client.post(
            "/api/crops/analyze",
            files={"file": ("leaf.jpg", img_bytes, "image/jpeg")},
            data={"mode": "direct", "explain": "true", "language": "en"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("crop", data)
        self.assertIn("condition", data)
        self.assertIn("explanation", data)
        self.assertIsNotNone(data["explanation"])

    def test_api_crops_analyze_png(self):
        """Test crop diagnosis with PNG leaf image."""
        img_bytes = create_synthetic_image("PNG")
        resp = client.post(
            "/api/crops/analyze",
            files={"file": ("leaf.png", img_bytes, "image/png")},
            data={"mode": "direct", "explain": "true", "language": "en"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("crop", data)

    def test_api_crops_analyze_webp(self):
        """Test crop diagnosis with WebP leaf image."""
        img_bytes = create_synthetic_image("WEBP")
        resp = client.post(
            "/api/crops/analyze",
            files={"file": ("leaf.webp", img_bytes, "image/webp")},
            data={"mode": "direct", "explain": "true", "language": "en"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("crop", data)

    def test_api_crops_analyze_invalid_type(self):
        """Test rejecting non-image uploads with 400 Bad Request."""
        text_bytes = b"Hello agricultural assistant"
        resp = client.post(
            "/api/crops/analyze",
            files={"file": ("notes.txt", text_bytes, "text/plain")}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unsupported file format", resp.json()["detail"])

    def test_api_crops_analyze_empty_file(self):
        """Test rejecting empty files."""
        resp = client.post(
            "/api/crops/analyze",
            files={"file": ("leaf.jpg", b"", "image/jpeg")}
        )
        self.assertEqual(resp.status_code, 400)

    def test_api_weather_risk_endpoint(self):
        """Test /api/weather/risk endpoint."""
        resp = client.get("/api/weather/risk?lat=11.0168&lon=76.9558&crop=Tomato&condition=Early_blight&language=en")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("risk_level", data)
        self.assertIn("scientific_disclaimer", data)

    def test_api_assistant_multimodal_endpoint(self):
        """Test /api/assistant/multimodal endpoint with leaf image + text query."""
        img_bytes = create_synthetic_image("JPEG")
        resp = client.post(
            "/api/assistant/multimodal",
            files={"image": ("test_leaf.jpg", img_bytes, "image/jpeg")},
            data={"query": "What are these spots and should I spray today?", "language": "en"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("explanation", data)
        self.assertIn("reply", data)
        self.assertIn("crop_prediction", data)
        self.assertIn("observations", data["explanation"])


if __name__ == "__main__":
    unittest.main()
