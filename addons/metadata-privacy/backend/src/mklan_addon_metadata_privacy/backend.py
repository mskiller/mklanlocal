from __future__ import annotations

import json

from PIL import ExifTags, Image, PngImagePlugin

from media_indexer_backend.addons import AddonDefinition, AddonPresetSeed, GeneratedArtifact, register_addon_definition
from media_indexer_backend.addons.image_utils import (
    asset_stem,
    clamp_image_size,
    encode_image,
    load_asset_image,
    option,
    output_format,
    output_quality,
    parse_bool,
)


EXIF_NAME_BY_ID = {tag_id: name for tag_id, name in ExifTags.TAGS.items()}
PNG_PROMPT_KEYS = {"parameters", "prompt", "workflow", "comment", "description"}


def _profile_keep_names(profile: str) -> set[str]:
    if profile == "camera_only":
        return {
            "Make",
            "Model",
            "LensModel",
            "FNumber",
            "ExposureTime",
            "FocalLength",
            "ISOSpeedRatings",
            "DateTimeOriginal",
        }
    if profile == "full":
        return set(EXIF_NAME_BY_ID.values())
    return set()


def _filtered_exif(image: Image.Image, *, profile: str, preserve_gps: bool) -> tuple[Image.Exif | None, list[str], list[str]]:
    exif = image.getexif()
    if not exif:
        return None, [], []

    keep_names = _profile_keep_names(profile)
    next_exif = Image.Exif()
    preserved: list[str] = []
    removed: list[str] = []
    for tag_id, value in exif.items():
        tag_name = EXIF_NAME_BY_ID.get(tag_id, str(tag_id))
        if tag_name == "GPSInfo" and not preserve_gps:
            removed.append(tag_name)
            continue
        if profile == "full" or tag_name in keep_names:
            next_exif[tag_id] = value
            preserved.append(tag_name)
        else:
            removed.append(tag_name)
    return next_exif, preserved, removed


def _filtered_pnginfo(image: Image.Image, *, preserve_prompt: bool, profile: str) -> tuple[PngImagePlugin.PngInfo | None, list[str], list[str]]:
    kept: list[str] = []
    removed: list[str] = []
    pnginfo = PngImagePlugin.PngInfo()
    for key, value in image.info.items():
        normalized_key = str(key).strip().lower()
        should_keep = profile == "full" or (preserve_prompt and normalized_key in PNG_PROMPT_KEYS)
        if isinstance(value, str) and should_keep:
            pnginfo.add_text(key, value)
            kept.append(key)
        elif isinstance(value, str):
            removed.append(key)
    if not kept:
        return None, kept, removed
    return pnginfo, kept, removed


def _process(context, asset):
    source_path, image = load_asset_image(asset, context.module_id)
    image = clamp_image_size(image, int(option(context, "max_input_size", 4096)))
    image = image.copy()
    image.info.clear()
    with Image.open(source_path) as original:
        profile = str(option(context, "preserve_profile", "share_safe")).strip().lower()
        preserve_gps = parse_bool(option(context, "preserve_gps", False), False)
        preserve_prompt = parse_bool(option(context, "preserve_prompt", False), False)
        next_exif, exif_preserved, exif_removed = _filtered_exif(original, profile=profile, preserve_gps=preserve_gps)
        next_pnginfo, png_preserved, png_removed = _filtered_pnginfo(original, preserve_prompt=preserve_prompt, profile=profile)

    requested_format = output_format(context, "png")
    if requested_format == "png":
        encoded = encode_image(image, "png", pnginfo=next_pnginfo)
    else:
        encoded = encode_image(image, requested_format, quality=output_quality(context), exif=next_exif)

    report = {
        "profile": profile,
        "preserve_gps": preserve_gps,
        "preserve_prompt": preserve_prompt,
        "preserved_exif_fields": sorted(exif_preserved),
        "removed_exif_fields": sorted(exif_removed),
        "preserved_text_fields": sorted(png_preserved),
        "removed_text_fields": sorted(png_removed),
    }
    stem = asset_stem(asset.filename)
    return [
        GeneratedArtifact(
            filename=f"{stem}-sanitized.{encoded.extension}",
            content=encoded.content,
            mime_type=encoded.mime_type,
            label="Sanitized Export",
            asset_id=str(asset.id),
            width=image.width,
            height=image.height,
            metadata_json=report,
        ),
        GeneratedArtifact(
            filename=f"{stem}-metadata-report.json",
            content=(json.dumps(report, indent=2) + "\n").encode("utf-8"),
            mime_type="application/json",
            label="Metadata Report",
            asset_id=str(asset.id),
            metadata_json={"json_report": True, **report},
        ),
    ]


def register() -> None:
    register_addon_definition(
        AddonDefinition(
            module_id="metadata_privacy",
            name="Metadata Privacy",
            description="Inspect, strip, and selectively preserve metadata for share-safe derivatives.",
            supports_asset=True,
            supports_batch=True,
            supports_collection=False,
            default_presets=[
                AddonPresetSeed(
                    name="Share Safe",
                    description="Strip GPS, prompt metadata, and most EXIF fields.",
                    config_json={"preserve_profile": "share_safe", "preserve_gps": False, "preserve_prompt": False, "output_format": "png"},
                ),
                AddonPresetSeed(
                    name="Camera Only",
                    description="Keep camera-facing EXIF fields but drop GPS and prompt metadata.",
                    config_json={"preserve_profile": "camera_only", "preserve_gps": False, "preserve_prompt": False, "output_format": "jpeg"},
                ),
                AddonPresetSeed(
                    name="Prompt Review",
                    description="Keep PNG prompt/workflow text for internal draft review.",
                    config_json={"preserve_profile": "share_safe", "preserve_gps": False, "preserve_prompt": True, "output_format": "png"},
                ),
            ],
            per_asset_processor=_process,
        )
    )
