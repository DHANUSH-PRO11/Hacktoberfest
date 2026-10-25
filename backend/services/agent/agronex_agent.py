"""
AgroNex Agent — Autonomous Agricultural Copilot Workflow Engine
Orchestrates Computer Vision Disease Detection, Real-time Open-Meteo Weather Risk Rules,
Sarvam AI Conversational Reasoning, and Supabase Persistence into an AgentFoundry-compliant loop.
"""

import os
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pathlib import Path

from services.ai.disease_detector import DiseaseDetector
from services.ai.ai_assistant import AIAssistant
from services.ai.gemma_assistant import GemmaMultimodalAssistant
from services.weather_service import WeatherService
from config.database import get_supabase
from config.weather_thresholds import (
    SPRAY_RAIN_PROB_THRESHOLD,
    SPRAY_PRECIP_THRESHOLD_MM,
    SPRAY_WIND_SPEED_THRESHOLD_KMH
)
from supabase import Client

logger = logging.getLogger(__name__)

class AgroNexAgent:
    def __init__(
        self,
        detector: Optional[DiseaseDetector] = None,
        assistant: Optional[AIAssistant] = None,
        weather_service: Optional[WeatherService] = None,
        gemma: Optional[GemmaMultimodalAssistant] = None
    ):
        self.detector = detector or DiseaseDetector()
        self.assistant = assistant or AIAssistant()
        self.weather_service = weather_service or WeatherService()
        self.gemma = gemma or GemmaMultimodalAssistant()


    def run(
        self,
        query: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        image_filename: Optional[str] = None,
        audio_bytes: Optional[bytes] = None,
        audio_filename: Optional[str] = None,
        crop_hint: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        language: str = "en",
        db_client: Optional[Client] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes the 10-step AgentFoundry-compliant Agricultural Copilot Workflow.
        """
        workflow_start_time = time.perf_counter()
        trace: List[Dict[str, Any]] = []
        tools_called: List[str] = []

        def log_node(node_name: str, status: str, details: Dict[str, Any], duration_ms: float):
            trace.append({
                "node": node_name,
                "status": status,
                "duration_ms": round(duration_ms, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": details
            })

        # ---------------------------------------------------------
        # Node 1: Input Ingestion & Transcription (if audio provided)
        # ---------------------------------------------------------
        node_start = time.perf_counter()
        active_query = (query or "").strip()
        transcription = None
        detected_audio_lang = None

        if audio_bytes and len(audio_bytes) > 0:
            tools_called.append("sarvam_speech_to_text")
            try:
                detected_audio_lang, transcription = self.assistant.speech_to_text(
                    audio_bytes=audio_bytes,
                    filename=audio_filename or "voice.wav"
                )
                if transcription:
                    active_query = f"{active_query} {transcription}".strip() if active_query else transcription
                    if "ta" in (detected_audio_lang or ""):
                        language = "ta"
            except Exception as e:
                logger.warning(f"Audio transcription failed in agent: {e}")

        log_node(
            "input_ingestion",
            "completed",
            {
                "has_query": bool(active_query),
                "has_audio": bool(audio_bytes),
                "transcription": transcription,
                "has_image": bool(image_bytes),
                "has_coordinates": latitude is not None and longitude is not None,
                "language": language
            },
            (time.perf_counter() - node_start) * 1000
        )

        # ---------------------------------------------------------
        # Node 2: Intent Classification & Tool Routing
        # ---------------------------------------------------------
        node_start = time.perf_counter()
        query_lower = active_query.lower()
        should_run_vision = bool(image_bytes and len(image_bytes) > 0)
        has_prior_context = bool(context and isinstance(context, dict) and ("crop" in context or "condition" in context))
        should_run_weather = (latitude is not None and longitude is not None) or has_prior_context or any(
            k in query_lower for k in ["weather", "rain", "temperature", "humidity", "spray", "வானிலை", "மழை", "தெளிக்கலாமா"]
        )
        should_run_schemes = any(
            k in query_lower for k in ["scheme", "subsidy", "pm-kisan", "pmkisan", "திட்டம்", "மானியம்"]
        )

        log_node(
            "intent_routing",
            "completed",
            {
                "routed_tools": {
                    "disease_detector": should_run_vision,
                    "weather_service": should_run_weather,
                    "schemes_provider": should_run_schemes,
                    "agricultural_reasoner": True
                }
            },
            (time.perf_counter() - node_start) * 1000
        )

        # ---------------------------------------------------------
        # Node 3: Tool Execution — Disease Detector (if image)
        # ---------------------------------------------------------
        crop_prediction: Optional[Dict[str, Any]] = None
        if should_run_vision:
            node_start = time.perf_counter()
            tools_called.append("efficientnet_v2_disease_detector")
            temp_image_path = None
            try:
                os.makedirs("uploads", exist_ok=True)
                clean_name = os.path.basename(image_filename or "agent_leaf.jpg")
                temp_image_path = f"uploads/{int(time.time()*1000)}_{clean_name}"
                with open(temp_image_path, "wb") as f:
                    f.write(image_bytes)

                crop_prediction = self.detector.predict(temp_image_path, preprocessing_mode="direct", enable_tta=True)
                log_node(
                    "disease_detection",
                    "completed",
                    {
                        "crop": crop_prediction.get("crop"),
                        "condition": crop_prediction.get("condition"),
                        "confidence": crop_prediction.get("confidence"),
                        "status": crop_prediction.get("status"),
                        "quality_status": crop_prediction.get("quality_status")
                    },
                    (time.perf_counter() - node_start) * 1000
                )
            except Exception as e:
                logger.error(f"Disease detection failed: {e}")
                log_node(
                    "disease_detection",
                    "failed",
                    {"error": str(e)},
                    (time.perf_counter() - node_start) * 1000
                )
            finally:
                if temp_image_path and os.path.exists(temp_image_path):
                    try:
                        os.remove(temp_image_path)
                    except Exception:
                        pass
        elif has_prior_context:
            conf_raw = float(context.get("confidence", 0.0))
            conf_norm = conf_raw / 100.0 if conf_raw > 1.0 else conf_raw
            crop_prediction = {
                "crop": context.get("crop", crop_hint or "Unknown"),
                "condition": context.get("condition", "Healthy"),
                "confidence": conf_norm,
                "status": context.get("status", "High confidence" if conf_norm >= 0.6 else "Uncertain"),
                "quality_status": context.get("quality_status", "Passed"),
                "warning_message": context.get("warning_message"),
                "is_healthy": context.get("is_healthy", "healthy" in str(context.get("condition", "")).lower()),
                "severity": context.get("severity", "Not determined"),
                "risk": context.get("risk", "Not determined")
            }
            log_node(
                "disease_detection",
                "context_reused",
                {
                    "crop": crop_prediction.get("crop"),
                    "condition": crop_prediction.get("condition"),
                    "confidence": crop_prediction.get("confidence"),
                    "source": "grounded_consultation_context"
                },
                0.1
            )

        # ---------------------------------------------------------
        # Node 4: Tool Execution — Weather & Agricultural Alerts
        # ---------------------------------------------------------
        weather_data: Optional[Dict[str, Any]] = None
        if should_run_weather:
            node_start = time.perf_counter()
            tools_called.append("open_meteo_weather_service")
            # Default to regional coordinates (e.g. Coimbatore, Tamil Nadu agricultural hub) if farmer didn't grant location
            lat = latitude if latitude is not None else 11.0168
            lon = longitude if longitude is not None else 76.9558
            crop_name = (crop_prediction.get("crop") if crop_prediction else None) or crop_hint
            cond_name = crop_prediction.get("condition") if crop_prediction else None

            try:
                weather_data = self.weather_service.get_weather(lat, lon, crop=crop_name, condition=cond_name)
                log_node(
                    "weather_lookup",
                    "completed",
                    {
                        "lat": lat,
                        "lon": lon,
                        "temperature": weather_data.get("current", {}).get("temperature"),
                        "alerts_count": len(weather_data.get("alerts", []))
                    },
                    (time.perf_counter() - node_start) * 1000
                )
            except Exception as e:
                logger.warning(f"Weather lookup failed: {e}")
                log_node(
                    "weather_lookup",
                    "failed",
                    {"error": str(e)},
                    (time.perf_counter() - node_start) * 1000
                )

        # ---------------------------------------------------------
        # Node 4b: Tool Execution — Government Agricultural Schemes
        # ---------------------------------------------------------
        schemes_data: List[Dict[str, Any]] = []
        if should_run_schemes:
            node_start_sch = time.perf_counter()
            tools_called.append("schemes_provider")
            try:
                from api.schemes import AGRICULTURAL_SCHEMES
                schemes_data = AGRICULTURAL_SCHEMES
                log_node(
                    "schemes_provider",
                    "completed",
                    {"schemes_matched": len(schemes_data)},
                    (time.perf_counter() - node_start_sch) * 1000
                )
            except Exception as e:
                logger.warning(f"Schemes lookup failed: {e}")

        # ---------------------------------------------------------
        # Node 5: Context Assembly & Uncertainty Gatekeeping
        # ---------------------------------------------------------
        node_start = time.perf_counter()
        context_packet: Dict[str, Any] = {}
        spray_advisory = "Favorable for field operations."

        if crop_prediction:
            context_packet["crop"] = crop_prediction.get("crop")
            context_packet["condition"] = crop_prediction.get("condition")
            context_packet["confidence"] = float(crop_prediction.get("confidence", 0.0)) * 100.0
            context_packet["status"] = crop_prediction.get("status")
            context_packet["quality_status"] = crop_prediction.get("quality_status")
            context_packet["warning_message"] = crop_prediction.get("warning_message")
            context_packet["is_healthy"] = crop_prediction.get("is_healthy", False)
            context_packet["severity"] = crop_prediction.get("severity", "Not determined")
            context_packet["risk"] = crop_prediction.get("risk", "Not determined")

        if weather_data and weather_data.get("success"):
            context_packet["weather"] = weather_data
            # Check spray window safety
            current = weather_data.get("current", {})
            alerts = weather_data.get("alerts", [])
            rain_prob = 0
            if weather_data.get("forecast") and len(weather_data["forecast"]) > 0:
                rain_prob = max(rain_prob, weather_data["forecast"][0].get("precipitation_probability_mean", 0) or 0)
            if weather_data.get("hourly"):
                hourly_rain = [h.get("precipitation_probability", 0) or 0 for h in weather_data["hourly"][:24]]
                if hourly_rain:
                    rain_prob = max(rain_prob, max(hourly_rain))

            wind_speed = current.get("wind_speed", 0) or 0
            precip = current.get("precipitation", 0) or 0

            if rain_prob > SPRAY_RAIN_PROB_THRESHOLD or precip > SPRAY_PRECIP_THRESHOLD_MM:
                spray_advisory = "DO NOT SPRAY: High chance of rainfall (>60%). Chemical wash-off hazard."
            elif wind_speed > SPRAY_WIND_SPEED_THRESHOLD_KMH:
                spray_advisory = "CAUTION SPRAYING: High winds (>25 km/h). Severe spray drift hazard."
            else:
                spray_advisory = "SAFE SPRAY WINDOW: Low wind and minimal rain probability in immediate 24h."

            context_packet["spray_advisory"] = spray_advisory

        if schemes_data:
            context_packet["schemes"] = schemes_data

        # Uncertainty gatekeeper rule
        requires_expert_confirmation = False
        if crop_prediction:
            conf = float(crop_prediction.get("confidence", 0.0))
            if conf < 0.60 or crop_prediction.get("status") == "Uncertain" or crop_prediction.get("quality_status") != "Passed":
                requires_expert_confirmation = True

        context_packet["requires_expert_confirmation"] = requires_expert_confirmation

        log_node(
            "context_assembly",
            "completed",
            {
                "spray_advisory": spray_advisory,
                "requires_expert_confirmation": requires_expert_confirmation,
                "schemes_active": bool(schemes_data)
            },
            (time.perf_counter() - node_start) * 1000
        )

        # ---------------------------------------------------------
        # Node 6: Agricultural Reasoning & Recommendation Synthesis
        # ---------------------------------------------------------
        node_start = time.perf_counter()
        tools_called.append("gemma_multimodal_copilot")
        tools_called.append("sarvam_agricultural_reasoner")
        effective_query = active_query or (
            f"Analyze the health of this {context_packet.get('crop', 'crop')} and advise if I should spray today based on local weather."
            if crop_prediction else
            "What are the best agricultural management practices for my farm right now?"
        )

        # Generate structured explainable AI assessment via Gemma 4
        structured_explanation = None
        if crop_prediction or image_bytes:
            try:
                structured_explanation = self.gemma.explain_leaf_symptoms(
                    image_bytes=image_bytes,
                    image_mime="image/jpeg",
                    user_query=effective_query,
                    crop_context=crop_prediction,
                    weather_context=weather_data,
                    language=language
                )
            except Exception as ge:
                logger.warning(f"Gemma symptom explanation generation error: {ge}")

        response_text = self.assistant.answer(
            question=effective_query,
            language=language,
            context=context_packet
        )

        log_node(
            "agricultural_reasoning",
            "completed",
            {
                "response_length": len(response_text),
                "language_used": language,
                "gemma_explained": bool(structured_explanation)
            },
            (time.perf_counter() - node_start) * 1000
        )


        # ---------------------------------------------------------
        # Node 7: Audio Synthesis (TTS)
        # ---------------------------------------------------------
        node_start = time.perf_counter()
        audio_base64 = None
        try:
            tools_called.append("sarvam_bulbul_tts")
            tts_lang = "ta-IN" if language == "ta" else "en-IN"
            audio_base64 = self.assistant.text_to_speech(response_text, language_code=tts_lang)
            log_node(
                "voice_synthesis",
                "completed" if audio_base64 else "skipped",
                {"audio_generated": bool(audio_base64)},
                (time.perf_counter() - node_start) * 1000
            )
        except Exception as e:
            logger.warning(f"TTS generation failed: {e}")
            log_node("voice_synthesis", "failed", {"error": str(e)}, (time.perf_counter() - node_start) * 1000)

        # ---------------------------------------------------------
        # Node 8: Cloud Persistence (Supabase if available)
        # ---------------------------------------------------------
        node_start = time.perf_counter()
        db = db_client or get_supabase()
        persisted = False
        persistence_error = None

        if db is not None:
            try:
                tools_called.append("supabase_storage_and_db")
                if crop_prediction and should_run_vision:
                    db.table("crop_analyses").insert({
                        "crop_type": crop_prediction.get("crop", "Unknown"),
                        "detected_disease": crop_prediction.get("condition", "Unknown"),
                        "confidence": float(crop_prediction.get("confidence", 0.0)),
                        "severity": crop_prediction.get("severity", "Not determined"),
                        "risk_level": crop_prediction.get("risk", "Not determined")
                    }).execute()

                db.table("chat_history").insert([
                    {"role": "user", "message": effective_query},
                    {"role": "ai", "message": response_text}
                ]).execute()
                persisted = True
            except Exception as e:
                persistence_error = str(e)
                logger.warning(f"Supabase persistence error: {e}")

        # Local fallback persistence for offline resilience
        try:
            from config import local_db
            if crop_prediction and should_run_vision:
                local_db.save_crop_analysis({
                    "crop_type": crop_prediction.get("crop", "Unknown"),
                    "detected_disease": crop_prediction.get("condition", "Unknown"),
                    "confidence": float(crop_prediction.get("confidence", 0.0)),
                    "severity": crop_prediction.get("severity", "Not determined"),
                    "risk_level": crop_prediction.get("risk", "Not determined")
                })
            local_db.save_chat_message("user", effective_query)
            local_db.save_chat_message("ai", response_text)
            if not persisted:
                persisted = True
        except Exception as e:
            logger.warning(f"Local DB persistence fallback error: {e}")

        backend_used = "supabase" if (db is not None and not persistence_error and persisted) else ("sqlite_fallback" if persisted else "none")
        node_status = "completed" if (persisted and not persistence_error and db is not None) else ("offline_fallback" if persisted else "error")

        log_node(
            "persistence",
            node_status,
            {
                "persisted": persisted,
                "storage_backend": backend_used,
                "supabase_used": db is not None,
                "error": persistence_error
            },
            (time.perf_counter() - node_start) * 1000
        )

        # ---------------------------------------------------------
        # Node 9: AgentFoundry Result Assembly
        # ---------------------------------------------------------
        total_latency_ms = round((time.perf_counter() - workflow_start_time) * 1000, 2)

        return {
            "success": True,
            "status": "completed",
            "agent_name": "AgroNex Agricultural Copilot",
            "version": "1.0.0",
            "workflow_id": "agronex-farming-copilot",
            "query": effective_query,
            "transcription": transcription,
            "language": language,
            "recommendation": response_text,
            "explanation": structured_explanation,
            "audio_base64": audio_base64,
            "crop_prediction": crop_prediction,
            "weather_context": weather_data,
            "spray_advisory": spray_advisory,
            "requires_expert_confirmation": requires_expert_confirmation,
            "evidence_report": {
                "model_status": crop_prediction.get("status") if crop_prediction else "No Image",
                "quality_gate": crop_prediction.get("quality_status") if crop_prediction else "N/A",
                "weather_active": bool(weather_data and weather_data.get("success")),
                "persisted": persisted,
                "storage_backend": backend_used
            },
            "tools_called": list(set(tools_called)),
            "total_latency_ms": total_latency_ms,
            "execution_trace": trace
        }
