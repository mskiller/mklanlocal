from __future__ import annotations

from pathlib import Path

from media_indexer_backend.core.config import get_settings
from media_indexer_backend.models.tables import Asset, Source
from media_indexer_backend.services.path_safety import resolve_asset_path
from media_indexer_backend.services.vips_image_service import render_resized_image_to_file


def _cache_root() -> Path:
    root = get_settings().preview_root_path / "cache"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _evict_lru_cache(root: Path, max_mb: int) -> None:
    files = [path for path in root.glob("*") if path.is_file()]
    total_size = sum(path.stat().st_size for path in files)
    max_bytes = max_mb * 1024 * 1024
    if total_size <= max_bytes:
        return
    for path in sorted(files, key=lambda item: item.stat().st_mtime):
        size = path.stat().st_size
        path.unlink(missing_ok=True)
        total_size -= size
        if total_size <= max_bytes:
            break


def ensure_cached_resized_image(
    asset: Asset,
    source: Source,
    *,
    width: int | None,
    height: int | None,
    quality: int,
    fmt: str,
) -> Path:
    source_path = resolve_asset_path(source.root_path, asset.relative_path)
    cache_root = _cache_root()
    cache_key = f"{asset.id}_{width or 0}x{height or 0}_q{quality}.{fmt}"
    cache_path = cache_root / cache_key
    if cache_path.exists():
        return cache_path

    render_resized_image_to_file(
        source_path,
        cache_path,
        width=width,
        height=height,
        quality=quality,
        fmt=fmt,
    )

    _evict_lru_cache(cache_root, get_settings().preview_cache_max_mb)
    return cache_path
