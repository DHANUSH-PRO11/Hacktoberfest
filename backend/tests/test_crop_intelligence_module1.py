"""
Module 1: Crop Intelligence Engine Comprehensive Test Suite
Tests:
- Format verification (JPEG, PNG, WebP)
- Rejection of oversized (>10MB), empty, and corrupted files
- Non-image / wrong MIME rejection
- Image Quality Gate: low resolution, darkness, overexposure, blur, low texture
- Missing model file handling & session initialization
- Output tensor interpretation, softmax numerical stability, and 38-class mapping
- Top-5 prediction ranking & ambiguity margin detection
- Diagnostic uncertainty policy and inconclusive state flags
- API endpoint contract completeness and HTTP error responses
- Real ONNX inference execution
"""

import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
from PIL import Image, ImageFilter
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app
from services.ai.image_quality_service import ImageQualityService
from services.ai.onnx_inference_service import OnnxInferenceService
from services.ai.disease_detector import DiseaseDetector


def create_test_image_bytes(
    fmt="JPEG",
    width=224,
    height=224,
    color=(40, 160, 50),
    blur=False,
    noise=True
) -> bytes:
    """Helper to generate in-memory test images in specified format and conditions."""
    if noise:
        np.random.seed(42)
        base = np.zeros((height, width, 3), dtype=np.uint8)
        base[:, :, 0] = np.clip(color[0] + np.random.randint(-15, 15, (height, width)), 0, 255)
        base[:, :, 1] = np.clip(color[1] + np.random.randint(-20, 20, (height, width)), 0, 255)
        base[:, :, 2] = np.clip(color[2] + np.random.randint(-15, 15, (height, width)), 0, 255)
        img = Image.fromarray(base, mode="RGB")
    else:
        img = Image.new("RGB", (width, height), color)

    if blur:
        img = img.filter(ImageFilter.BoxBlur(12))

    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class TestImageQualityService(unittest.TestCase):
    """Evaluates the standalone Image Quality Gate."""

    def setUp(self):
        self.quality_service = ImageQualityService()

    def test_valid_image_passes_quality_gate(self):
        img_bytes = create_test_image_bytes("JPEG", width=300, height=300, color=(50, 160, 60))
        result = self.quality_service.evaluate_quality(img_bytes)
        self.assertIn(result["quality_status"], ["Passed", "Warning: Low Texture"])
        self.assertGreater(result["quality_score"], 0.6)
        self.assertIsInstance(result["photography_tips"], list)
        self.assertGreater(len(result["photography_tips"]), 0)

    def test_low_resolution_detection(self):
        # 60x60 is below min_image_width (100)
        img_bytes = create_test_image_bytes("JPEG", width=60, height=60)
        result = self.quality_service.evaluate_quality(img_bytes)
        issue_codes = [issue["code"] for issue in result["detected_issues"]]
        self.assertIn("LOW_RESOLUTION", issue_codes)
        self.assertTrue(any("LOW RESOLUTION" in result["quality_status"].upper() or "LOW_RESOLUTION" in code for code in issue_codes))

    def test_excessive_darkness_detection(self):
        # Very dark near-black image (mean luminance < 40)
        img_bytes = create_test_image_bytes("JPEG", width=224, height=224, color=(10, 12, 10))
        result = self.quality_service.evaluate_quality(img_bytes)
        issue_codes = [issue["code"] for issue in result["detected_issues"]]
        self.assertIn("LOW_LIGHT", issue_codes)
        self.assertLess(result["quality_score"], 1.0)

    def test_overexposure_detection(self):
        # Almost pure white image
        img_bytes = create_test_image_bytes("PNG", width=224, height=224, color=(250, 252, 251), noise=False)
        result = self.quality_service.evaluate_quality(img_bytes)
        issue_codes = [issue["code"] for issue in result["detected_issues"]]
        self.assertTrue("OVEREXPOSED" in issue_codes or "LOW_TEXTURE" in issue_codes)

    def test_blur_detection(self):
        # Heavy blur reduces discrete Laplacian variance
        img_bytes = create_test_image_bytes("JPEG", width=224, height=224, color=(50, 150, 60), blur=True)
        result = self.quality_service.evaluate_quality(img_bytes)
        issue_codes = [issue["code"] for issue in result["detected_issues"]]
        self.assertIn("BLUR_DETECTED", issue_codes)

    def test_corrupted_image_handling(self):
        corrupted_bytes = b"NOT_AN_IMAGE_FILE_DATA_CORRUPT"
        result = self.quality_service.evaluate_quality(corrupted_bytes)
        self.assertEqual(result["quality_status"], "Degraded")
        self.assertEqual(result["quality_score"], 0.0)
        self.assertIn("INVALID_IMAGE", [i["code"] for i in result["detected_issues"]])

    def test_tamil_language_support_in_tips(self):
        img_bytes = create_test_image_bytes("JPEG", width=60, height=60)
        result = self.quality_service.evaluate_quality(img_bytes, language="ta")
        # Ensure photography tips are returned in Tamil
        self.assertTrue(any("வெளிச்சம்" in tip or "படம்" in tip for tip in result["photography_tips"]))


class TestOnnxInferenceService(unittest.TestCase):
    """Evaluates ONNX inference service, session reuse, preprocessing, and 38-class mapping."""

    @classmethod
    def setUpClass(cls):
        cls.service = OnnxInferenceService.get_instance()

    def test_session_singleton_caching(self):
        service2 = OnnxInferenceService.get_instance()
        self.assertIs(self.service, service2)
        self.assertIsNotNone(self.service.session)

    def test_missing_model_file_handling(self):
        with self.assertRaises(FileNotFoundError):
            OnnxInferenceService(model_path="non_existent_model_file.onnx")

    def test_missing_classes_file_handling(self):
        with self.assertRaises(FileNotFoundError):
            OnnxInferenceService(classes_path="non_existent_classes.json")

    def test_class_count_and_mapping(self):
        self.assertEqual(self.service.num_classes, 38)
        self.assertIn("Tomato___Early_blight", self.service.classes)
        self.assertIn("Potato___Late_blight", self.service.classes)
        self.assertIn("Corn_(maize)___healthy", self.service.classes)

    def test_direct_preprocessing_tensor_shape(self):
        img = Image.new("RGB", (320, 240), (60, 150, 40))
        tensor = self.service.preprocess_image(img, mode="direct")
        self.assertEqual(tensor.shape, (1, 3, 224, 224))
        self.assertEqual(tensor.dtype, np.float32)

    def test_letterbox_preprocessing_tensor_shape(self):
        img = Image.new("RGB", (400, 200), (60, 150, 40))
        tensor = self.service.preprocess_image(img, mode="letterbox")
        self.assertEqual(tensor.shape, (1, 3, 224, 224))
        self.assertEqual(tensor.dtype, np.float32)

    def test_real_onnx_inference_and_top5_ranking(self):
        img = Image.new("RGB", (224, 224), (50, 160, 60))
        tensor = self.service.preprocess_image(img, mode="direct")
        result = self.service.run_inference(tensor, top_k=5)

        self.assertIn("primary_prediction", result)
        self.assertIn("top_predictions", result)
        self.assertEqual(len(result["top_predictions"]), 5)

        # Check top-5 are sorted descending by confidence
        scores = [p["confidence"] for p in result["top_predictions"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

        # Check sum of probabilities <= 1.0
        self.assertLessEqual(sum(scores), 1.0001)

        primary = result["primary_prediction"]
        self.assertIn("class_name", primary)
        self.assertIn("crop", primary)
        self.assertIn("condition", primary)
        self.assertIn("raw_score", primary)
        self.assertIsInstance(result["is_ambiguous"], bool)
        self.assertGreater(result["inference_latency_ms"], 0.0)

    def test_invalid_tensor_shape_rejection(self):
        invalid_tensor = np.zeros((1, 3, 100, 100), dtype=np.float32)
        with self.assertRaises(ValueError):
            self.service.run_inference(invalid_tensor)


class TestDiseaseDetectorEndToEnd(unittest.TestCase):
    """Evaluates DiseaseDetector uncertainty policy, contracts, and formats."""

    @classmethod
    def setUpClass(cls):
        cls.detector = DiseaseDetector()

    def test_jpeg_inference_contract(self):
        jpeg_bytes = create_test_image_bytes("JPEG", width=224, height=224)
        result = self.detector.predict(jpeg_bytes)

        # Module 1 Contract Fields
        self.assertTrue(result["analysis_id"].startswith("ca_"))
        self.assertIn("predicted_class", result)
        self.assertIn("display_name", result)
        self.assertIsInstance(result["model_score"], float)
        self.assertIn("confidence_interpretation", result)
        self.assertIsInstance(result["top_predictions"], list)
        self.assertEqual(len(result["top_predictions"]), 5)
        self.assertIn("quality_assessment", result)
        self.assertIsInstance(result["inconclusive"], bool)
        self.assertIsInstance(result["photography_tips"], list)
        self.assertIn("model_version", result)
        self.assertGreater(result["processing_time_ms"], 0.0)

        # Backward compatibility fields
        self.assertIn("crop", result)
        self.assertIn("condition", result)
        self.assertIn("confidence", result)
        self.assertIn("is_healthy", result)
        self.assertIn("status", result)
        self.assertEqual(result["is_inconclusive"], result["inconclusive"])

    def test_png_inference(self):
        png_bytes = create_test_image_bytes("PNG", width=224, height=224)
        result = self.detector.predict(png_bytes)
        self.assertIsNotNone(result["predicted_class"])
        self.assertGreater(result["confidence"], 0.0)

    def test_webp_inference(self):
        webp_bytes = create_test_image_bytes("WEBP", width=224, height=224)
        result = self.detector.predict(webp_bytes)
        self.assertIsNotNone(result["predicted_class"])
        self.assertGreater(result["confidence"], 0.0)

    def test_uncertainty_policy_triggers_inconclusive_on_low_score(self):
        # Test with detector set to a high uncertainty threshold (e.g. 0.99)
        strict_detector = DiseaseDetector(uncertainty_threshold=0.999)
        jpeg_bytes = create_test_image_bytes("JPEG", width=224, height=224)
        result = strict_detector.predict(jpeg_bytes)

        self.assertTrue(result["inconclusive"])
        self.assertTrue(result["is_inconclusive"])
        self.assertIn(result["status"], ["Inconclusive", "Uncertain"])
        self.assertTrue(
            "inconclusive" in result["confidence_interpretation"].lower() or
            "uncertain" in result["confidence_interpretation"].lower()
        )
        self.assertIsNotNone(result["uncertainty_reason"])


class TestCropsAPIEndpoints(unittest.TestCase):
    """Evaluates FastAPI HTTP validation, 10MB limit, magic byte checking, and error responses."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_valid_jpeg_upload(self):
        jpeg_bytes = create_test_image_bytes("JPEG", width=224, height=224)
        res = self.client.post(
            "/api/crops/analyze",
            files={"file": ("leaf.jpg", jpeg_bytes, "image/jpeg")},
            data={"explain": "false"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("analysis_id", data)
        self.assertIn("predicted_class", data)
        self.assertIn("model_score", data)
        self.assertIn("confidence_interpretation", data)
        self.assertIn("quality_assessment", data)

    def test_valid_png_upload(self):
        png_bytes = create_test_image_bytes("PNG", width=224, height=224)
        res = self.client.post(
            "/api/crops/analyze",
            files={"file": ("leaf.png", png_bytes, "image/png")},
            data={"explain": "false"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("predicted_class", res.json())

    def test_valid_webp_upload(self):
        webp_bytes = create_test_image_bytes("WEBP", width=224, height=224)
        res = self.client.post(
            "/api/crops/analyze",
            files={"file": ("leaf.webp", webp_bytes, "image/webp")},
            data={"explain": "false"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("predicted_class", res.json())

    def test_empty_file_rejected(self):
        res = self.client.post(
            "/api/crops/analyze",
            files={"file": ("empty.jpg", b"", "image/jpeg")},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("empty", res.json()["detail"].lower())

    def test_oversized_file_rejected_with_413(self):
        # 11 MB dummy stream
        oversized_bytes = b"A" * (11 * 1024 * 1024)
        res = self.client.post(
            "/api/crops/analyze",
            files={"file": ("large.jpg", oversized_bytes, "image/jpeg")},
        )
        self.assertEqual(res.status_code, 413)
        self.assertIn("exceeds maximum allowed size of 10 MB", res.json()["detail"])

    def test_spoofed_mime_type_non_image_rejected(self):
        # Claims to be image/jpeg, but content is plaintext HTML
        fake_jpeg = b"<html><body>Not an image!</body></html>"
        res = self.client.post(
            "/api/crops/analyze",
            files={"file": ("fake.jpg", fake_jpeg, "image/jpeg")},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("invalid image file content", res.json()["detail"].lower())

    def test_corrupted_image_rejected(self):
        # Starts with JPEG magic bytes but has corrupted payload
        corrupt_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00CORRUPTED_TRUNCATED"
        res = self.client.post(
            "/api/crops/analyze",
            files={"file": ("corrupt.jpg", corrupt_jpeg, "image/jpeg")},
        )
        self.assertEqual(res.status_code, 400)
        self.assertTrue(
            "corrupted" in res.json()["detail"].lower() or "failed to decode" in res.json()["detail"].lower()
        )

    def test_crops_history_endpoint(self):
        res = self.client.get("/api/crops/history")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

    def test_crops_stats_endpoint(self):
        res = self.client.get("/api/crops/stats")
        self.assertEqual(res.status_code, 200)
        stats = res.json()
        self.assertIn("total_scans", stats)
        self.assertIn("healthy_count", stats)


if __name__ == "__main__":
    unittest.main()
