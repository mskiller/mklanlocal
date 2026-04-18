from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from media_indexer_backend.models.enums import MediaType
from media_indexer_backend.schemas.image_ops import CropSpec
from media_indexer_backend.services.extractors import extract_png_metadata_from_file
from media_indexer_backend.services.image_service import ensure_cached_resized_image
from media_indexer_backend.services.vips_image_service import render_cropped_image_bytes, render_preview_and_blurhash
from media_indexer_worker.services.previews import PreviewGenerator


def _workspace_temp_dir() -> Path:
    root = Path(__file__).resolve().parent / "_tmp"
    path = root / str(uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


def _create_test_image(path: Path, *, size: tuple[int, int] = (320, 160), color: tuple[int, int, int] = (30, 80, 140)) -> None:
    Image.new("RGB", size, color).save(path, format="PNG")


def test_render_cropped_image_bytes_preserves_png_text_metadata():
    tmp_path = _workspace_temp_dir()
    source_path = tmp_path / "metadata-source.png"
    png_info = PngInfo()
    png_info.add_text("parameters", "sampler=euler")
    Image.new("RGB", (120, 80), (120, 30, 60)).save(source_path, format="PNG", pnginfo=png_info)

    cropped_bytes = render_cropped_image_bytes(
        source_path,
        CropSpec(rotation_quadrants=0, crop_x=10, crop_y=12, crop_width=60, crop_height=30),
        output_format=".png",
    )
    cropped_path = tmp_path / "metadata-crop.png"
    cropped_path.write_bytes(cropped_bytes)

    metadata = extract_png_metadata_from_file(cropped_path)

    assert metadata.get("parameters") == "sampler=euler"


def test_preview_generator_creates_preview_and_blurhash(monkeypatch):
    tmp_path = _workspace_temp_dir()
    preview_root = tmp_path / "previews"
    source_path = tmp_path / "source.png"
    _create_test_image(source_path, size=(640, 320))

    monkeypatch.setattr(
        "media_indexer_worker.services.previews.get_settings",
        lambda: SimpleNamespace(
            preview_root_path=preview_root,
            max_thumbnail_size=256,
        ),
    )

    generator = PreviewGenerator()
    preview_name, blur_hash = generator.generate(uuid4(), MediaType.IMAGE, source_path)

    assert preview_name is not None
    assert (preview_root / preview_name).exists()
    assert blur_hash is not None
    assert len(blur_hash) > 10


def test_render_preview_and_blurhash_falls_back_to_pillow_when_libvips_fails(monkeypatch):
    tmp_path = _workspace_temp_dir()
    source_path = tmp_path / "source.png"
    output_path = tmp_path / "preview.jpg"
    _create_test_image(source_path, size=(640, 320))

    monkeypatch.setattr("media_indexer_backend.services.vips_image_service.libvips_available", lambda: True)

    def _raise_vips_error(path: Path):
        del path
        raise RuntimeError("pngload: out of order read")

    monkeypatch.setattr("media_indexer_backend.services.vips_image_service._vips_load_image", _raise_vips_error)

    blur_hash = render_preview_and_blurhash(source_path, output_path, max_size=256)

    assert output_path.exists()
    assert blur_hash is not None
    assert len(blur_hash) > 10


def test_ensure_cached_resized_image_reuses_existing_cache(monkeypatch):
    tmp_path = _workspace_temp_dir()
    preview_root = tmp_path / "preview-cache"
    source_root = tmp_path / "source-root"
    source_root.mkdir()
    source_path = source_root / "asset.png"
    _create_test_image(source_path, size=(600, 400))

    settings = SimpleNamespace(
        preview_root_path=preview_root,
        preview_cache_max_mb=64,
        allowed_source_root_paths=[source_root],
    )
    monkeypatch.setattr("media_indexer_backend.services.image_service.get_settings", lambda: settings)
    monkeypatch.setattr("media_indexer_backend.services.path_safety.get_settings", lambda: settings)

    asset = SimpleNamespace(id=uuid4(), relative_path="asset.png")
    source = SimpleNamespace(root_path=str(source_root))

    first = ensure_cached_resized_image(asset, source, width=240, height=240, quality=82, fmt="webp")
    before_mtime = first.stat().st_mtime
    second = ensure_cached_resized_image(asset, source, width=240, height=240, quality=82, fmt="webp")

    assert first == second
    assert second.exists()
    assert second.stat().st_mtime == before_mtime
