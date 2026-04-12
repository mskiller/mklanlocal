from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from shutil import rmtree
from uuid import UUID

from PIL import Image

from media_indexer_backend.core.config import get_settings
from media_indexer_backend.models.enums import MediaType
from media_indexer_backend.services.blurhash import encode_blurhash
from media_indexer_backend.services.deepzoom import deepzoom_manifest_absolute_path, deepzoom_tiles_absolute_dir


logger = logging.getLogger(__name__)


class PreviewGenerator:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.settings.preview_root_path.mkdir(parents=True, exist_ok=True)

    def deepzoom_exists(self, asset_id: UUID) -> bool:
        return deepzoom_manifest_absolute_path(asset_id, self.settings.preview_root_path).exists()

    def cleanup(self, asset_id: UUID, preview_path: str | None) -> None:
        if preview_path:
            (self.settings.preview_root_path / preview_path).unlink(missing_ok=True)
        manifest_path = deepzoom_manifest_absolute_path(asset_id, self.settings.preview_root_path)
        tiles_dir = deepzoom_tiles_absolute_dir(asset_id, self.settings.preview_root_path)
        manifest_path.unlink(missing_ok=True)
        if tiles_dir.exists():
            rmtree(tiles_dir, ignore_errors=True)

    def generate(self, asset_id: UUID, media_type: MediaType, source_path: Path) -> tuple[str | None, str | None]:
        output_name = f"{asset_id}.jpg"
        output_path = self.settings.preview_root_path / output_name
        blur_hash: str | None = None
        try:
            if media_type == MediaType.IMAGE:
                with Image.open(source_path) as image:
                    image = image.convert("RGB")
                    preview_image = image.copy()
                    preview_image.thumbnail((self.settings.max_thumbnail_size, self.settings.max_thumbnail_size))
                    preview_image.save(output_path, format="JPEG", quality=88)

                    blur_image = image.copy()
                    blur_image.thumbnail((32, 32))
                    blur_hash = encode_blurhash(blur_image, x_components=4, y_components=3)
            elif media_type == MediaType.VIDEO:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(source_path),
                        "-ss",
                        "00:00:01",
                        "-frames:v",
                        "1",
                        str(output_path),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            else:
                return None, None
        except Exception as exc:  # noqa: BLE001
            logger.warning("preview generation failed", extra={"source_path": str(source_path), "error": str(exc)})
            return None, None

        manifest_path = deepzoom_manifest_absolute_path(asset_id, self.settings.preview_root_path)
        tiles_dir = deepzoom_tiles_absolute_dir(asset_id, self.settings.preview_root_path)
        manifest_path.unlink(missing_ok=True)
        if tiles_dir.exists():
            rmtree(tiles_dir, ignore_errors=True)

        return (output_name if output_path.exists() else None), blur_hash
