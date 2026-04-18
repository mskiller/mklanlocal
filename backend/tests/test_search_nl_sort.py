from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from media_indexer_backend.api.routes import search


BASE_TIME = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)


def make_asset(
    filename: str,
    *,
    indexed_offset_hours: int,
    created_offset_hours: int | None = None,
    modified_offset_hours: int | None = None,
):
    return SimpleNamespace(
        filename=filename,
        indexed_at=BASE_TIME + timedelta(hours=indexed_offset_hours),
        created_at=None if created_offset_hours is None else BASE_TIME + timedelta(hours=created_offset_hours),
        modified_at=BASE_TIME if modified_offset_hours is None else BASE_TIME + timedelta(hours=modified_offset_hours),
    )


def test_sort_semantic_assets_keeps_best_match_order_by_default():
    assets = [
        make_asset("closest.png", indexed_offset_hours=1),
        make_asset("middle.png", indexed_offset_hours=2),
        make_asset("furthest.png", indexed_offset_hours=3),
    ]

    ordered = search._sort_semantic_assets(assets, sort="relevance", sort_direction="desc")

    assert [asset.filename for asset in ordered] == ["closest.png", "middle.png", "furthest.png"]


def test_sort_semantic_assets_can_reverse_similarity_order():
    assets = [
        make_asset("closest.png", indexed_offset_hours=1),
        make_asset("middle.png", indexed_offset_hours=2),
        make_asset("furthest.png", indexed_offset_hours=3),
    ]

    ordered = search._sort_semantic_assets(assets, sort="relevance", sort_direction="asc")

    assert [asset.filename for asset in ordered] == ["furthest.png", "middle.png", "closest.png"]


def test_sort_semantic_assets_can_reorder_by_latest_index():
    assets = [
        make_asset("semantic-top.png", indexed_offset_hours=1),
        make_asset("semantic-middle.png", indexed_offset_hours=8),
        make_asset("semantic-third.png", indexed_offset_hours=4),
    ]

    ordered = search._sort_semantic_assets(assets, sort="indexed_at", sort_direction="desc")

    assert [asset.filename for asset in ordered] == [
        "semantic-middle.png",
        "semantic-third.png",
        "semantic-top.png",
    ]


def test_semantic_candidate_limit_expands_for_non_relevance():
    assert search._semantic_candidate_limit(50, "relevance") == 50
    assert search._semantic_candidate_limit(50, "indexed_at") == 200
    assert search._semantic_candidate_limit(200, "indexed_at") == 400
