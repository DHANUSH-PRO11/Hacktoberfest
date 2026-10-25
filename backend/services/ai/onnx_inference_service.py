"""
AgroNex ONNX Inference Service
Handles thread-safe cached ONNX Runtime session management, verified preprocessing,
tensor validation, inference execution, and top-k class ranking for the EfficientNetV2-S model.
"""

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import onnxruntime as ort
from PIL import Image

logger = logging.getLogger(__name__)


class OnnxInferenceService:
    """
    Reusable, thread-safe ONNX inference service for the 38-class PlantVillage EfficientNetV2-S model.
    Caches the ONNX runtime session to prevent per-request reloading overhead.
    """

    _instance: Optional["OnnxInferenceService"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        model_path: Optional[str] = None,
        classes_path: Optional[str] = None,
        providers: Optional[List[str]] = None,
    ):
        base_dir = Path(__file__).resolve().parent.parent.parent
        model_dir = base_dir / "models"

        self.model_path = model_path or str(model_dir / "efficientnet_v2_s_best.onnx")
        self.classes_path = classes_path or str(model_dir / "classes.json")
        self.model_version = "efficientnet_v2_s-onnx-v1.0"

        # 1. Verify and load class labels configuration
        if not os.path.isfile(self.classes_path):
            raise FileNotFoundError(f"Class configuration not found at: {self.classes_path}")

        with open(self.classes_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.classes: List[str] = self.config["classes"]
        self.num_classes: int = len(self.classes)
        self.img_size: int = int(self.config.get("image_size", 224))
        self.mean: np.ndarray = np.array(
            self.config.get("normalisation", {}).get("mean", [0.485, 0.456, 0.406]),
            dtype=np.float32,
        )
        self.std: np.ndarray = np.array(
            self.config.get("normalisation", {}).get("std", [0.229, 0.224, 0.225]),
            dtype=np.float32,
        )

        # 2. Verify model file existence
        if not os.path.isfile(self.model_path):
            raise FileNotFoundError(
                f"EfficientNetV2-S ONNX model not found at: {self.model_path}. "
                "Ensure efficientnet_v2_s_best.onnx is present in backend/models/."
            )

        # 3. Configure ONNX Runtime Session Options
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        # Configure thread pool for low-latency CPU serving
        cpu_threads = min(4, max(1, os.cpu_count() or 2))
        opts.intra_op_num_threads = cpu_threads
        opts.inter_op_num_threads = 1

        selected_providers = providers or ["CPUExecutionProvider"]
        logger.info(
            f"Initializing ONNX session with model '{self.model_path}' using providers {selected_providers}..."
        )
        t0 = time.perf_counter()
        self.session = ort.InferenceSession(self.model_path, sess_options=opts, providers=selected_providers)
        init_ms = (time.perf_counter() - t0) * 1000.0
        logger.info(f"ONNX session loaded successfully in {init_ms:.1f} ms.")

        # 4. Inspect model inputs and outputs
        self.inputs_meta = self.session.get_inputs()
        self.outputs_meta = self.session.get_outputs()

        self.input_name = self.inputs_meta[0].name
        self.input_shape = self.inputs_meta[0].shape  # e.g. ['batch_size' or 1, 3, 224, 224]
        self.output_name = self.outputs_meta[0].name
        self.output_shape = self.outputs_meta[0].shape

        logger.info(
            f"ONNX Model Metadata: input='{self.input_name}' {self.input_shape}, "
            f"output='{self.output_name}' {self.output_shape}, classes={self.num_classes}"
        )

    @classmethod
    def get_instance(cls, **kwargs) -> "OnnxInferenceService":
        """Thread-safe singleton accessor."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(**kwargs)
        return cls._instance

    def preprocess_image(self, img: Image.Image, mode: str = "direct") -> np.ndarray:
        """
        Transforms a PIL RGB Image into an NCHW normalized float32 numpy array.
        - 'direct': Direct bilinear squish to (img_size, img_size).
        - 'letterbox': Aspect-preserving resize with ImageNet mean canvas padding [124, 116, 104].
        """
        if img.mode != "RGB":
            img = img.convert("RGB")

        if mode == "letterbox":
            w, h = img.size
            scale = self.img_size / max(w, h)
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))

            resized = img.resize((new_w, new_h), Image.Resampling.BILINEAR)

            # Canvas filled with ImageNet mean color [124, 116, 104]
            canvas = Image.new("RGB", (self.img_size, self.img_size), (124, 116, 104))
            pad_left = (self.img_size - new_w) // 2
            pad_top = (self.img_size - new_h) // 2
            canvas.paste(resized, (pad_left, pad_top))
            processed_img = canvas
        else:
            # Baseline direct squish resize
            processed_img = img.resize((self.img_size, self.img_size), Image.Resampling.BILINEAR)

        # Convert to numpy array [0.0, 1.0]
        img_array = np.array(processed_img, dtype=np.float32) / 255.0

        # Normalize with model ImageNet mean and std
        img_array = (img_array - self.mean) / self.std

        # Transpose to Channel, Height, Width (C, H, W)
        img_array = np.transpose(img_array, (2, 0, 1))

        # Add batch dimension (1, C, H, W)
        img_array = np.expand_dims(img_array, axis=0)

        return np.ascontiguousarray(img_array, dtype=np.float32)

    def _softmax(self, logits: np.ndarray) -> np.ndarray:
        """Numerically stable softmax computed along axis=1."""
        max_logits = np.max(logits, axis=1, keepdims=True)
        exp_logits = np.exp(logits - max_logits)
        return exp_logits / np.sum(exp_logits, axis=1, keepdims=True)

    def run_inference(
        self,
        input_tensor: np.ndarray,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Executes model inference on a validated input tensor.
        Returns:
            primary_prediction: Dict containing top prediction details
            top_predictions: List of top_k ranked predictions
            raw_logits: list of float raw logits for the top predictions
            is_ambiguous: bool (True if margin between top-1 and top-2 is < 0.15)
            ambiguity_margin: float difference between top-1 and top-2 scores
            inference_latency_ms: float
        """
        # Validate tensor dimensions
        if input_tensor.ndim != 4 or input_tensor.shape[1] != 3 or input_tensor.shape[2] != self.img_size or input_tensor.shape[3] != self.img_size:
            raise ValueError(
                f"Invalid input tensor shape {input_tensor.shape}. Expected (batch, 3, {self.img_size}, {self.img_size})."
            )

        if input_tensor.dtype != np.float32:
            input_tensor = input_tensor.astype(np.float32)

        t_start = time.perf_counter()
        try:
            outputs = self.session.run([self.output_name], {self.input_name: input_tensor})
        except Exception as e:
            logger.error(f"ONNX Runtime inference execution error: {e}")
            raise RuntimeError(f"ONNX inference failure: {e}") from e

        inference_latency_ms = (time.perf_counter() - t_start) * 1000.0
        raw_logits_batch = outputs[0]  # shape (batch, 38)

        if raw_logits_batch.shape[1] != self.num_classes:
            raise ValueError(
                f"Output tensor dimension {raw_logits_batch.shape[1]} does not match "
                f"expected class count {self.num_classes}."
            )

        # If batch > 1 (e.g. TTA), average probabilities across views
        probs_batch = self._softmax(raw_logits_batch)
        if probs_batch.shape[0] > 1:
            mean_probs = np.mean(probs_batch, axis=0)
            mean_logits = np.mean(raw_logits_batch, axis=0)
        else:
            mean_probs = probs_batch[0]
            mean_logits = raw_logits_batch[0]

        # Rank Top-K predictions
        top_k = min(top_k, self.num_classes)
        top_indices = np.argsort(mean_probs)[::-1][:top_k]

        ranked_predictions: List[Dict[str, Any]] = []
        for idx in top_indices:
            class_name = self.classes[idx]
            parts = class_name.split("___")
            crop = parts[0].replace("_", " ") if len(parts) > 0 else "Unknown"
            condition = parts[1].replace("_", " ") if len(parts) > 1 else class_name
            is_healthy = "healthy" in condition.lower()
            display_name = f"{crop}: {condition}"

            ranked_predictions.append({
                "class_index": int(idx),
                "class_name": class_name,
                "display_name": display_name,
                "crop": crop,
                "condition": condition,
                "confidence": float(mean_probs[idx]),
                "raw_score": float(mean_logits[idx]),
                "is_healthy": is_healthy,
            })

        best = ranked_predictions[0]

        # Check classification ambiguity margin (difference between top-1 and top-2)
        ambiguity_margin = float(ranked_predictions[0]["confidence"] - ranked_predictions[1]["confidence"]) if len(ranked_predictions) > 1 else 1.0
        is_ambiguous = ambiguity_margin < 0.15

        return {
            "primary_prediction": best,
            "top_predictions": ranked_predictions,
            "is_ambiguous": is_ambiguous,
            "ambiguity_margin": round(ambiguity_margin, 4),
            "inference_latency_ms": round(inference_latency_ms, 2),
            "model_metadata": {
                "model_name": self.config.get("model_name", "efficientnet_v2_s"),
                "model_version": self.model_version,
                "num_classes": self.num_classes,
                "input_shape": list(self.input_shape),
                "providers": self.session.get_providers(),
            },
        }
