from __future__ import annotations

import json

from PIL import Image, ImageDraw, ImageFilter

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
    parse_float,
    parse_hex_color,
)


def _resolve_rect(rect: dict, width: int, height: int) -> tuple[int, int, int, int]:
    x = rect.get("x", 0)
    y = rect.get("y", 0)
    rect_width = rect.get("width", 0)
    rect_height = rect.get("height", 0)
    if all(isinstance(value, (int, float)) and 0 <= float(value) <= 1 for value in [x, y, rect_width, rect_height]):
        left = int(float(x) * width)
        top = int(float(y) * height)
        right = int(float(x + rect_width) * width)
        bottom = int(float(y + rect_height) * height)
    else:
        left = int(float(x))
        top = int(float(y))
        right = int(float(x) + float(rect_width))
        bottom = int(float(y) + float(rect_height))
    return max(0, left), max(0, top), min(width, right), min(height, bottom)


def _mask_rectangles(mask_rects, width: int, height: int, feather_radius: float):
    mask = Image.new("L", (width, height), 0)
    drawer = ImageDraw.Draw(mask)
    resolved = []
    for rect in mask_rects:
        left, top, right, bottom = _resolve_rect(rect, width, height)
        if right <= left or bottom <= top:
            continue
        drawer.rectangle((left, top, right, bottom), fill=255)
        resolved.append({"left": left, "top": top, "right": right, "bottom": bottom})
    if feather_radius > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=feather_radius))
    return mask, resolved


def _process(context, asset):
    _, image = load_asset_image(asset, context.module_id)
    image = clamp_image_size(image, int(option(context, "max_input_size", 4096))).convert("RGBA")
    mask_rects = option(context, "mask_rects", [])
    if not isinstance(mask_rects, list) or not mask_rects:
        raise ValueError("object_erase requires params_json.mask_rects with one or more rectangles.")

    feather_radius = max(0.0, min(16.0, parse_float(option(context, "feather_radius", 6.0), 6.0)))
    fill_mode = str(option(context, "fill_mode", "blur")).strip().lower()
    export_mask = parse_bool(option(context, "export_mask", True), True)
    fill_color = parse_hex_color(option(context, "fill_color", "#f2f2f2"), (242, 242, 242, 255))

    mask_image, resolved_rects = _mask_rectangles(mask_rects, image.width, image.height, feather_radius)
    if not resolved_rects:
        raise ValueError("object_erase did not receive any valid mask rectangles.")

    if fill_mode == "solid":
        fill_layer = Image.new("RGBA", image.size, fill_color)
    else:
        fill_layer = image.filter(ImageFilter.GaussianBlur(radius=max(12.0, feather_radius * 3.0)))

    erased = image.copy()
    erased.paste(fill_layer, mask=mask_image)
    requested_format = output_format(context, "png")
    encoded_erased = encode_image(erased, requested_format, quality=output_quality(context))

    artifacts = [
        GeneratedArtifact(
            filename=f"{asset_stem(asset.filename)}-erase.{encoded_erased.extension}",
            content=encoded_erased.content,
            mime_type=encoded_erased.mime_type,
            label="Erased Draft",
            asset_id=str(asset.id),
            width=erased.width,
            height=erased.height,
            metadata_json={
                "fill_mode": fill_mode,
                "mask_rects": resolved_rects,
                "feather_radius": feather_radius,
            },
        )
    ]

    if export_mask:
        encoded_mask = encode_image(mask_image, "png")
        artifacts.append(
            GeneratedArtifact(
                filename=f"{asset_stem(asset.filename)}-erase-mask.png",
                content=encoded_mask.content,
                mime_type=encoded_mask.mime_type,
                label="Saved Mask",
                asset_id=str(asset.id),
                width=mask_image.width,
                height=mask_image.height,
                metadata_json={"mask_rects": resolved_rects},
            )
        )

    artifacts.append(
        GeneratedArtifact(
            filename=f"{asset_stem(asset.filename)}-erase-report.json",
            content=(json.dumps({"mask_rects": resolved_rects, "fill_mode": fill_mode, "feather_radius": feather_radius}, indent=2) + "\n").encode("utf-8"),
            mime_type="application/json",
            label="Replay Params",
            asset_id=str(asset.id),
            metadata_json={"json_report": True},
        )
    )
    return artifacts


def register() -> None:
    register_addon_definition(
        AddonDefinition(
            module_id="object_erase",
            name="Object Erase",
            description="Apply saved rectangle masks and generate erased draft variants for review.",
            supports_asset=True,
            supports_batch=True,
            supports_collection=False,
            default_presets=[
                AddonPresetSeed(
                    name="Soft Blur Fill",
                    description="Blur-fill masked rectangles and keep a replayable mask artifact.",
                    config_json={"fill_mode": "blur", "feather_radius": 6, "export_mask": True, "output_format": "png"},
                ),
                AddonPresetSeed(
                    name="Solid Draft Fill",
                    description="Use a flat neutral fill for quick share-safe drafts.",
                    config_json={"fill_mode": "solid", "fill_color": "#f2f2f2", "feather_radius": 4, "export_mask": True, "output_format": "png"},
                ),
            ],
            per_asset_processor=_process,
        )
    )
