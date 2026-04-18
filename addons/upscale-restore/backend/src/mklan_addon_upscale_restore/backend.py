from __future__ import annotations

from PIL import ImageFilter

from media_indexer_backend.addons import AddonDefinition, AddonPresetSeed, GeneratedArtifact, register_addon_definition
from media_indexer_backend.addons.image_utils import (
    RESAMPLING,
    asset_stem,
    clamp_image_size,
    encode_image,
    load_asset_image,
    option,
    output_format,
    output_quality,
    parse_float,
    parse_int,
)


def _process(context, asset):
    _, image = load_asset_image(asset, context.module_id)
    image = clamp_image_size(image, int(option(context, "max_input_size", 4096)))
    scale = max(2, min(4, parse_int(option(context, "scale", 2), 2)))
    denoise_strength = max(0.0, min(1.0, parse_float(option(context, "denoise_strength", 0.3), 0.3)))
    sharpen_strength = max(0.0, min(2.0, parse_float(option(context, "sharpen_strength", 1.0), 1.0)))

    upscaled = image.resize((image.width * scale, image.height * scale), RESAMPLING.LANCZOS)
    if denoise_strength >= 0.2:
        upscaled = upscaled.filter(ImageFilter.MedianFilter(size=3))
    if sharpen_strength > 0:
        upscaled = upscaled.filter(
            ImageFilter.UnsharpMask(radius=1.4 + (0.8 * sharpen_strength), percent=int(120 + (60 * sharpen_strength)), threshold=3)
        )

    requested_format = output_format(context, "png")
    encoded = encode_image(upscaled, requested_format, quality=output_quality(context))
    return [
        GeneratedArtifact(
            filename=f"{asset_stem(asset.filename)}-restore-x{scale}.{encoded.extension}",
            content=encoded.content,
            mime_type=encoded.mime_type,
            label=f"Upscaled x{scale}",
            asset_id=str(asset.id),
            width=upscaled.width,
            height=upscaled.height,
            metadata_json={
                "scale": scale,
                "denoise_strength": denoise_strength,
                "sharpen_strength": sharpen_strength,
            },
        )
    ]


def register() -> None:
    register_addon_definition(
        AddonDefinition(
            module_id="upscale_restore",
            name="Upscale + Restore",
            description="Create cached x2/x4 upscale derivatives with light denoise and sharpening.",
            supports_asset=True,
            supports_batch=True,
            supports_collection=False,
            default_presets=[
                AddonPresetSeed(
                    name="Balanced x2",
                    description="x2 upscale with gentle cleanup.",
                    config_json={"scale": 2, "denoise_strength": 0.3, "sharpen_strength": 1.0, "output_format": "png"},
                ),
                AddonPresetSeed(
                    name="Crisp x4",
                    description="x4 upscale tuned for sharper draft review.",
                    config_json={"scale": 4, "denoise_strength": 0.15, "sharpen_strength": 1.4, "output_format": "png"},
                ),
            ],
            per_asset_processor=_process,
        )
    )
