from __future__ import annotations

from PIL import Image, ImageDraw, ImageOps

from media_indexer_backend.addons import AddonDefinition, AddonPresetSeed, GeneratedArtifact, register_addon_definition
from media_indexer_backend.addons.image_utils import (
    RESAMPLING,
    asset_stem,
    clamp_image_size,
    default_font,
    encode_image,
    load_asset_image,
    option,
    output_format,
    output_quality,
    parse_bool,
    parse_hex_color,
    parse_int,
)


def _apply_export_recipe(context, asset):
    _, image = load_asset_image(asset, context.module_id)
    image = clamp_image_size(image, int(option(context, "max_input_size", 4096))).convert("RGBA")

    resize_width = parse_int(option(context, "resize_width", 0), 0)
    resize_height = parse_int(option(context, "resize_height", 0), 0)
    fit_mode = str(option(context, "fit_mode", "contain")).strip().lower()
    if resize_width > 0 or resize_height > 0:
        target_width = resize_width or image.width
        target_height = resize_height or image.height
        if fit_mode == "cover":
            image = ImageOps.fit(image, (target_width, target_height), method=RESAMPLING.LANCZOS)
        else:
            image = ImageOps.contain(image, (target_width, target_height), method=RESAMPLING.LANCZOS)

    frame_px = max(0, parse_int(option(context, "frame_px", 0), 0))
    if frame_px:
        frame_color = parse_hex_color(option(context, "frame_color", "#ffffff"), (255, 255, 255, 255))
        image = ImageOps.expand(image, border=frame_px, fill=frame_color)

    watermark_text = str(option(context, "watermark_text", "")).strip()
    if watermark_text:
        drawable = ImageDraw.Draw(image)
        font = default_font()
        text_bbox = drawable.textbbox((0, 0), watermark_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        padding = 10
        box = (
            image.width - text_width - (padding * 2),
            image.height - text_height - (padding * 2),
            image.width,
            image.height,
        )
        drawable.rectangle(box, fill=(0, 0, 0, 120))
        drawable.text((box[0] + padding, box[1] + padding), watermark_text, fill=(255, 255, 255, 230), font=font)

    requested_format = output_format(context, "webp")
    encoded = encode_image(image, requested_format, quality=output_quality(context))
    return GeneratedArtifact(
        filename=f"{asset_stem(asset.filename)}-recipe.{encoded.extension}",
        content=encoded.content,
        mime_type=encoded.mime_type,
        label="Recipe Export",
        asset_id=str(asset.id),
        width=image.width,
        height=image.height,
        metadata_json={
            "resize_width": resize_width or None,
            "resize_height": resize_height or None,
            "frame_px": frame_px,
            "watermark_text": watermark_text or None,
        },
    )


def _build_contact_sheet(context):
    assets = context.assets
    if not assets:
        raise ValueError("export_recipes collection jobs require at least one asset.")

    columns = max(2, min(8, parse_int(option(context, "columns", 4), 4)))
    thumb_size = max(96, min(512, parse_int(option(context, "thumb_size", 256), 256)))
    background = parse_hex_color(option(context, "background_color", "#f7f4ef"), (247, 244, 239, 255))

    prepared: list[tuple[Image.Image, str]] = []
    for asset in assets:
        _, image = load_asset_image(asset, context.module_id)
        image = ImageOps.fit(image.convert("RGB"), (thumb_size, thumb_size), method=RESAMPLING.LANCZOS)
        prepared.append((image, asset.filename))

    rows = (len(prepared) + columns - 1) // columns
    label_height = 30
    canvas = Image.new("RGB", (columns * thumb_size, rows * (thumb_size + label_height)), background[:3])
    draw = ImageDraw.Draw(canvas)
    font = default_font()

    for index, (thumb, label) in enumerate(prepared):
        column = index % columns
        row = index // columns
        x = column * thumb_size
        y = row * (thumb_size + label_height)
        canvas.paste(thumb, (x, y))
        draw.rectangle((x, y + thumb_size, x + thumb_size, y + thumb_size + label_height), fill=(255, 255, 255))
        draw.text((x + 8, y + thumb_size + 8), label[:30], fill=(40, 40, 40), font=font)

    encoded = encode_image(canvas, "jpeg", quality=92)
    collection_id = context.scope_json.get("collection_id", "collection")
    return GeneratedArtifact(
        filename=f"collection-{collection_id}-contact-sheet.{encoded.extension}",
        content=encoded.content,
        mime_type=encoded.mime_type,
        label="Contact Sheet",
        width=canvas.width,
        height=canvas.height,
        metadata_json={"collection_id": collection_id, "columns": columns, "thumb_size": thumb_size},
    )


def _process_job(context):
    artifacts = []
    export_individuals = parse_bool(option(context, "export_individuals", context.scope_type != "collection"), context.scope_type != "collection")
    contact_sheet = parse_bool(option(context, "contact_sheet", context.scope_type == "collection"), context.scope_type == "collection")

    if export_individuals:
        for asset in context.assets:
            artifacts.append(_apply_export_recipe(context, asset))
    if contact_sheet and context.scope_type == "collection":
        artifacts.append(_build_contact_sheet(context))
    if not artifacts:
        raise ValueError("export_recipes did not receive a recipe that creates any artifacts.")
    return artifacts


def register() -> None:
    register_addon_definition(
        AddonDefinition(
            module_id="export_recipes",
            name="Export Recipes",
            description="Run reusable export presets for web shares, overlays, and collection contact sheets.",
            supports_asset=True,
            supports_batch=True,
            supports_collection=True,
            default_presets=[
                AddonPresetSeed(
                    name="Web Share",
                    description="Resize and convert to a lighter WebP share export.",
                    config_json={"resize_width": 2048, "fit_mode": "contain", "output_format": "webp", "quality": 90, "export_individuals": True},
                ),
                AddonPresetSeed(
                    name="Watermarked Share",
                    description="Resize and stamp a watermark on each exported derivative.",
                    config_json={"resize_width": 2048, "fit_mode": "contain", "output_format": "jpeg", "watermark_text": "MKLan Draft", "quality": 90, "export_individuals": True},
                ),
                AddonPresetSeed(
                    name="Contact Sheet",
                    description="Generate a collection contact sheet without individual exports.",
                    config_json={"contact_sheet": True, "export_individuals": False, "columns": 4, "thumb_size": 256, "output_format": "jpeg"},
                ),
            ],
            job_processor=_process_job,
        )
    )
