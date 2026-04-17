from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from media_indexer_worker.services.tag_suggestions import TagSuggestionService


class _Result:
    def __init__(self, payload):
        self.payload = payload

    def scalars(self):
        return self

    def all(self):
        return self.payload


class _FakeEmbedder:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors

    def embed_text(self, text: str) -> list[float] | None:
        return self.vectors.get(text)


class _FakeSession:
    def __init__(self, *, vocab_entries, existing_tags, similarity_record) -> None:
        self.vocab_entries = vocab_entries
        self.existing_tags = existing_tags
        self.similarity_record = similarity_record
        self.added: list[object] = []
        self.delete_calls = 0
        self.select_calls = 0

    def execute(self, _query):
        if getattr(_query, "is_delete", False):
            self.delete_calls += 1
            return _Result([])
        self.select_calls += 1
        if self.select_calls == 1:
            return _Result(self.vocab_entries)
        return _Result(self.existing_tags)

    def get(self, _model, _asset_id):
        return self.similarity_record

    def add_all(self, rows):
        self.added.extend(rows)


def test_suggest_tags_replaces_pending_and_skips_existing_tags() -> None:
    embedder = _FakeEmbedder(
        {
            "sunset prompt": [1.0, 0.0],
            "portrait prompt": [0.8, 0.6],
        }
    )
    service = TagSuggestionService(embedder)
    session = _FakeSession(
        vocab_entries=[
            SimpleNamespace(id=1, tag="sunset", clip_prompt="sunset prompt"),
            SimpleNamespace(id=2, tag="portrait", clip_prompt="portrait prompt"),
        ],
        existing_tags=["sunset"],
        similarity_record=SimpleNamespace(embedding=[1.0, 0.0]),
    )

    service.suggest_tags(session, uuid4(), threshold=0.5)

    assert session.delete_calls == 1
    assert len(session.added) == 1
    assert session.added[0].tag == "portrait"


def test_suggest_tags_clears_pending_when_embedding_is_missing() -> None:
    embedder = _FakeEmbedder({"test prompt": [1.0, 0.0]})
    service = TagSuggestionService(embedder)
    session = _FakeSession(
        vocab_entries=[SimpleNamespace(id=1, tag="test", clip_prompt="test prompt")],
        existing_tags=[],
        similarity_record=SimpleNamespace(embedding=None),
    )

    service.suggest_tags(session, uuid4(), threshold=0.2)

    assert session.delete_calls == 1
    assert session.added == []
