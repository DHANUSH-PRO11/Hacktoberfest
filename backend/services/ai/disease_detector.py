"""
AgroNex Crop Disease Detector (Module 1: Crop Intelligence Engine)
Coordinates the ImageQualityService and OnnxInferenceService to provide
reliable image ingestion, preprocessing, inference, uncertainty interpretation,
and diagnostic recommendations.
"""

import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import Image

from services.ai.image_quality_service import (
    DEFAULT_QUALITY_CONFIG,
    ImageQualityService,
    PHOTOGRAPHY_TIPS,
    PHOTOGRAPHY_TIPS_TA,
)
from services.ai.onnx_inference_service import OnnxInferenceService

logger = logging.getLogger(__name__)

DEFAULT_UNCERTAINTY_THRESHOLD: float = float(os.getenv("UNCERTAINTY_THRESHOLD", "0.60"))


class DiseaseDetector:
    """
    Unified Crop Disease Diagnostic Engine.
    Integrates Image Quality Gate, ONNX Inference Service, and Configurable Uncertainty Policy.
    """

    def __init__(
        self,
        quality_config: Optional[Dict[str, Any]] = None,
        model_path: Optional[str] = None,
        classes_path: Optional[str] = None,
        uncertainty_threshold: Optional[float] = None,
    ):
        self.uncertainty_threshold = (
            uncertainty_threshold
            if uncertainty_threshold is not None
            else DEFAULT_UNCERTAINTY_THRESHOLD
        )
        self.quality_service = ImageQualityService(config=quality_config)
        self.inference_service = OnnxInferenceService.get_instance(
            model_path=model_path,
            classes_path=classes_path,
        )

        # Expose class metadata for backward compatibility
        self.classes = self.inference_service.classes
        self.img_size = self.inference_service.img_size
        self.mean = self.inference_service.mean
        self.std = self.inference_service.std
        self.session = self.inference_service.session
        self.input_name = self.inference_service.input_name
        self.output_name = self.inference_service.output_name

    def check_image_quality(
        self, img: Image.Image, language: str = "en"
    ) -> Tuple[str, Optional[str], Dict[str, Any]]:
        """
        Runs the Image Quality Service.
        Returns (quality_status, warning_message, metrics_dict) for backward compatibility.
        """
        res = self.quality_service.evaluate_quality(img, language=language)
        return res["quality_status"], res["user_facing_message"], res.get("metrics", {})

    def _load_and_orient_image(self, image_input: Any) -> Image.Image:
        """Loads and orients image via ImageQualityService."""
        return self.quality_service.load_and_orient_image(image_input)

    def _preprocess_image(self, img: Image.Image, mode: str = "direct"):
        """Preprocesses image via OnnxInferenceService."""
        return self.inference_service.preprocess_image(img, mode=mode)

    def _softmax(self, logits: Any) -> Any:
        """Numerically stable softmax."""
        return self.inference_service._softmax(logits)

    def predict(
        self,
        image_input: Any,
        preprocessing_mode: str = "direct",
        enable_tta: bool = False,
        language: str = "en",
    ) -> Dict[str, Any]:
        """
        Executes end-to-end crop diagnosis:
        1. Ingests and standardizes image (EXIF transpose, alpha compositing).
        2. Evaluates optical and botanical quality gate (ImageQualityService).
        3. Prepares normalized tensor (direct or letterbox mode).
        4. Runs cached ONNX inference with raw logits & softmax calculation.
        5. Evaluates uncertainty policy and ambiguity margins.
        6. Constructs full Module 1 contract while maintaining backward compatibility.
        """
        t_start = time.perf_counter()
        analysis_id = f"ca_{uuid.uuid4().hex[:12]}"
        is_tamil = "ta" in (language or "").lower()

        # 1. Ingest & orient image
        try:
            img = self.quality_service.load_and_orient_image(image_input)
        except Exception as e:
            logger.error(f"Image loading failed: {e}")
            raise ValueError(f"Unable to read image input: {e}") from e

        # 2. Quality Gatekeeper
        t_qual = time.perf_counter()
        quality_assessment = self.quality_service.evaluate_quality(img, language=language)
        quality_latency_ms = (time.perf_counter() - t_qual) * 1000.0
        quality_status = quality_assessment["quality_status"]
        warning_message = quality_assessment["user_facing_message"]

        # 3. Preprocess Tensor
        t_prep = time.perf_counter()
        primary_tensor = self.inference_service.preprocess_image(img, mode=preprocessing_mode)

        if enable_tta:
            import numpy as np
            flipped_img = img.transpose(Image.FLIP_LEFT_RIGHT)
            flipped_tensor = self.inference_service.preprocess_image(flipped_img, mode=preprocessing_mode)
            input_tensor = np.concatenate([primary_tensor, flipped_tensor], axis=0)
        else:
            input_tensor = primary_tensor
        preprocessing_latency_ms = (time.perf_counter() - t_prep) * 1000.0

        # 4. ONNX Inference
        t_inf = time.perf_counter()
        inference_result = self.inference_service.run_inference(input_tensor, top_k=5)
        inference_latency_ms = (time.perf_counter() - t_inf) * 1000.0

        total_latency_ms = (time.perf_counter() - t_start) * 1000.0

        primary = inference_result["primary_prediction"]
        top_preds = inference_result["top_predictions"]
        predicted_class = primary["class_name"]
        crop = primary["crop"]
        condition = primary["condition"]
        is_healthy = primary["is_healthy"]
        model_score = primary["confidence"]
        raw_score = primary["raw_score"]
        is_ambiguous = inference_result["is_ambiguous"]
        ambiguity_margin = inference_result["ambiguity_margin"]

        # 5. Uncertainty and Confidence Interpretation Policy
        # Distinguish model score (heuristic visual similarity) from clinical diagnosis.
        score_percent = model_score * 100.0
        thresh_percent = self.uncertainty_threshold * 100.0

        is_inconclusive = False
        uncertainty_reasons: List[str] = []

        if quality_status != "Passed":
            is_inconclusive = True
            uncertainty_reasons.append(
                f"Image quality issue detected: {quality_status} ({warning_message or 'poor clarity'})."
            )

        if model_score < self.uncertainty_threshold:
            is_inconclusive = True
            uncertainty_reasons.append(
                f"Model score ({score_percent:.1f}%) is below the diagnostic uncertainty threshold ({thresh_percent:.1f}%)."
            )

        if is_ambiguous and model_score < 0.70:
            is_inconclusive = True
            top2_condition = top_preds[1]["condition"] if len(top_preds) > 1 else "alternative condition"
            uncertainty_reasons.append(
                f"Ambiguous diagnosis: close match between '{condition}' and '{top2_condition}' (margin: {ambiguity_margin*100:.1f}%)."
            )

        # Construct actionable confidence interpretation
        if quality_status != "Passed":
            status = "Inconclusive"
            extra_uncertainty = (
                f" Model score ({score_percent:.1f}%) is also below the diagnostic uncertainty threshold."
                if model_score < self.uncertainty_threshold
                else ""
            )
            conf_interpretation = (
                f"Inconclusive due to image quality issues ({quality_status}).{extra_uncertainty} "
                "The visual prediction is suggestive but cannot be relied upon without a clearer photo."
                if not is_tamil else
                f"படத்தின் தெளிவின்மை காரணமாக ({quality_status}) முடிவு தெளிவற்றதாக உள்ளது. மீண்டும் தெளிவான படம் எடுக்கவும்."
            )
        elif is_inconclusive:
            status = "Uncertain"
            conf_interpretation = (
                f"Uncertain visual match ({score_percent:.1f}%). "
                "The leaf shows symptoms that overlap with multiple conditions or fall below confidence thresholds."
                if not is_tamil else
                f"தெளிவற்ற அறிகுறி ({score_percent:.1f}%). ஒன்றுக்கும் மேற்பட்ட நோய்களின் அறிகுறிகள் காணப்படலாம்."
            )
        elif score_percent >= 80.0:
            status = "High confidence"
            conf_interpretation = (
                f"High visual similarity ({score_percent:.1f}% match). "
                "Visual hypothesis matches training distribution. Confirm with local extension officers before spraying."
                if not is_tamil else
                f"அதிக காட்சிப் பொருத்தம் ({score_percent:.1f}%). கள அலுவலரிடம் சரிபார்த்து பின் மருந்திடவும்."
            )
        else:
            status = "Moderate confidence"
            conf_interpretation = (
                f"Moderate visual similarity ({score_percent:.1f}% match). "
                f"Observation is consistent with {condition}, but secondary symptoms should be monitored."
                if not is_tamil else
                f"மிதமான காட்சிப் பொருத்தம் ({score_percent:.1f}%). பயிர் மாற்றங்களை தொடர்ந்து கவனிக்கவும்."
            )

        tips = quality_assessment.get("photography_tips") or (PHOTOGRAPHY_TIPS_TA if is_tamil else PHOTOGRAPHY_TIPS)
        display_name = f"{crop}: {condition}"

        uncertainty_reason_str = " ".join(uncertainty_reasons) if uncertainty_reasons else None

        # Build combined contract (Section 7 specs + backward compatible fields)
        return {
            # === Module 1 Backend Contract Specifications ===
            "analysis_id": analysis_id,
            "predicted_class": predicted_class,
            "display_name": display_name,
            "model_score": round(model_score, 4),
            "confidence_interpretation": conf_interpretation,
            "top_predictions": top_preds,
            "quality_assessment": quality_assessment,
            "inconclusive": is_inconclusive,
            "photography_tips": tips,
            "model_version": self.inference_service.model_version,
            "processing_time_ms": round(total_latency_ms, 2),

            # === Backward Compatibility with Existing Modules & Frontends ===
            "crop": crop,
            "condition": condition,
            "confidence": round(model_score, 4),
            "is_healthy": is_healthy,
            "status": status,
            "is_inconclusive": is_inconclusive,
            "disease": condition,
            "severity": "Not determined",
            "risk": "Not determined",
            "quality_status": quality_status,
            "warning_message": warning_message,
            "uncertainty_reason": uncertainty_reason_str,
            "latency_ms": round(total_latency_ms, 2),
            "quality_check_latency_ms": round(quality_latency_ms, 3),
            "preprocessing_latency_ms": round(preprocessing_latency_ms, 3),
            "inference_latency_ms": round(inference_latency_ms, 3),
            "preprocessing_mode": preprocessing_mode,
            "tta_enabled": enable_tta,
            "is_ambiguous": is_ambiguous,
            "ambiguity_margin": ambiguity_margin,
            "raw_score": round(raw_score, 4),
        }
