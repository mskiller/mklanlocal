from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from media_indexer_backend.models.enums import MediaType
from media_indexer_backend.services import asset_service, compare_service
from media_indexer_backend.services.deepzoom import (
    deepzoom_available,
    deepzoom_manifest_absolute_path,
    deepzoom_manifest_relative_path,
    deepzoom_tiles_absolute_dir,
    deepzoom_url,
)


def _asset():
    asset_id = uuid4()
    now = datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=asset_id,
        source_id=uuid4(),
        relative_path="gallery/example.png",
        filename="example.png",
        extension=".png",
        media_type=MediaType.IMAGE,
        mime_type="image/png",
        size_bytes=2048,
        modified_at=now,
        created_at=now,
        indexed_at=now,
        preview_path=f"{asset_id}.jpg",
        metadata_record=SimpleNamespace(normalized_json={"width": 2048, "height": 2048, "prompt_tags": ["solo"]}),
        tags=[SimpleNamespace(tag="solo")],
        similarity=None,
        source=SimpleNamespace(name="Gallery Source"),
    )


def test_deepzoom_helpers_follow_asset_based_paths(tmp_path) -> None:
    asset_id = uuid4()

    manifest_path = deepzoom_manifest_absolute_path(asset_id, tmp_path)
    tiles_path = deepzoom_tiles_absolute_dir(asset_id, tmp_path)

    assert deepzoom_manifest_relative_path(asset_id).as_posix() == f"deepzoom/{asset_id}.dzi"
    assert manifest_path.as_posix().endswith(f"/deepzoom/{asset_id}.dzi")
    assert tiles_path.as_posix().endswith(f"/deepzoom/{asset_id}_files")
    assert deepzoom_available(asset_id, tmp_path) is False

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("<Image />", encoding="utf-8")

    assert deepzoom_available(asset_id, tmp_path) is True
    assert deepzoom_url(asset_id, tmp_path) == f"/assets/{asset_id}/deepzoom.dzi"


def test_asset_payloads_surface_deepzoom_urls(monkeypatch) -> None:
    asset = _asset()

    monkeypatch.setattr(asset_service, "deepzoom_url", lambda asset_id: f"/assets/{asset_id}/deepzoom.dzi")
    monkeypatch.setattr(compare_service, "deepzoom_url", lambda asset_id: f"/assets/{asset_id}/deepzoom.dzi")

    browse_item = asset_service.asset_browse_item(asset)
    summary = asset_service._asset_summary(asset)
    compare_payload = compare_service._compare_asset_payload(asset)

    assert browse_item.deepzoom_available is True
    assert browse_item.deepzoom_url == f"/assets/{asset.id}/deepzoom.dzi"
    assert summary.deepzoom_available is True
    assert summary.deepzoom_url == f"/assets/{asset.id}/deepzoom.dzi"
    assert compare_payload.deepzoom_available is True
    assert compare_payload.deepzoom_url == f"/assets/{asset.id}/deepzoom.dzi"
