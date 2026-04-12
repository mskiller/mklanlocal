from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from media_indexer_backend.models.enums import MatchType, MediaType
from media_indexer_backend.services import asset_service, compare_service


def _asset(
    *,
    asset_id,
    prompt_tags: list[str],
    filename: str,
) -> SimpleNamespace:
    now = datetime(2026, 4, 11, 9, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=asset_id,
        source_id=uuid4(),
        relative_path=f"generated/{filename}",
        filename=filename,
        extension=".png",
        media_type=MediaType.IMAGE,
        mime_type="image/png",
        size_bytes=1024,
        modified_at=now,
        created_at=now,
        indexed_at=now,
        preview_path=f"{asset_id}.jpg",
        metadata_record=SimpleNamespace(
            normalized_json={
                "width": 1024,
                "height": 1024,
                "prompt_tags": prompt_tags,
            }
        ),
        tags=[SimpleNamespace(tag=tag) for tag in prompt_tags],
        similarity=SimpleNamespace(phash="ff00"),
        source=SimpleNamespace(name="Test Source"),
    )


class _Result:
    def __init__(self, payload):
        self.payload = payload

    def scalar_one_or_none(self):
        return self.payload

    def scalar_one(self):
        return self.payload

    def scalars(self):
        return self

    def unique(self):
        return self

    def all(self):
        return self.payload

    def first(self):
        return self.payload


def test_compare_assets_includes_prompt_tag_diff(monkeypatch) -> None:
    asset_a_id = uuid4()
    asset_b_id = uuid4()
    asset_a = _asset(asset_id=asset_a_id, prompt_tags=["freckles", "solo", "cinematic"], filename="left.png")
    asset_b = _asset(asset_id=asset_b_id, prompt_tags=["solo", "blue eyes", "freckles"], filename="right.png")

    def fake_get_asset_or_404(_session, asset_id):
        return asset_a if asset_id == asset_a_id else asset_b

    class FakeSession:
        def execute(self, _query, _params=None):
            return _Result(SimpleNamespace(similarity=0.88))

    monkeypatch.setattr(compare_service, "get_asset_or_404", fake_get_asset_or_404)

    response = compare_service.compare_assets(FakeSession(), asset_a_id, asset_b_id)

    assert response.prompt_tag_overlap == 2
    assert response.shared_prompt_tags == ["freckles", "solo"]
    assert response.left_only_prompt_tags == ["cinematic"]
    assert response.right_only_prompt_tags == ["blue_eyes"]


def test_get_similar_assets_includes_prompt_tag_overlap(monkeypatch) -> None:
    target_id = uuid4()
    candidate_id = uuid4()
    target_asset = _asset(asset_id=target_id, prompt_tags=["freckles", "solo"], filename="target.png")
    candidate_asset = _asset(asset_id=candidate_id, prompt_tags=["solo", "blue eyes"], filename="candidate.png")
    similarity_link = SimpleNamespace(
        asset_id_a=min(target_id, candidate_id, key=str),
        asset_id_b=max(target_id, candidate_id, key=str),
        match_type=MatchType.SEMANTIC,
        distance=0.12,
    )

    def fake_get_asset_or_404(_session, asset_id):
        return target_asset if asset_id == target_id else candidate_asset

    class FakeSession:
        def __init__(self):
            self.calls = 0

        def execute(self, _query):
            self.calls += 1
            if self.calls == 1:
                return _Result([similarity_link])
            return _Result([candidate_asset])

    monkeypatch.setattr(asset_service, "get_asset_or_404", fake_get_asset_or_404)

    results = asset_service.get_similar_assets(FakeSession(), target_id, MatchType.SEMANTIC, 10)

    assert len(results) == 1
    assert results[0].prompt_tag_overlap == 1
    assert results[0].shared_prompt_tags == ["solo"]


def test_compare_assets_rejects_identical_asset_ids() -> None:
    asset_id = uuid4()

    class FakeSession:
        pass

    with pytest.raises(Exception) as exc_info:
        compare_service.compare_assets(FakeSession(), asset_id, asset_id)

    assert getattr(exc_info.value, "status_code", None) == 400
    assert "different images" in str(getattr(exc_info.value, "detail", ""))


def test_asset_browse_item_includes_dimensions() -> None:
    asset = _asset(asset_id=uuid4(), prompt_tags=["solo"], filename="browse.png")

    item = asset_service.asset_browse_item(asset)

    assert item.width == 1024
    assert item.height == 1024
