from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from media_indexer_backend.core.config import get_settings
from media_indexer_backend.services.path_safety import normalize_relative_path, resolve_asset_path, resolve_directory_path, validate_source_root


def test_validate_source_root_accepts_child_of_allowed_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = tmp_path / "allowed"
    child = allowed / "photos"
    child.mkdir(parents=True)
    monkeypatch.setattr(get_settings(), "allowed_source_roots", str(allowed))
    assert validate_source_root(str(child)) == str(child.resolve())


def test_validate_source_root_rejects_outside_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    monkeypatch.setattr(get_settings(), "allowed_source_roots", str(allowed))
    with pytest.raises(HTTPException):
        validate_source_root(str(outside))


def test_resolve_asset_path_blocks_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    (allowed / "photo.jpg").write_bytes(b"hello")
    monkeypatch.setattr(get_settings(), "allowed_source_roots", str(allowed))
    with pytest.raises(HTTPException):
        resolve_asset_path(str(allowed), "../outside.jpg")


def test_normalize_relative_path_rejects_parent_segments() -> None:
    with pytest.raises(HTTPException):
        normalize_relative_path("nested/../outside.jpg")


def test_resolve_directory_path_accepts_nested_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = tmp_path / "allowed"
    nested = allowed / "nested" / "photos"
    nested.mkdir(parents=True)
    monkeypatch.setattr(get_settings(), "allowed_source_roots", str(allowed))

    resolved, normalized = resolve_directory_path(str(allowed), "nested/photos")

    assert resolved == nested.resolve()
    assert normalized == "nested/photos"
