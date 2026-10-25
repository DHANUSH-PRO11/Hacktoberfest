"""
AgroNex AI - Module 2: Gemma Multimodal Copilot Comprehensive Test Suite

Tests:
1. Model and API verification:
   - verify_model_endpoint reports exact configuration, candidate models, and credentials status.
   - No silent model spoofing or false claims.
2. Agricultural Explanation Workflow:
   - Generates all 10 Module 2 structured fields with exact field names.
   - Preserves legacy aliases for backward compatibility.
   - Bilingual support: English and Tamil with agricultural terminology.
3. Evidence and Safety:
   - Inconclusive predictions (<60% confidence or quality warning) trigger strict safety overrides.
   - Forbids chemical sprays on uncertain diagnoses.
   - Missing weather data is handled without fabricating measurements.
   - Distinguishes visible symptoms from possible explanations.
4. Multimodal & Multi-turn Chat:
   - Accepts image bytes, crop prediction context, weather context, and user questions.
   - Retains conversation history across turns.
   - Returns the 5 required quick prompts in English and Tamil.
5. Structured Output Validation & Robustness:
   - Malformed JSON recovery and fallback engine resilience.
   - API endpoints: /api/assistant/model-info, /api/assistant/chat, /api/assistant/multimodal.
"""

try:
    import pytest
    fixture = pytest.fixture
except ImportError:
    pytest = None
    def fixture(fn):
        return fn

import io
import sys
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app
from services.ai.gemma_assistant import GemmaMultimodalAssistant
from schemas.schemas import StructuredExplanation, ChatMessage

client = TestClient(app)


@fixture
def sample_leaf_image_bytes():
    """Create a minimal valid RGB PNG image in-memory."""
    img = Image.new("RGB", (256, 256), color=(45, 130, 45))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestModelAndEndpointVerification:
    """Requirement 2: Model and API Verification."""

    def test_verify_model_endpoint_reports_status(self):
        assistant = GemmaMultimodalAssistant()
        verification = assistant.verify_model_endpoint()

        assert "api_configured" in verification
        assert "target_model" in verification
        assert "candidate_models" in verification
        assert "endpoint_reachable" in verification
        assert "status_message" in verification

        # Must report exact configuration without silent spoofing
        if not verification["api_configured"]:
            assert verification["is_using_grounding_engine"] is True
            assert "grounding" in verification["status_message"].lower() or "missing" in verification["status_message"].lower()

    def test_model_info_api_endpoint(self):
        response = client.get("/api/assistant/model-info")
        assert response.status_code == 200
        data = response.json()
        assert "model_verification" in data
        assert "supported_languages" in data
        assert "en" in data["supported_languages"]
        assert "ta" in data["supported_languages"]
        assert "module_2_fields" in data
        assert len(data["module_2_fields"]) == 10


class TestAgriculturalExplanationWorkflow:
    """Requirement 3 & 4: Agricultural Explanation & Safety."""

    def test_explanation_contains_all_10_module2_fields_english(self, sample_leaf_image_bytes):
        assistant = GemmaMultimodalAssistant()
        prediction = {
            "predicted_class": "Tomato___Early_blight",
            "confidence": 0.88,
            "crop": "Tomato",
            "is_inconclusive": False,
            "quality_status": "Passed",
            "top_predictions": [
                {"class_name": "Tomato___Early_blight", "confidence": 0.88},
                {"class_name": "Tomato___Late_blight", "confidence": 0.08}
            ]
        }
        weather = {
            "temperature": 27.5,
            "humidity": 82.0,
            "rainfall": 12.0,
            "retrieval_timestamp": "2026-10-25T16:00:00Z"
        }

        explanation = assistant.explain_leaf_symptoms(
            image_bytes=sample_leaf_image_bytes,
            crop_prediction=prediction,
            weather_data=weather,
            user_question="What are these concentric spots on my tomato leaves?",
            language="en"
        )

        assert isinstance(explanation, (dict, StructuredExplanation))
        # Validate against Pydantic schema
        validated = StructuredExplanation.model_validate(explanation) if isinstance(explanation, dict) else explanation

        # Check all 10 required Module 2 fields
        assert validated.summary is not None and len(validated.summary) > 0
        assert validated.observed_symptoms is not None and len(validated.observed_symptoms) > 0
        assert validated.possible_causes is not None and len(validated.possible_causes) > 0
        assert isinstance(validated.alternative_explanations, list)
        assert validated.model_prediction_context is not None
        assert validated.weather_influence is not None
        assert isinstance(validated.recommended_next_steps, list) and len(validated.recommended_next_steps) > 0
        assert isinstance(validated.prevention_guidance, list) and len(validated.prevention_guidance) > 0
        assert validated.uncertainty_and_limitations is not None
        assert validated.kvk_consultation_guidance is not None

        # Verify legacy aliases are populated
        assert validated.disease_name == validated.summary
        assert validated.symptoms == validated.observed_symptoms
        assert validated.recommendations == validated.recommended_next_steps
        assert validated.preventive_measures == validated.prevention_guidance

    def test_explanation_bilingual_tamil(self, sample_leaf_image_bytes):
        assistant = GemmaMultimodalAssistant()
        prediction = {
            "predicted_class": "Tomato___Early_blight",
            "confidence": 0.85,
            "crop": "Tomato",
            "is_inconclusive": False,
            "quality_status": "Passed"
        }

        explanation = assistant.explain_leaf_symptoms(
            image_bytes=sample_leaf_image_bytes,
            crop_prediction=prediction,
            weather_data=None,
            user_question="என் தக்காளி இலைகளில் கரும்புள்ளிகள் உள்ளன",
            language="ta"
        )

        assert isinstance(explanation, (dict, StructuredExplanation))
        validated = StructuredExplanation.model_validate(explanation) if isinstance(explanation, dict) else explanation
        assert validated.summary is not None
        # Tamil agricultural keywords check
        assert any(kw in validated.summary or kw in (validated.kvk_consultation_guidance or "") for kw in ["வேளாண்", "தக்காளி", "இலை", "நோய்", "KVK", "கண்காணிப்பு"])

    def test_strict_safety_override_on_inconclusive_prediction(self, sample_leaf_image_bytes):
        """When prediction is inconclusive (<60% or quality warning), chemical treatment MUST be forbidden."""
        assistant = GemmaMultimodalAssistant()
        inconclusive_prediction = {
            "predicted_class": "Apple___Apple_scab",
            "confidence": 0.42,
            "crop": "Apple",
            "is_inconclusive": True,
            "uncertainty_reason": "Low confidence (0.42 < 0.60)",
            "quality_status": "Warning: Mild Blur"
        }

        explanation = assistant.explain_leaf_symptoms(
            image_bytes=sample_leaf_image_bytes,
            crop_prediction=inconclusive_prediction,
            weather_data=None,
            user_question="Should I spray copper fungicide right now?",
            language="en"
        )

        # Check safety constraints
        all_steps_text = " ".join(explanation.recommended_next_steps).lower()
        limitations_text = explanation.uncertainty_and_limitations.lower()

        # Must explicitly warn against chemical treatment based on uncertain result
        assert "do not spray" in all_steps_text or "do not apply chemical" in all_steps_text or "avoid chemical" in all_steps_text
        assert "uncertain" in limitations_text or "inconclusive" in limitations_text
        # Must advise clear photograph and physical KVK inspection
        assert "kvk" in explanation.kvk_consultation_guidance.lower()
        assert "krishi vigyan kendra" in explanation.kvk_consultation_guidance.lower() or "kvk" in explanation.kvk_consultation_guidance.lower()

    def test_missing_weather_data_handling(self, sample_leaf_image_bytes):
        """Missing weather context must not result in fabricated readings."""
        assistant = GemmaMultimodalAssistant()
        prediction = {
            "predicted_class": "Potato___Late_blight",
            "confidence": 0.91,
            "crop": "Potato",
            "is_inconclusive": False,
            "quality_status": "Passed"
        }

        explanation = assistant.explain_leaf_symptoms(
            image_bytes=sample_leaf_image_bytes,
            crop_prediction=prediction,
            weather_data=None,  # No weather data
            user_question="How will weather affect this?",
            language="en"
        )

        # Must state that local weather measurements were not provided
        assert "not provided" in explanation.weather_influence.lower() or "unavailable" in explanation.weather_influence.lower()


class TestMultiTurnBilingualChat:
    """Requirement 5: Bilingual Chat & Follow-up."""

    def test_chat_with_conversation_history(self):
        assistant = GemmaMultimodalAssistant()
        history = [
            {"sender": "user", "text": "I noticed brown circular spots on my tomato plants."},
            {"sender": "assistant", "text": "These appear consistent with Early Blight (Alternaria solani)."},
        ]

        response = assistant.chat(
            message="What should I check before treating this plant?",
            language="en",
            conversation_history=history
        )

        assert isinstance(response, str)
        assert len(response) > 20
        # The response should address what to check (weather, leaf undersides, dosage)
        assert any(term in response.lower() for term in ["check", "inspect", "weather", "leaf", "symptom", "kvk"])

    def test_chat_tamil_language(self):
        assistant = GemmaMultimodalAssistant()
        response = assistant.chat(
            message="இந்த முடிவை தமிழில் விளக்குங்கள்",
            language="ta",
            crop_context="Tomato Early Blight"
        )

        assert isinstance(response, str)
        assert len(response) > 10

    def test_api_chat_endpoint_returns_quick_prompts(self):
        payload = {
            "message": "When should I consult a KVK expert?",
            "language": "en",
            "conversation_history": []
        }
        response = client.post("/api/assistant/chat", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert "reply" in data
        assert "detected_language" in data
        assert data["detected_language"] == "en"
        assert "quick_prompts" in data
        assert len(data["quick_prompts"]) == 5
        assert "What symptoms did the model detect?" in data["quick_prompts"]
        assert "When should I consult a KVK expert?" in data["quick_prompts"]

    def test_api_chat_endpoint_tamil_quick_prompts(self):
        payload = {
            "message": "KVK நிபுணரை எப்போது அணுக வேண்டும்?",
            "language": "ta",
            "conversation_history": []
        }
        response = client.post("/api/assistant/chat", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["detected_language"] == "ta"
        assert len(data["quick_prompts"]) == 5
        assert any("KVK" in q for q in data["quick_prompts"])


class TestMultimodalApiEndpoint:
    """Requirement 6: Multimodal Assistant Page Integration."""

    def test_api_multimodal_endpoint_with_image_and_prediction(self, sample_leaf_image_bytes):
        files = {
            "image": ("leaf.png", sample_leaf_image_bytes, "image/png")
        }
        data = {
            "question": "What symptoms did the model detect?",
            "language": "en",
            "crop_prediction": '{"predicted_class": "Corn_(maize)___Common_rust_", "confidence": 0.89, "crop": "Corn (maize)", "is_inconclusive": false, "quality_status": "Passed"}',
            "weather_data": '{"temperature": 29.0, "humidity": 75.0, "retrieval_timestamp": "2026-10-25T16:15:00Z"}'
        }

        response = client.post("/api/assistant/multimodal", files=files, data=data)
        assert response.status_code == 200
        res_json = response.json()

        assert "reply" in res_json
        assert "explanation" in res_json
        assert res_json["explanation"] is not None
        assert "model_used" in res_json
        assert "quick_prompts" in res_json
        assert len(res_json["quick_prompts"]) == 5

        # Check structured explanation fields
        explanation = res_json["explanation"]
        assert "summary" in explanation
        assert "observed_symptoms" in explanation
        assert "possible_causes" in explanation
        assert "alternative_explanations" in explanation
        assert "model_prediction_context" in explanation
        assert "weather_influence" in explanation
        assert "recommended_next_steps" in explanation
        assert "prevention_guidance" in explanation
        assert "uncertainty_and_limitations" in explanation
        assert "kvk_consultation_guidance" in explanation

    def test_api_multimodal_endpoint_invalid_image_type(self):
        files = {
            "image": ("test.txt", b"plain text is not an image", "text/plain")
        }
        data = {
            "question": "Analyze this leaf",
            "language": "en"
        }
        response = client.post("/api/assistant/multimodal", files=files, data=data)
        assert response.status_code == 400
        assert "unsupported file format" in response.json()["detail"].lower() or "corrupted" in response.json()["detail"].lower()


class TestRobustnessAndErrorHandling:
    """Requirement 8: Structured Output Validation & Robustness."""

    def test_fallback_grounding_engine_deterministic_response(self, sample_leaf_image_bytes):
        """Direct test of the deterministic agricultural grounding engine fallback."""
        assistant = GemmaMultimodalAssistant()
        fallback = assistant._fallback_explanation(
            predicted_class="Pepper__bell___Bacterial_spot",
            confidence=0.82,
            weather_data={"temperature": 28, "humidity": 85},
            user_question="What are these water-soaked lesions?",
            language="en",
            is_inconclusive=False,
            quality_status="Passed"
        )

        assert isinstance(fallback, StructuredExplanation)
        assert "bacterial spot" in fallback.summary.lower()
        assert len(fallback.observed_symptoms) >= 2
        assert len(fallback.recommended_next_steps) >= 3
        assert "KVK" in fallback.kvk_consultation_guidance
