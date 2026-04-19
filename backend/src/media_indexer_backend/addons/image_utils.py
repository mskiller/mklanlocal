from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageFont, ImageOps, PngImagePlugin

from media_indexer_backend.addons.registry import AddonExecutionContext
from media_indexer_backend.models.enums import MediaType
from media_indexer_backend.models.tables import Asset
from media_indexer_backend.services.path_safety import resolve_asset_path


RESAMPLING = getattr(Image, "Resampling", Image)


@dataclass(slots=True)
class EncodedImage:
    content: bytes
    extension: str
    mime_type: str


def option(context: AddonExecutionContext, key: str, default: Any) -> Any:
    value = context.params_json.get(key)
    if value is None or value == "":
        value = context.module_settings.get(key, default)
    return default if value is None or value == "" else value


def asset_stem(filename: str) -> str:
    return Path(filename).stem or "artifact"


def ensure_image_asset(asset: Asset, module_id: str) -> None:
    if asset.media_type != MediaType.IMAGE:
        raise ValueError(f"{module_id} only supports image assets.")
    if asset.source is None:
        raise ValueError(f"{module_id} requires assets with a mounted source.")


def load_asset_image(asset: Asset, module_id: str) -> tuple[Path, Image.Image]:
    ensure_image_asset(asset, module_id)
    source_path = resolve_asset_path(asset.source.root_path, asset.relative_path)
    with Image.open(source_path) as image:
        prepared = ImageOps.exif_transpose(image)
        if prepared.mode not in {"RGB", "RGBA", "L"}:
            target_mode = "RGBA" if "A" in prepared.getbands() else "RGB"
            prepared = prepared.convert(target_mode)
        else:
            prepared = prepared.copy()
    return source_path, prepared


def clamp_image_size(image: Image.Image, max_input_size: int | None) -> Image.Image:
    if not max_input_size or max(image.size) <= max_input_size:
        return image
    scale = max_input_size / max(image.size)
    resized = image.resize(
        (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
        RESAMPLING.LANCZOS,
    )
    return resized


def output_format(context: AddonExecutionContext, default: str) -> str:
    value = str(option(context, "output_format", default)).strip().lower()
    if value in {"jpg", "jpeg"}:
        return "jpeg"
    if value in {"png", "webp"}:
        return value
    return default


def output_quality(context: AddonExecutionContext, default: int = 92) -> int:
    try:
        quality = int(option(context, "quality", default))
    except (TypeError, ValueError):
        return default
    return max(30, min(100, quality))


def encode_image(
    image: Image.Image,
    fmt: str,
    *,
    quality: int = 92,
    pnginfo: PngImagePlugin.PngInfo | None = None,
    exif: Image.Exif | None = None,
) -> EncodedImage:
    normalized = fmt.lower()
    extension = "jpg" if normalized == "jpeg" else normalized
    mime_type = {
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }[normalized]
    save_kwargs: dict[str, Any] = {}
    output_image = image
    if normalized == "jpeg":
        output_image = image.convert("RGB")
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
    elif normalized == "webp":
        save_kwargs["quality"] = quality
        save_kwargs["method"] = 6
    if pnginfo is not None and normalized == "png":
        save_kwargs["pnginfo"] = pnginfo
    if exif is not None and normalized in {"jpeg", "webp"} and len(exif):
        save_kwargs["exif"] = exif

    buffer = BytesIO()
    output_image.save(buffer, format=normalized.upper(), **save_kwargs)
    return EncodedImage(content=buffer.getvalue(), extension=extension, mime_type=mime_type)


def parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def parse_hex_color(value: Any, default: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    if not isinstance(value, str):
        return default
    cleaned = value.strip().lstrip("#")
    if len(cleaned) not in {6, 8}:
        return default
    try:
        if len(cleaned) == 6:
            red = int(cleaned[0:2], 16)
            green = int(cleaned[2:4], 16)
            blue = int(cleaned[4:6], 16)
            return red, green, blue, 255
        red = int(cleaned[0:2], 16)
        green = int(cleaned[2:4], 16)
        blue = int(cleaned[4:6], 16)
        alpha = int(cleaned[6:8], 16)
        return red, green, blue, alpha
    except ValueError:
        return default


def default_font():
    return ImageFont.load_default()
