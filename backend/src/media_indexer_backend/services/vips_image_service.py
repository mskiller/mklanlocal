from __future__ import annotations

from io import BytesIO
import logging
from pathlib import Path

from fastapi import HTTPException, status
from PIL import Image, ImageOps
from PIL.PngImagePlugin import PngInfo

from media_indexer_backend.schemas.image_ops import CropSpec
from media_indexer_backend.services.blurhash import encode_blurhash

try:
    import pyvips
except ImportError:  # pragma: no cover - exercised through fallback path in tests
    pyvips = None


SUPPORTED_OUTPUT_FORMATS = {
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".webp": "webp",
}


logger = logging.getLogger(__name__)


def libvips_available() -> bool:
    return pyvips is not None


def crop_output_extension(filename: str, *, default_extension: str = ".png") -> str:
    suffix = Path(filename).suffix.lower()
    return suffix if suffix in SUPPORTED_OUTPUT_FORMATS else default_extension


def _normalized_output_format(output_format: str) -> str:
    normalized = output_format.strip().lower()
    if not normalized.startswith("."):
        normalized = f".{normalized}"
    if normalized not in SUPPORTED_OUTPUT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported edited image format: {output_format}.",
        )
    return SUPPORTED_OUTPUT_FORMATS[normalized]


def _validate_crop_bounds(crop_spec: CropSpec, width: int, height: int) -> None:
    if crop_spec.crop_x + crop_spec.crop_width > width or crop_spec.crop_y + crop_spec.crop_height > height:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Crop rectangle must stay within the rotated image bounds.",
        )


def _vips_load_image(source_path: Path):
    if pyvips is None:  # pragma: no cover - guarded by caller
        raise RuntimeError("pyvips is not available.")
    return pyvips.Image.new_from_file(str(source_path), access="sequential").autorot()


def _vips_resize_to_fit(image, width: int | None, height: int | None):
    if not width and not height:
        return image
    target_width = width or image.width
    target_height = height or image.height
    scale = min(target_width / image.width, target_height / image.height)
    if scale >= 1:
        return image
    return image.resize(scale, kernel="lanczos3")


def _vips_prepare_for_output(image, output_format: str):
    if pyvips is None:  # pragma: no cover - guarded by caller
        raise RuntimeError("pyvips is not available.")
    if image.interpretation != pyvips.Interpretation.SRGB:
        image = image.colourspace("srgb")
    if output_format == "jpeg" and image.hasalpha():
        image = image.flatten(background=[255, 255, 255])
    return image


def _vips_save_to_file(image, output_path: Path, output_format: str, *, quality: int, preserve_metadata: bool) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prepared = _vips_prepare_for_output(image, output_format)
    if output_format == "jpeg":
        prepared.write_to_file(str(output_path), Q=quality, optimize_coding=True, strip=not preserve_metadata)
        return
    if output_format == "webp":
        prepared.write_to_file(str(output_path), Q=quality, strip=not preserve_metadata)
        return
    prepared.write_to_file(str(output_path), compression=6, strip=not preserve_metadata)


def _vips_write_to_buffer(image, output_format: str, *, quality: int, preserve_metadata: bool) -> bytes:
    prepared = _vips_prepare_for_output(image, output_format)
    format_string = f".{output_format}"
    if output_format == "jpeg":
        return prepared.write_to_buffer(format_string, Q=quality, optimize_coding=True, strip=not preserve_metadata)
    if output_format == "webp":
        return prepared.write_to_buffer(format_string, Q=quality, strip=not preserve_metadata)
    return prepared.write_to_buffer(format_string, compression=6, strip=not preserve_metadata)


def _vips_rotated_crop(image, crop_spec: CropSpec):
    if crop_spec.rotation_quadrants == 1:
        image = image.rot("d90")
    elif crop_spec.rotation_quadrants == 2:
        image = image.rot("d180")
    elif crop_spec.rotation_quadrants == 3:
        image = image.rot("d270")
    _validate_crop_bounds(crop_spec, image.width, image.height)
    return image.crop(crop_spec.crop_x, crop_spec.crop_y, crop_spec.crop_width, crop_spec.crop_height)


def _pillow_load_image(source_path: Path) -> Image.Image:
    with Image.open(source_path) as opened:
        image = ImageOps.exif_transpose(opened)
        image.load()
        return image.copy()


def _pillow_resize_to_fit(image: Image.Image, width: int | None, height: int | None) -> Image.Image:
    resized = image.copy()
    if width or height:
        resized.thumbnail((width or resized.width, height or resized.height), Image.Resampling.LANCZOS)
    return resized


def _pillow_metadata(image: Image.Image) -> dict:
    return {
        "exif": image.info.get("exif"),
        "icc_profile": image.info.get("icc_profile"),
        "png_text": {
            key: value
            for key, value in image.info.items()
            if isinstance(key, str) and isinstance(value, str) and key not in {"exif", "icc_profile"}
        },
    }


def _pillow_prepare_for_output(image: Image.Image, output_format: str) -> Image.Image:
    if output_format == "jpeg":
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        background.alpha_composite(rgba)
        return background.convert("RGB")
    if output_format == "webp":
        return image.convert("RGBA" if "A" in image.getbands() else "RGB")
    if output_format == "png" and image.mode == "P":
        return image.convert("RGBA")
    return image.copy()


def _pillow_save(
    image: Image.Image,
    output,
    output_format: str,
    *,
    quality: int,
    metadata: dict | None,
    preserve_metadata: bool,
) -> None:
    prepared = _pillow_prepare_for_output(image, output_format)
    save_kwargs: dict = {}
    if output_format == "jpeg":
        save_kwargs.update(format="JPEG", quality=quality, optimize=True)
    elif output_format == "webp":
        save_kwargs.update(format="WEBP", quality=quality, method=4)
    else:
        save_kwargs.update(format="PNG", compress_level=6)

    if preserve_metadata and metadata:
        if metadata.get("exif"):
            save_kwargs["exif"] = metadata["exif"]
        if metadata.get("icc_profile"):
            save_kwargs["icc_profile"] = metadata["icc_profile"]
        if output_format == "png" and metadata.get("png_text"):
            png_info = PngInfo()
            for key, value in metadata["png_text"].items():
                png_info.add_text(key, value)
            save_kwargs["pnginfo"] = png_info

    prepared.save(output, **save_kwargs)


def _pillow_rotated_crop(image: Image.Image, crop_spec: CropSpec) -> Image.Image:
    rotated = image.copy()
    if crop_spec.rotation_quadrants:
        rotated = rotated.rotate(-90 * crop_spec.rotation_quadrants, expand=True)
    _validate_crop_bounds(crop_spec, rotated.width, rotated.height)
    box = (
        crop_spec.crop_x,
        crop_spec.crop_y,
        crop_spec.crop_x + crop_spec.crop_width,
        crop_spec.crop_y + crop_spec.crop_height,
    )
    return rotated.crop(box)


def _blurhash_from_image_file(image_path: Path) -> str:
    with Image.open(image_path) as opened:
        image = ImageOps.exif_transpose(opened)
        image.load()
        blur_preview = _pillow_resize_to_fit(image, 32, 32)
        return encode_blurhash(blur_preview.convert("RGB"), x_components=4, y_components=3)


def render_preview_and_blurhash(
    source_path: Path,
    output_path: Path,
    *,
    max_size: int,
    quality: int = 88,
) -> str:
    if libvips_available():
        try:
            image = _vips_load_image(source_path)
            preview = _vips_resize_to_fit(image, max_size, max_size)
            _vips_save_to_file(preview, output_path, "jpeg", quality=quality, preserve_metadata=False)
            return _blurhash_from_image_file(output_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "libvips preview render failed; falling back to Pillow",
                extra={"source_path": str(source_path), "error": str(exc)},
            )

    image = _pillow_load_image(source_path)
    preview = _pillow_resize_to_fit(image, max_size, max_size)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _pillow_save(preview, output_path, "jpeg", quality=quality, metadata=None, preserve_metadata=False)
    blur_preview = _pillow_resize_to_fit(image, 32, 32)
    return encode_blurhash(blur_preview.convert("RGB"), x_components=4, y_components=3)


def render_resized_image_to_file(
    source_path: Path,
    output_path: Path,
    *,
    width: int | None,
    height: int | None,
    quality: int,
    fmt: str,
) -> None:
    output_format = _normalized_output_format(fmt)
    if libvips_available():
        try:
            image = _vips_load_image(source_path)
            resized = _vips_resize_to_fit(image, width, height)
            _vips_save_to_file(resized, output_path, output_format, quality=quality, preserve_metadata=False)
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "libvips resize render failed; falling back to Pillow",
                extra={"source_path": str(source_path), "error": str(exc), "format": output_format},
            )

    image = _pillow_load_image(source_path)
    resized = _pillow_resize_to_fit(image, width, height)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _pillow_save(resized, output_path, output_format, quality=quality, metadata=None, preserve_metadata=False)


def render_cropped_image_bytes(
    source_path: Path,
    crop_spec: CropSpec,
    *,
    output_format: str,
    quality: int = 92,
) -> bytes:
    normalized_format = _normalized_output_format(output_format)
    if libvips_available():
        try:
            image = _vips_load_image(source_path)
            cropped = _vips_rotated_crop(image, crop_spec)
            return _vips_write_to_buffer(cropped, normalized_format, quality=quality, preserve_metadata=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "libvips crop render failed; falling back to Pillow",
                extra={"source_path": str(source_path), "error": str(exc), "format": normalized_format},
            )

    image = _pillow_load_image(source_path)
    metadata = _pillow_metadata(image)
    cropped = _pillow_rotated_crop(image, crop_spec)
    buffer = BytesIO()
    _pillow_save(cropped, buffer, normalized_format, quality=quality, metadata=metadata, preserve_metadata=True)
    return buffer.getvalue()
