from __future__ import annotations

from io import BytesIO
import json
from types import SimpleNamespace
from uuid import uuid4

from PIL import Image, ImageDraw, PngImagePlugin

from media_indexer_backend.addons import AddonExecutionContext, get_addon_definition
from media_indexer_backend.models.enums import MediaType
from media_indexer_backend.platform.registry import ensure_runtime_import_paths


ensure_runtime_import_paths("backend")

import mklan_addon_background_removal.backend as background_backend
import mklan_addon_export_recipes.backend as export_backend
import mklan_addon_metadata_privacy.backend as metadata_backend
import mklan_addon_object_erase.backend as erase_backend
import mklan_addon_upscale_restore.backend as upscale_backend


background_backend.register()
export_backend.register()
metadata_backend.register()
erase_backend.register()
upscale_backend.register()


def _build_test_png_bytes(*, prompt: str | None = None, square_color=(220, 40, 40)) -> bytes:
    image = Image.new("RGB", (120, 120), (255, 255, 255))
    drawer = ImageDraw.Draw(image)
    drawer.rectangle((30, 30, 90, 90), fill=square_color)
    buffer = BytesIO()
    if prompt:
        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add_text("Prompt", prompt)
        image.save(buffer, format="PNG", pnginfo=pnginfo)
    else:
        image.save(buffer, format="PNG")
    return buffer.getvalue()


def _asset(filename: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        filename=filename,
        relative_path=filename,
        media_type=MediaType.IMAGE,
        source=SimpleNamespace(root_path="memory://tests"),
    )


def _context(module_id: str, assets: list[SimpleNamespace], *, params_json: dict | None = None, scope_type: str = "asset", scope_json: dict | None = None):
    return AddonExecutionContext(
        session=None,
        current_user=SimpleNamespace(id=uuid4(), username="tester"),
        module_id=module_id,
        module_settings={},
        params_json=params_json or {},
        scope_type=scope_type,
        scope_json=scope_json or {},
        assets=assets,
        collection=SimpleNamespace(id=scope_json.get("collection_id")) if scope_json and scope_json.get("collection_id") else None,
        preset=None,
        recipe_version=1,
    )


def test_background_removal_preserves_subject_alpha(monkeypatch):
    source_image = Image.open(BytesIO(_build_test_png_bytes())).convert("RGBA")
    asset = _asset("subject.png")
    context = _context("background_removal", [asset], params_json={"threshold": 35, "soften_radius": 0, "export_mask": True})

    monkeypatch.setattr(background_backend, "load_asset_image", lambda *_args, **_kwargs: ("memory://subject.png", source_image.copy()))

    definition = get_addon_definition("background_removal")
    artifacts = definition.per_asset_processor(context, asset)  # type: ignore[union-attr]

    assert [artifact.label for artifact in artifacts] == ["Cutout", "Alpha Mask"]
    cutout = Image.open(BytesIO(artifacts[0].content)).convert("RGBA")
    assert cutout.getpixel((5, 5))[3] == 0
    assert cutout.getpixel((60, 60))[3] > 200


def test_upscale_restore_scales_image_dimensions(monkeypatch):
    source_image = Image.open(BytesIO(_build_test_png_bytes())).convert("RGBA")
    asset = _asset("tiny.png")
    context = _context("upscale_restore", [asset], params_json={"scale": 2})

    monkeypatch.setattr(upscale_backend, "load_asset_image", lambda *_args, **_kwargs: ("memory://tiny.png", source_image.copy()))

    definition = get_addon_definition("upscale_restore")
    artifacts = definition.per_asset_processor(context, asset)  # type: ignore[union-attr]

    restored = Image.open(BytesIO(artifacts[0].content))
    assert artifacts[0].label == "Upscaled x2"
    assert restored.size == (240, 240)


def test_object_erase_emits_saved_mask_and_replay_params(monkeypatch):
    source_image = Image.open(BytesIO(_build_test_png_bytes(square_color=(0, 0, 0)))).convert("RGBA")
    asset = _asset("erase.png")
    context = _context(
        "object_erase",
        [asset],
        params_json={"mask_rects": [{"x": 0.2, "y": 0.2, "width": 0.45, "height": 0.45}], "fill_mode": "blur"},
    )

    monkeypatch.setattr(erase_backend, "load_asset_image", lambda *_args, **_kwargs: ("memory://erase.png", source_image.copy()))

    definition = get_addon_definition("object_erase")
    artifacts = definition.per_asset_processor(context, asset)  # type: ignore[union-attr]

    assert [artifact.label for artifact in artifacts] == ["Erased Draft", "Saved Mask", "Replay Params"]
    erased = Image.open(BytesIO(artifacts[0].content)).convert("RGBA")
    assert erased.getpixel((60, 60))[:3] != (0, 0, 0)
    replay_report = json.loads(artifacts[2].content.decode("utf-8"))
    assert replay_report["fill_mode"] == "blur"
    assert replay_report["mask_rects"]


def test_metadata_privacy_strips_prompt_text_from_png(monkeypatch):
    source_bytes = _build_test_png_bytes(prompt="sunset street scene")
    source_image = Image.open(BytesIO(source_bytes)).convert("RGBA")
    asset = _asset("metadata.png")
    context = _context("metadata_privacy", [asset], params_json={"preserve_profile": "share_safe", "preserve_prompt": False})
    original_open = Image.open

    monkeypatch.setattr(metadata_backend, "load_asset_image", lambda *_args, **_kwargs: ("memory://metadata.png", source_image.copy()))
    monkeypatch.setattr(metadata_backend.Image, "open", lambda *_args, **_kwargs: original_open(BytesIO(source_bytes)))

    definition = get_addon_definition("metadata_privacy")
    artifacts = definition.per_asset_processor(context, asset)  # type: ignore[union-attr]

    sanitized = original_open(BytesIO(artifacts[0].content))
    report = json.loads(artifacts[1].content.decode("utf-8"))

    assert artifacts[0].label == "Sanitized Export"
    assert "Prompt" not in sanitized.info
    assert "Prompt" in report["removed_text_fields"]


def test_export_recipes_builds_collection_contact_sheet(monkeypatch):
    source_one = Image.open(BytesIO(_build_test_png_bytes())).convert("RGBA")
    source_two = Image.open(BytesIO(_build_test_png_bytes(square_color=(40, 60, 220)))).convert("RGBA")
    assets = [_asset("one.png"), _asset("two.png")]
    context = _context(
        "export_recipes",
        assets,
        params_json={"contact_sheet": True, "export_individuals": False, "columns": 2, "thumb_size": 96},
        scope_type="collection",
        scope_json={"collection_id": str(uuid4())},
    )

    asset_map = {
        "one.png": source_one.copy(),
        "two.png": source_two.copy(),
    }
    monkeypatch.setattr(
        export_backend,
        "load_asset_image",
        lambda asset, *_args, **_kwargs: (f"memory://{asset.filename}", asset_map[asset.filename].copy()),
    )

    definition = get_addon_definition("export_recipes")
    artifacts = definition.job_processor(context)  # type: ignore[union-attr]

    contact_sheet = Image.open(BytesIO(artifacts[0].content))
    assert artifacts[0].label == "Contact Sheet"
    assert contact_sheet.width == 192
    assert contact_sheet.height > 96
