from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from media_indexer_backend.models.enums import MediaType
from media_indexer_backend.services.asset_service import asset_browse_item


def test_asset_browse_item_keeps_image_preview_url_without_preview_path():
    asset = SimpleNamespace(
        id=uuid4(),
        source_id=uuid4(),
        source=SimpleNamespace(name="Test Source"),
        filename="sample.png",
        relative_path="folder/sample.png",
        preview_path=None,
        blur_hash=None,
        metadata_record=SimpleNamespace(normalized_json={"width": 640, "height": 480}, raw_json={}),
        modified_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        created_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        size_bytes=12345,
        annotations=[],
        media_type=MediaType.IMAGE,
        waveform_preview_path=None,
        video_keyframes=None,
        visual_workflow_json=None,
    )

    item = asset_browse_item(asset)

    assert item.preview_url == f"/assets/{asset.id}/preview"
