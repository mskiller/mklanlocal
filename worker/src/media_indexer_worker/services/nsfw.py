from __future__ import annotations

import logging
from pathlib import Path

from media_indexer_backend.core.config import get_settings

logger = logging.getLogger(__name__)


class NsfwDetectorService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._pipeline = None
        self._load_failed = False

    def _load(self) -> bool:
        if not self.settings.nsfw_detector_enabled:
            return False
        if self._load_failed:
            return False
        if self._pipeline is not None:
            return True
        try:
            from transformers import pipeline

            # pipeline will automatically download the model on first launch
            self._pipeline = pipeline("image-classification", model=self.settings.nsfw_model_id)
            return True
        except Exception as exc:  # noqa: BLE001
            self._load_failed = True
            logger.warning("nsfw model unavailable: %s", exc, extra={"error": str(exc)}, exc_info=True)
            return False

    def detect_nsfw(self, path: Path) -> bool:
        if not self._load():
            return False
        assert self._pipeline is not None
        try:
            from PIL import Image

            with Image.open(path) as image:
                image = image.convert("RGB")
                results = self._pipeline(image)
                # results is typically: [{'label': 'nsfw', 'score': 0.99}, {'label': 'normal', 'score': 0.01}]
                for result in results:
                    if result["label"].lower() == "nsfw" and result["score"] > 0.6:
                        return True
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("nsfw detection failed: %s", exc, extra={"path": str(path), "error": str(exc)}, exc_info=True)
            return False
