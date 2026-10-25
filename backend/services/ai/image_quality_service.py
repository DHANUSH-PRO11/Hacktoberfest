"""
AgroNex Image Quality Assessment Service
Evaluates input leaf photos for optical and botanical suitability:
- Minimum resolution (width, height)
- Illumination extremes (underexposure / low light, overexposure / glare)
- Sharpness and motion blur via 2D discrete Laplacian variance
- Botanical texture and color variance (without arbitrary green-only foliage assumptions)
- Actionable photography guidance for farmers
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Configurable heuristic threshold defaults
DEFAULT_QUALITY_CONFIG: Dict[str, Any] = {
    "enable_quality_gate": True,
    "min_image_width": 100,           # Recommended minimum width in pixels
    "min_image_height": 100,          # Recommended minimum height in pixels
    "blur_laplacian_threshold": 60.0, # Baseline focus threshold via discrete Laplacian variance
    "darkness_mean_threshold": 40.0,   # Minimum mean luminance (0-255 scale)
    "overexposure_clip_ratio": 0.25,   # Maximum fraction of pixels with luminance > 245
    "min_texture_std": 12.0,          # Minimum luminance standard deviation (detects flat blank walls/surfaces)
    "foliage_min_pixel_ratio": 0.05,  # Baseline minimum foliage pixel ratio
}

PHOTOGRAPHY_TIPS: List[str] = [
    "Lighting: Take photos in bright, natural daytime light. Avoid direct harsh flash or deep shadows.",
    "Focus: Hold the smartphone steady. Tap the screen to focus sharply on the affected leaf spots or lesions.",
    "Orientation: Position the leaf flat so it fills at least 70% of the camera frame.",
    "Background: Place the leaf against a neutral background (or the palm of your hand) to reduce background clutter."
]

PHOTOGRAPHY_TIPS_TA: List[str] = [
    "வெளிச்சம்: பிரகாசமான இயற்கை பகல் வெளிச்சத்தில் படம் எடுக்கவும். கடுமையான நிழல்கள் அல்லது ஃப்ளாஷ் வெளிச்சத்தை தவிர்க்கவும்.",
    "கவனம் (Focus): கேமராவை அசைக்காமல் வைக்கவும். பாதிக்கப்பட்ட இலை புள்ளிகள் மீது திரையைத் தொட்டு ஃபோகஸ் செய்யவும்.",
    "அமைவு: இலை கேமரா திரையில் குறைந்தது 70% இடத்தை நிரப்புமாறு நேராகப் பிடிக்கவும்.",
    "பின்னணி: இலை தெளிவாகத் தெரிய உங்கள் உள்ளங்கையிலோ அல்லது வெற்றுப் பின்னணியிலோ வைக்கவும்."
]


class ImageQualityService:
    """
    Reusable image quality evaluation service for agricultural leaf diagnosis.
    Inspects resolution, illumination, blur, and texture without hard-rejecting
    valid leaves with unusual colors, backgrounds, or lighting.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = dict(DEFAULT_QUALITY_CONFIG)
        if config:
            self.config.update(config)

    def load_and_orient_image(self, image_input: Union[str, bytes, Image.Image, Any]) -> Image.Image:
        """
        Safely loads an image, applies EXIF rotation tags,
        and standardizes alpha/palette modes over a neutral canvas.
        """
        if isinstance(image_input, Image.Image):
            img = image_input
        elif isinstance(image_input, (bytes, bytearray)):
            import io
            img = Image.open(io.BytesIO(image_input))
        else:
            img = Image.open(image_input)

        # Correct EXIF rotation (smartphones frequently store rotation flags)
        try:
            img = ImageOps.exif_transpose(img)
        except Exception as e:
            logger.debug(f"EXIF transpose skipped: {e}")

        # Safe color mode normalization:
        # RGBA / LA / P with transparency composite over neutral grey (240, 240, 240)
        # to prevent black halo artifacts around cutout leaves
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGBA')
            canvas = Image.new('RGB', img.size, (240, 240, 240))
            canvas.paste(img, mask=img.split()[3])
            return canvas
        elif img.mode == 'CMYK':
            return img.convert('RGB')
        elif img.mode != 'RGB':
            return img.convert('RGB')

        return img

    def evaluate_quality(
        self,
        image_input: Union[str, bytes, Image.Image, Any],
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Runs comprehensive image quality checks and returns a structured assessment.
        Returns:
            quality_status: "Passed" | "Warning" | "Degraded"
            quality_score: float in [0.0, 1.0] representing empirical image quality index
            detected_issues: list of issue dicts {"code", "severity", "message"}
            user_facing_message: summary explanation
            photography_tips: actionable guidance
            metrics: raw measurement dictionary
        """
        is_tamil = "ta" in (language or "").lower()
        tips = PHOTOGRAPHY_TIPS_TA if is_tamil else PHOTOGRAPHY_TIPS

        try:
            img = self.load_and_orient_image(image_input)
        except Exception as e:
            logger.error(f"Failed to decode image in quality service: {e}")
            return {
                "quality_status": "Degraded",
                "quality_score": 0.0,
                "detected_issues": [{
                    "code": "INVALID_IMAGE",
                    "severity": "critical",
                    "message": f"Image decoding error: {str(e)}"
                }],
                "user_facing_message": "Uploaded file is corrupted or not a readable image format." if not is_tamil else "பதிவேற்றப்பட்ட கோப்பு செல்லுபடியாகாத படம்.",
                "photography_tips": tips,
                "metrics": {}
            }

        if not self.config.get("enable_quality_gate", True):
            return {
                "quality_status": "Passed",
                "quality_score": 1.0,
                "detected_issues": [],
                "user_facing_message": None,
                "photography_tips": tips,
                "metrics": {"width": img.width, "height": img.height}
            }

        w, h = img.size
        min_w = self.config["min_image_width"]
        min_h = self.config["min_image_height"]

        detected_issues: List[Dict[str, Any]] = []
        penalties = 0.0

        # 1. Dimension Check
        if w < min_w or h < min_h:
            msg = (
                f"Image resolution ({w}x{h}) is below the recommended minimum "
                f"({min_w}x{min_h}). A higher-resolution photo is recommended."
                if not is_tamil else
                f"படத்தின் அளவு ({w}x{h}) மிகவும் குறைவாக உள்ளது (பரிந்துரை: {min_w}x{min_h}+)."
            )
            detected_issues.append({
                "code": "LOW_RESOLUTION",
                "severity": "warning",
                "message": msg
            })
            penalties += 0.35

        arr = np.array(img, dtype=np.float32)
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

        # Luminance channel Y (ITU-R BT.601 standards)
        lum = 0.299 * r + 0.587 * g + 0.114 * b

        # Studio background separation:
        # Lab benchmarks (e.g. PlantVillage) use uniform near-white backgrounds (>235 across RGB).
        # We isolate the leaf region from studio borders to prevent false overexposure alarms.
        is_studio_white = (r > 235.0) & (g > 235.0) & (b > 235.0)
        white_ratio = float(np.mean(is_studio_white))
        if 0.15 <= white_ratio <= 0.85:
            target_mask = ~is_studio_white
        else:
            target_mask = np.ones_like(lum, dtype=bool)

        if np.any(target_mask):
            mean_lum = float(np.mean(lum[target_mask]))
            clip_ratio = float(np.mean(lum[target_mask] > 245.0))
            lum_std = float(np.std(lum[target_mask]))
        else:
            mean_lum = float(np.mean(lum))
            clip_ratio = float(np.mean(lum > 245.0))
            lum_std = float(np.std(lum))

        # 2. Darkness / Underexposure Check
        dark_thresh = self.config["darkness_mean_threshold"]
        if mean_lum < dark_thresh:
            msg = (
                f"Image appears underexposed (mean luminance {mean_lum:.1f} < {dark_thresh:.1f}). "
                "Better natural lighting is recommended."
                if not is_tamil else
                f"படம் போதுமான வெளிச்சம் இல்லாமல் இருட்டாக உள்ளது (வெளிச்சம் {mean_lum:.1f} < {dark_thresh:.1f})."
            )
            detected_issues.append({
                "code": "LOW_LIGHT",
                "severity": "warning",
                "message": msg
            })
            penalties += min(0.40, (dark_thresh - mean_lum) / dark_thresh * 0.40)

        # 3. Overexposure / Glare Check
        glare_thresh = self.config["overexposure_clip_ratio"]
        if clip_ratio > glare_thresh:
            msg = (
                f"Surface glare/overexposure detected ({clip_ratio * 100:.1f}% clipped pixels). "
                "Avoid harsh direct flash or specular reflections."
                if not is_tamil else
                f"படத்தில் அதிகப்படியான ஒளி பிரதிபலிப்பு/மினுமினுப்பு உள்ளது ({clip_ratio * 100:.1f}%)."
            )
            detected_issues.append({
                "code": "OVEREXPOSED",
                "severity": "warning",
                "message": msg
            })
            penalties += min(0.35, clip_ratio * 0.5)

        # 4. Sharpness / Blur Detection (2D discrete Laplacian variance)
        blur_thresh = self.config["blur_laplacian_threshold"]
        if lum.shape[0] >= 3 and lum.shape[1] >= 3:
            lap = lum[:-2, 1:-1] + lum[2:, 1:-1] + lum[1:-1, :-2] + lum[1:-1, 2:] - 4.0 * lum[1:-1, 1:-1]
            blur_var = float(np.var(lap))
        else:
            blur_var = 0.0

        if blur_var < blur_thresh:
            msg = (
                f"Image appears out of focus or blurry (Laplacian variance {blur_var:.1f} < {blur_thresh:.1f}). "
                "A sharper photo is recommended."
                if not is_tamil else
                f"படம் மங்கலாக (blur) உள்ளது. கேமராவை அசைக்காமல் தெளிவாக படம் எடுக்கவும்."
            )
            detected_issues.append({
                "code": "BLUR_DETECTED",
                "severity": "warning",
                "message": msg
            })
            penalties += min(0.40, (blur_thresh - blur_var) / blur_thresh * 0.40)

        # 5. Botanical Texture & Foliage Presence
        foliage_thresh = self.config.get("foliage_min_pixel_ratio", 0.05)
        exg = 2.0 * g - r - b
        foliage_pixels = (exg > 10.0) & (g > 30.0)
        foliage_ratio = float(np.mean(foliage_pixels))

        min_texture_std = self.config["min_texture_std"]
        if foliage_ratio < foliage_thresh and not (0.15 <= white_ratio <= 0.85):
            msg = (
                f"Low vegetation/foliage detected ({foliage_ratio * 100:.1f}% green pixels). "
                "Ensure the crop leaf fills most of the frame."
                if not is_tamil else
                "படத்தில் பயிர் இலை அமைப்பு குறைவாக உள்ளது. இலையை பெரிதாக காட்டவும்."
            )
            detected_issues.append({
                "code": "LOW_FOLIAGE",
                "severity": "info",
                "message": msg
            })
            penalties += 0.25
        elif lum_std < min_texture_std:
            msg = (
                f"Very low visual texture detected (contrast std {lum_std:.1f} < {min_texture_std:.1f}). "
                "Ensure the crop leaf fills the camera frame."
                if not is_tamil else
                "படத்தில் பயிர் இலை அமைப்பு தெளிவாக தெரியவில்லை. இலையை பெரிதாக காட்டவும்."
            )
            detected_issues.append({
                "code": "LOW_TEXTURE",
                "severity": "info",
                "message": msg
            })
            penalties += 0.20

        # Empirical quality score in range [0.05, 1.0]
        quality_score = max(0.05, min(1.0, 1.0 - penalties))

        # Overall Status
        if not detected_issues:
            quality_status = "Passed"
            user_facing_message = None
        elif any(issue["severity"] == "critical" for issue in detected_issues):
            quality_status = "Degraded"
            user_facing_message = detected_issues[0]["message"]
        else:
            primary_code = detected_issues[0]["code"]
            if primary_code == "BLUR_DETECTED":
                quality_status = "Warning: Mild Blur"
            elif primary_code == "LOW_LIGHT":
                quality_status = "Warning: Low Light"
            elif primary_code == "LOW_RESOLUTION":
                quality_status = "Warning: Low Resolution"
            elif primary_code == "OVEREXPOSED":
                quality_status = "Warning: Overexposed"
            elif primary_code == "LOW_FOLIAGE":
                quality_status = "Warning: Low Foliage"
            elif primary_code == "LOW_TEXTURE":
                quality_status = "Warning: Low Texture"
            else:
                quality_status = f"Warning: {primary_code.replace('_', ' ').title()}"
            user_facing_message = detected_issues[0]["message"]

        return {
            "quality_status": quality_status,
            "quality_score": round(quality_score, 3),
            "detected_issues": detected_issues,
            "user_facing_message": user_facing_message,
            "photography_tips": tips,
            "metrics": {
                "width": w,
                "height": h,
                "mean_luminance": round(mean_lum, 2),
                "clip_ratio": round(clip_ratio, 4),
                "blur_variance": round(blur_var, 2),
                "luminance_std": round(lum_std, 2)
            }
        }
