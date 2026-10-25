from typing import Optional, List, Dict, Any, Tuple
import os
import io
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from PIL import Image
from supabase import Client

from config.database import get_supabase
from config import local_db
from schemas import schemas
from services.ai.disease_detector import DiseaseDetector
from services.ai.gemma_assistant import GemmaMultimodalAssistant
from services.weather_service import WeatherService

logger = logging.getLogger(__name__)

router = APIRouter()
detector = DiseaseDetector()
gemma_assistant = GemmaMultimodalAssistant()
weather_service = WeatherService()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit


def _validate_image_bytes(file_bytes: bytes, declared_type: str, filename: str) -> Tuple[str, int, int]:
    """
    Never trusts filename or MIME type alone.
    Validates byte signatures (magic numbers) and decodes structure using PIL.
    Returns (format, width, height) or raises HTTPException.
    """
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Uploaded image exceeds maximum allowed size of 10 MB."
        )

    # Check declared content type and extension
    if declared_type and declared_type not in ALLOWED_IMAGE_TYPES:
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format '{declared_type or ext}'. Only JPEG, PNG, and WebP leaf images are supported."
            )

    # Magic byte signature validation
    is_jpeg = file_bytes.startswith(b"\xff\xd8\xff")
    is_png = file_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    is_webp = len(file_bytes) >= 12 and file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP"

    if not (is_jpeg or is_png or is_webp):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format or invalid image file content. Only authentic JPEG, PNG, and WebP leaf photos are supported."
        )

    # Integrity verification
    try:
        with Image.open(io.BytesIO(file_bytes)) as test_img:
            test_img.verify()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Uploaded file is corrupted or damaged: {str(e)}"
        )

    # Decode dimensions and verify PIL format
    try:
        with Image.open(io.BytesIO(file_bytes)) as test_img:
            img_format = (test_img.format or "").upper()
            if img_format not in {"JPEG", "JPG", "PNG", "WEBP"}:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported decoded format '{img_format}'. Only JPEG, PNG, and WebP are allowed."
                )
            width, height = test_img.size
            return img_format, width, height
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to decode image contents: {str(e)}"
        )


@router.post("/analyze", response_model=schemas.CropAnalysisResponse)
async def analyze_crop(
    file: UploadFile = File(...),
    mode: str = Form("direct"),
    enable_tta: bool = Form(False),
    explain: bool = Form(True),
    language: str = Form("en"),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    db: Optional[Client] = Depends(get_supabase)
):
    """
    Module 1: Crop Intelligence Engine Analysis Endpoint.
    - Validates image content, byte signatures, and size (up to 10MB).
    - Executes Image Quality Gate and EfficientNetV2-S ONNX inference.
    - Interprets diagnostic uncertainty and provides photography tips.
    - Optionally generates explainable multimodal agronomic context.
    """
    filename = os.path.basename(file.filename or "leaf.jpg")
    content_type = (file.content_type or "").lower()

    # Read binary stream
    file_bytes = await file.read()

    # 1. Strict byte and integrity validation (never trust MIME/filename alone)
    img_format, img_width, img_height = _validate_image_bytes(file_bytes, content_type, filename)
    file_size_kb = len(file_bytes) / 1024
    logger.info(
        f"Processing leaf photo: {filename} ({img_width}x{img_height}, "
        f"{file_size_kb:.1f} KB, format: {img_format})"
    )

    # 2. Open-source EfficientNetV2-S ONNX Inference & Quality Assessment
    try:
        prediction = detector.predict(
            io.BytesIO(file_bytes),
            preprocessing_mode=mode,
            enable_tta=enable_tta,
            language=language
        )
    except Exception as e:
        logger.error(f"Inference failure for image {filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Crop disease diagnosis failed: {str(e)}")

    # 3. Weather Risk Intelligence Context
    lat = latitude if latitude is not None else 11.0168
    lon = longitude if longitude is not None else 76.9558
    try:
        weather_ctx = weather_service.get_weather(
            lat=lat,
            lon=lon,
            crop=prediction.get("crop"),
            condition=prediction.get("condition")
        )
    except Exception as e:
        logger.warning(f"Weather lookup during analysis failed: {e}")
        weather_ctx = None

    # 4. Gemma 4 Multimodal Explainable AI Assistant
    explanation = None
    if explain:
        try:
            explanation = gemma_assistant.explain_leaf_symptoms(
                image_bytes=file_bytes,
                image_mime=f"image/{img_format.lower()}",
                user_query=None,
                crop_context=prediction,
                weather_context=weather_ctx,
                language=language
            )
            prediction["explanation"] = explanation
        except Exception as e:
            logger.warning(f"Gemma 4 explanation generation warning: {e}")

    # 5. Persistence (Supabase Storage & Local SQLite)
    public_url = None
    saved_file_path = None
    if db is not None:
        try:
            file_name_in_storage = f"{int(datetime.now(timezone.utc).timestamp())}_{filename}"
            db.storage.from_("crop-images").upload(
                file_name_in_storage,
                file_bytes,
                {"content-type": f"image/{img_format.lower()}"}
            )
            public_url = db.storage.from_("crop-images").get_public_url(file_name_in_storage)
            db.table("crop_analyses").insert({
                "crop_type": prediction.get("crop", "Unknown"),
                "image_path": public_url,
                "detected_disease": prediction.get("condition", "Unknown"),
                "confidence": float(prediction.get("confidence", 0.0)),
                "severity": prediction.get("severity", "Not determined"),
                "risk_level": prediction.get("risk", "Not determined"),
                "quality_status": prediction.get("quality_status", "Passed"),
            }).execute()
        except Exception as e:
            logger.warning(f"Supabase persistence notice: {e}")

    try:
        # Save thumbnail in uploads directory for local preview
        os.makedirs("uploads", exist_ok=True)
        saved_file_path = f"uploads/{int(datetime.now(timezone.utc).timestamp())}_{filename}"
        with open(saved_file_path, "wb") as f_out:
            f_out.write(file_bytes)

        local_db.save_crop_analysis({
            "crop_type": prediction.get("crop", "Unknown"),
            "image_path": public_url or saved_file_path,
            "detected_disease": prediction.get("condition", "Unknown"),
            "confidence": float(prediction.get("confidence", 0.0)),
            "severity": prediction.get("severity", "Not determined"),
            "risk_level": prediction.get("risk", "Not determined"),
            "quality_status": prediction.get("quality_status", "Passed"),
            "weather_context": (
                f"{weather_ctx.get('current', {}).get('temperature', 28)}°C, Rain {weather_ctx.get('current', {}).get('precipitation', 0)}mm"
                if weather_ctx else None
            ),
            "is_inconclusive": prediction.get("is_inconclusive", False)
        })
    except Exception as e:
        logger.warning(f"Local database save notice: {e}")

    return prediction


@router.get("/stats")
def get_crop_statistics():
    """Calculates KPI metrics from actual database records (total scans, healthy, alerts, inconclusive)."""
    return local_db.get_crop_stats()


@router.get("/history", response_model=List[schemas.CropAnalysisResponse])
def get_crop_history(
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    db: Optional[Client] = Depends(get_supabase)
):
    """Retrieve history of saved crop analyses with pagination and backward-compatible fields."""
    records = []
    if db is not None:
        try:
            res = db.table("crop_analyses").select("*").order("created_at", desc=True).range(offset, offset + limit - 1).execute()
            for row in res.data or []:
                conf = float(row.get("confidence", 0.0))
                crop = row.get("crop_type", "Unknown")
                cond = row.get("detected_disease", "Unknown")
                is_healthy = "healthy" in cond.lower()
                q_status = row.get("quality_status") or "Passed"
                is_incon = (q_status != "Passed") or (conf < 0.60)
                display_name = f"{crop}: {cond}"
                class_name = f"{crop.replace(' ', '_')}___{cond.replace(' ', '_')}"

                records.append({
                    "analysis_id": str(row.get("id")),
                    "predicted_class": class_name,
                    "display_name": display_name,
                    "model_score": conf,
                    "confidence_interpretation": "Saved diagnostic record",
                    "top_predictions": [{"class_name": class_name, "confidence": conf, "display_name": display_name, "crop": crop, "condition": cond, "is_healthy": is_healthy}],
                    "quality_assessment": {"quality_status": q_status, "photography_tips": []},
                    "inconclusive": is_incon,
                    "photography_tips": [],
                    "model_version": "efficientnet_v2_s-onnx-v1.0",
                    "processing_time_ms": None,
                    "id": str(row.get("id")) if row.get("id") else None,
                    "created_at": row.get("created_at"),
                    "crop": crop,
                    "condition": cond,
                    "confidence": conf,
                    "is_healthy": is_healthy,
                    "status": "Inconclusive" if is_incon and q_status != "Passed" else ("High confidence" if conf >= 0.7 else ("Moderate confidence" if conf >= 0.6 else "Uncertain")),
                    "is_inconclusive": is_incon,
                    "disease": cond,
                    "severity": row.get("severity", "Not determined"),
                    "risk": row.get("risk_level", "Not determined"),
                    "quality_status": q_status,
                    "warning_message": None if q_status == "Passed" else f"Image quality: {q_status}",
                    "uncertainty_reason": f"Confidence ({conf*100:.1f}%) is below uncertainty threshold (60.0%)" if conf < 0.60 else None,
                    "latency_ms": None,
                    "preprocessing_mode": "direct",
                    "tta_enabled": False
                })
            if records:
                return records
        except Exception as e:
            logger.warning(f"Failed to fetch history from Supabase: {e}")

    # Fallback to local DB history
    try:
        local_records = local_db.get_recent_crop_analyses(limit=limit, offset=offset)
        for row in local_records:
            conf = float(row.get("confidence", 0.0))
            crop = row.get("crop_type", "Unknown")
            cond = row.get("detected_disease", "Unknown")
            is_healthy = "healthy" in cond.lower()
            q_status = row.get("quality_status") or "Passed"
            is_incon = bool(row.get("is_inconclusive")) or (q_status != "Passed") or (conf < 0.60)
            display_name = f"{crop}: {cond}"
            class_name = f"{crop.replace(' ', '_')}___{cond.replace(' ', '_')}"

            records.append({
                "analysis_id": str(row.get("id")),
                "predicted_class": class_name,
                "display_name": display_name,
                "model_score": conf,
                "confidence_interpretation": "Saved diagnostic record",
                "top_predictions": [{"class_name": class_name, "confidence": conf, "display_name": display_name, "crop": crop, "condition": cond, "is_healthy": is_healthy}],
                "quality_assessment": {"quality_status": q_status, "photography_tips": []},
                "inconclusive": is_incon,
                "photography_tips": [],
                "model_version": "efficientnet_v2_s-onnx-v1.0",
                "processing_time_ms": None,
                "id": str(row.get("id")) if row.get("id") else None,
                "created_at": row.get("created_at"),
                "crop": crop,
                "condition": cond,
                "confidence": conf,
                "is_healthy": is_healthy,
                "status": "Inconclusive" if is_incon and q_status != "Passed" else ("High confidence" if conf >= 0.7 else ("Moderate confidence" if conf >= 0.6 else "Uncertain")),
                "is_inconclusive": is_incon,
                "disease": cond,
                "severity": row.get("severity", "Not determined"),
                "risk": row.get("risk_level", "Not determined"),
                "quality_status": q_status,
                "warning_message": None if q_status == "Passed" else f"Image quality: {q_status}",
                "uncertainty_reason": f"Confidence ({conf*100:.1f}%) is below uncertainty threshold (60.0%)" if conf < 0.60 else None,
                "latency_ms": None,
                "preprocessing_mode": "direct",
                "tta_enabled": False
            })
    except Exception as e:
        logger.warning(f"Failed to fetch local crop history: {e}")

    return records


@router.delete("/history/{record_id}")
def delete_crop_history_record(record_id: str, db: Optional[Client] = Depends(get_supabase)):
    """Deletes a specific crop diagnosis history record."""
    deleted = False
    if db is not None:
        try:
            db.table("crop_analyses").delete().eq("id", record_id).execute()
            deleted = True
        except Exception as e:
            logger.warning(f"Failed to delete record from Supabase: {e}")

    local_deleted = local_db.delete_crop_analysis(record_id)
    if not deleted and not local_deleted:
        raise HTTPException(status_code=404, detail="Analysis record not found.")
    return {"success": True, "message": "Record deleted successfully"}
