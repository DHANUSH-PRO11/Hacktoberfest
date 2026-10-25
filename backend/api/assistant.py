import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Depends, Query
from supabase import Client
from schemas import schemas
from services.ai.ai_assistant import AIAssistant
from services.ai.gemma_assistant import GemmaMultimodalAssistant, QUICK_PROMPTS_EN, QUICK_PROMPTS_TA
from services.ai.disease_detector import DiseaseDetector
from services.weather_service import WeatherService
from config.database import get_supabase
from config import local_db
import os
import io
from PIL import Image
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter()
assistant = AIAssistant()
gemma_assistant = GemmaMultimodalAssistant()
detector = DiseaseDetector()
weather_service = WeatherService()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


@router.get("/model-info")
def get_model_verification():
    """
    Returns real-time diagnostic verification of the configured Gemma 4 / Gemini model endpoint.
    Exposes availability, active model identifier, candidate models, supported languages,
    and fallback engine status with complete transparency.
    """
    verification = gemma_assistant.verify_model_endpoint()
    return {
        "model_verification": verification,
        **verification,
        "supported_languages": ["en", "ta"],
        "module_2_fields": [
            "summary",
            "observed_symptoms",
            "possible_causes",
            "alternative_explanations",
            "model_prediction_context",
            "weather_influence",
            "recommended_next_steps",
            "prevention_guidance",
            "uncertainty_and_limitations",
            "kvk_consultation_guidance"
        ]
    }


@router.post("/chat", response_model=schemas.ChatResponse)
def chat(message: schemas.ChatMessage, db: Optional[Client] = Depends(get_supabase)):
    """
    Bilingual chat endpoint supporting Tamil and English with multi-turn conversation memory,
    grounded agricultural responses, and standardized farmer quick prompts.
    """
    try:
        lang = message.language or "en"
        # If context contains crop diagnosis, generate structured explanation through Gemma 4
        explanation = None
        if message.context and ("crop" in message.context or "condition" in message.context):
            try:
                explanation = gemma_assistant.explain_leaf_symptoms(
                    user_query=message.message,
                    crop_context=message.context,
                    weather_context=message.context.get("weather"),
                    language=lang,
                    conversation_history=message.conversation_history
                )
            except Exception as e:
                logger.warning(f"Gemma symptom explanation warning: {e}")

        # Primary answer through Gemma multimodal assistant
        gemma_res = gemma_assistant.answer_general_query(
            query=message.message,
            language=lang,
            context=message.context,
            conversation_history=message.conversation_history
        )
        reply = gemma_res.get("reply") or ""
        quick_prompts = gemma_res.get("quick_prompts") or (QUICK_PROMPTS_TA if lang == "ta" else QUICK_PROMPTS_EN)

        # Audio synthesis (graceful fallback if TTS fails)
        audio_base64 = None
        try:
            audio_base64 = assistant.text_to_speech(reply, language_code="ta-IN" if lang == "ta" else "en-IN")
        except Exception as e:
            logger.debug(f"Audio synthesis notice: {e}")

        # Save to Supabase if configured
        if db is not None:
            try:
                db.table("chat_history").insert([
                    {"role": "user", "message": message.message},
                    {"role": "ai", "message": reply}
                ]).execute()
            except Exception as e:
                logger.warning(f"Supabase chat save failed: {e}")

        # Always save to local_db for offline resilience
        try:
            local_db.save_chat_message("user", message.message)
            local_db.save_chat_message("ai", reply)
        except Exception as e:
            logger.warning(f"Local db chat save failed: {e}")

        return {
            "reply": reply,
            "audio_base64": audio_base64,
            "explanation": explanation,
            "detected_language": lang,
            "quick_prompts": quick_prompts
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multimodal")
async def multimodal_chat(
    query: Optional[str] = Form(None),
    question: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    language: Optional[str] = Form("en"),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    context: Optional[str] = Form(None),
    crop_prediction: Optional[str] = Form(None),
    weather_data: Optional[str] = Form(None),
    conversation_history: Optional[str] = Form(None),
    db: Optional[Client] = Depends(get_supabase)
):
    """
    Multimodal Gemma 4 entrypoint for image-plus-text queries.
    Accepts leaf photos (JPEG, PNG, WebP) along with farmer questions,
    runs open-source pathology classification (Module 1), queries Open-Meteo micro-climate (Module 3),
    and returns structured Gemma 4 explainable reasoning.
    """
    lang = language or "en"
    user_query = query or question

    parsed_context = {}
    if crop_prediction:
        try:
            parsed_context = json.loads(crop_prediction)
        except Exception:
            pass
    elif context:
        try:
            parsed_context = json.loads(context)
        except Exception:
            parsed_context = {"raw": context}

    parsed_weather = None
    if weather_data:
        try:
            parsed_weather = json.loads(weather_data)
        except Exception:
            pass

    parsed_history = None
    if conversation_history:
        try:
            parsed_history = json.loads(conversation_history)
        except Exception:
            pass

    image_bytes = None
    image_mime = "image/jpeg"
    prediction = None

    if image is not None:
        content_type = (image.content_type or "").lower()
        if content_type and not any(t in content_type for t in ["image/jpeg", "image/jpg", "image/png", "image/webp"]):
            raise HTTPException(status_code=400, detail="Unsupported file format: Only JPEG, PNG, and WebP leaf images are supported.")

        image_bytes = await image.read()
        if len(image_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Image file exceeds maximum allowed size of 10 MB.")

        try:
            with Image.open(io.BytesIO(image_bytes)) as img_test:
                img_test.verify()
        except Exception:
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")

        image_mime = content_type or "image/jpeg"

        # Run Module 1 Open-source model inference directly via stream if not supplied
        try:
            prediction = detector.predict(io.BytesIO(image_bytes), preprocessing_mode="direct", enable_tta=True, language=lang)
        except Exception as e:
            logger.error(f"Inference during multimodal analysis failed: {e}")

    # Use explicitly supplied crop context if inference was inconclusive or passed directly
    if not prediction and parsed_context:
        prediction = parsed_context
    elif prediction and parsed_context:
        # Merge supplied user labels if relevant
        for k, v in parsed_context.items():
            if k not in prediction or not prediction[k]:
                prediction[k] = v

    # Retrieve real-time weather from Module 3 or use supplied context
    weather_ctx = parsed_weather
    if not weather_ctx:
        lat = latitude if latitude is not None else 11.0168
        lon = longitude if longitude is not None else 76.9558
        crop_name = (prediction or {}).get("crop") or parsed_context.get("crop")
        cond_name = (prediction or {}).get("condition") or parsed_context.get("condition")

        try:
            weather_ctx = weather_service.get_weather(lat, lon, crop=crop_name, condition=cond_name)
        except Exception as e:
            logger.warning(f"Weather lookup failed: {e}")
            weather_ctx = None

    # Generate Gemma 4 structured explanation across all 10 Module 2 fields
    explanation = gemma_assistant.explain_leaf_symptoms(
        image_bytes=image_bytes,
        image_mime=image_mime,
        user_query=user_query,
        crop_context=prediction or parsed_context,
        weather_context=weather_ctx,
        language=lang,
        conversation_history=parsed_history
    )

    reply_text = explanation.get("summary") or explanation.get("observations") or "Assessment completed."
    audio_base64 = None
    try:
        audio_base64 = assistant.text_to_speech(reply_text, language_code="ta-IN" if lang == "ta" else "en-IN")
    except Exception as e:
        logger.debug(f"TTS notice: {e}")

    # Persist chat
    user_log = user_query or ("📷 Leaf inspection" if lang == "en" else "📷 இலை ஆய்வு")
    try:
        local_db.save_chat_message("user", user_log)
        local_db.save_chat_message("ai", reply_text)
    except Exception as e:
        logger.warning(f"Local db save error: {e}")

    quick_prompts = QUICK_PROMPTS_TA if lang == "ta" else QUICK_PROMPTS_EN

    return {
        "reply": reply_text,
        "explanation": explanation,
        "crop_prediction": prediction,
        "weather_context": weather_ctx,
        "audio_base64": audio_base64,
        "language": lang,
        "model_used": explanation.get("model_used", "Gemma 4"),
        "is_fallback": explanation.get("is_fallback", True),
        "quick_prompts": quick_prompts
    }


@router.post("/voice", response_model=schemas.VoiceChatResponse)
async def voice_chat(
    file: UploadFile = File(...),
    language: Optional[str] = Form("ta"),
    context: Optional[str] = Form(None),
    db: Optional[Client] = Depends(get_supabase)
):
    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file received")
        if len(audio_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Audio file exceeds maximum allowed size of 10 MB.")

        filename = file.filename or "recording.webm"
        if "." not in filename:
            ct = file.content_type or ""
            if "wav" in ct:
                filename = f"{filename}.wav"
            elif "mp4" in ct:
                filename = f"{filename}.mp4"
            elif "ogg" in ct:
                filename = f"{filename}.ogg"
            else:
                filename = f"{filename}.webm"

        parsed_context = None
        if context:
            try:
                parsed_context = json.loads(context)
            except Exception:
                parsed_context = {"raw_context": context}

        result = assistant.process_voice_chat(
            audio_bytes=audio_bytes,
            filename=filename,
            preferred_language=language or "ta",
            content_type=file.content_type or "audio/wav",
            context=parsed_context
        )

        user_text = result.get("transcription") or "Farmer Voice Query"
        reply_text = result.get("reply") or ""

        # Persist conversation
        if db is not None:
            try:
                db.table("chat_history").insert([
                    {"role": "user", "message": user_text},
                    {"role": "ai", "message": reply_text}
                ]).execute()
            except Exception as e:
                logger.warning(f"Supabase chat save failed: {e}")

        try:
            local_db.save_chat_message("user", user_text)
            local_db.save_chat_message("ai", reply_text)
        except Exception as e:
            logger.warning(f"Local db chat save failed: {e}")

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=List[schemas.ChatHistoryItem])
def get_chat_history(
    limit: int = Query(50, ge=1, le=100, description="Max chat messages to retrieve"),
    offset: int = Query(0, ge=0, description="Number of chat messages to skip"),
    db: Optional[Client] = Depends(get_supabase)
):
    """Retrieve chat history from Supabase or fallback to local SQLite with pagination."""
    if db is not None:
        try:
            res = db.table("chat_history").select("*").order("created_at", desc=True).range(offset, offset + limit - 1).execute()
            if res.data:
                return [{"id": str(r.get("id")), "role": r.get("role"), "message": r.get("message"), "created_at": str(r.get("created_at"))} for r in res.data]
        except Exception as e:
            logger.warning(f"Failed to fetch Supabase chat history: {e}")

    records = local_db.get_chat_history(limit=limit, offset=offset)
    return records


@router.delete("/history")
def clear_chat_history(db: Optional[Client] = Depends(get_supabase)):
    """Clears conversational history in both Supabase and local SQLite."""
    if db is not None:
        try:
            db.table("chat_history").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        except Exception as e:
            logger.warning(f"Failed to clear Supabase chat history: {e}")

    local_db.clear_chat_history()
    return {"success": True, "message": "Conversation history cleared successfully"}
