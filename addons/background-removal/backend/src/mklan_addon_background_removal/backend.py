from __future__ import annotations

from PIL import Image
from PIL import ImageChops, ImageFilter

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
)


def _build_alpha_mask(image, threshold: float, soften_radius: float):
    rgb = image.convert("RGB")
    corners = [
        rgb.getpixel((0, 0)),
        rgb.getpixel((rgb.width - 1, 0)),
        rgb.getpixel((0, rgb.height - 1)),
        rgb.getpixel((rgb.width - 1, rgb.height - 1)),
    ]
    average = tuple(int(sum(channel) / len(corners)) for channel in zip(*corners, strict=False))
    background = Image.new("RGB", rgb.size, average)
    difference = ImageChops.difference(rgb, background)
    red, green, blue = difference.split()
    strongest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    mask = strongest.point(
        lambda value: 0 if value < threshold else min(255, int(((value - threshold) / max(1, 255 - threshold)) * 255))
    )
    if soften_radius > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=soften_radius))
    return mask


def _process(context, asset):
    _, image = load_asset_image(asset, context.module_id)
    image = clamp_image_size(image, int(option(context, "max_input_size", 4096)))
    threshold = max(5.0, min(220.0, parse_float(option(context, "threshold", 40.0), 40.0)))
    soften_radius = max(0.0, min(8.0, parse_float(option(context, "soften_radius", 1.5), 1.5)))
    include_mask = parse_bool(option(context, "export_mask", True), True)

    alpha_mask = _build_alpha_mask(image, threshold, soften_radius)
    cutout = image.convert("RGBA")
    cutout.putalpha(alpha_mask)

    requested_format = output_format(context, "png")
    encoded_cutout = encode_image(cutout, requested_format, quality=output_quality(context))
    stem = asset_stem(asset.filename)
    artifacts = [
        GeneratedArtifact(
            filename=f"{stem}-background-removed.{encoded_cutout.extension}",
            content=encoded_cutout.content,
            mime_type=encoded_cutout.mime_type,
            label="Cutout",
            asset_id=str(asset.id),
            width=cutout.width,
            height=cutout.height,
            metadata_json={
                "threshold": threshold,
                "soften_radius": soften_radius,
                "output_format": requested_format,
            },
        )
    ]
    if include_mask:
        encoded_mask = encode_image(alpha_mask, "png")
        artifacts.append(
            GeneratedArtifact(
                filename=f"{stem}-alpha-mask.png",
                content=encoded_mask.content,
                mime_type=encoded_mask.mime_type,
                label="Alpha Mask",
                asset_id=str(asset.id),
                width=alpha_mask.width,
                height=alpha_mask.height,
                metadata_json={"mask_only": True},
            )
        )
    return artifacts


def register() -> None:
    register_addon_definition(
        AddonDefinition(
            module_id="background_removal",
            name="Background Removal",
            description="Generate transparent cutouts and alpha masks from indexed images.",
            supports_asset=True,
            supports_batch=True,
            supports_collection=False,
            default_presets=[
                AddonPresetSeed(
                    name="Cutout PNG",
                    description="Balanced matte extraction with PNG transparency.",
                    config_json={"threshold": 40, "soften_radius": 1.5, "output_format": "png", "export_mask": True},
                ),
                AddonPresetSeed(
                    name="Cutout WebP",
                    description="Transparent WebP for lighter previews and drafts.",
                    config_json={"threshold": 32, "soften_radius": 1.0, "output_format": "webp", "export_mask": False},
                ),
            ],
            per_asset_processor=_process,
        )
    )
