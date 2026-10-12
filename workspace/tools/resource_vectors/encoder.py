"""Optional local Transformers CLIP image/text encoder."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

try:
    import torch
    from transformers import AutoModel, AutoProcessor
except ImportError:  # Optional dependency; reported when the encoder is requested.
    torch = None
    AutoModel = None
    AutoProcessor = None


class ModelUnavailableError(RuntimeError):
    """The requested encoder cannot be loaded under the offline policy."""


def _feature_tensor(value):
    """Extract a tensor across Transformers CLIP return-value variants."""
    if torch is not None and torch.is_tensor(value):
        return value
    for name in ("image_embeds", "text_embeds", "pooler_output"):
        candidate = getattr(value, name, None)
        if torch is not None and torch.is_tensor(candidate):
            return candidate
    raise TypeError(f"unsupported CLIP feature output: {type(value).__name__}")


class TransformersClipEncoder:
    def __init__(
        self,
        model_id: str = "openai/clip-vit-base-patch32",
        *,
        revision: str = "main",
        allow_download: bool = False,
    ):
        self.model_id = model_id
        self.revision = revision
        if AutoModel is None or AutoProcessor is None or torch is None:
            raise ModelUnavailableError(
                "transformers/torch is unavailable; install dependencies and provide a local model"
            )
        local_only = not allow_download
        try:
            self.model = AutoModel.from_pretrained(
                model_id, revision=revision, local_files_only=local_only
            )
            self.processor = AutoProcessor.from_pretrained(
                model_id, revision=revision, local_files_only=local_only
            )
            self.model.eval()
        except (OSError, ValueError) as error:
            action = (
                "check network/cache access"
                if allow_download
                else "rerun with --allow-model-download when network access is approved"
            )
            raise ModelUnavailableError(
                f"model {model_id}@{revision} unavailable: {error}; {action}"
            ) from error

    def encode_images(self, paths: Sequence[Path]) -> np.ndarray:
        images = []
        try:
            for path in paths:
                with Image.open(path) as source:
                    images.append(source.convert("RGB"))
            inputs = self.processor(images=images, return_tensors="pt", padding=True)
            with torch.inference_mode():
                vectors = _feature_tensor(self.model.get_image_features(**inputs))
            return vectors.detach().cpu().numpy().astype(np.float32)
        finally:
            for image in images:
                image.close()

    def encode_text(self, text: str) -> np.ndarray:
        inputs = self.processor(text=[text], return_tensors="pt", padding=True)
        with torch.inference_mode():
            vector = _feature_tensor(self.model.get_text_features(**inputs))
        return vector[0].detach().cpu().numpy().astype(np.float32)


__all__ = ["ModelUnavailableError", "TransformersClipEncoder"]
