from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from media_indexer_backend.api.dependencies import require_admin, require_collection_manager, require_upload_access
from media_indexer_backend.models.enums import UserRole, UserStatus
from media_indexer_backend.services.source_service import source_read_for_user
from media_indexer_backend.services.user_service import (
    authenticate_user,
    auth_user_response,
    change_password,
    hash_password,
    update_user,
    verify_password,
)
from media_indexer_backend.services.workflow_export import build_comfyui_workflow_export


def test_auth_user_response_exposes_capabilities() -> None:
    admin = auth_user_response(SimpleNamespace(id=uuid4(), username="admin", role=UserRole.ADMIN))
    curator = auth_user_response(SimpleNamespace(id=uuid4(), username="curator", role=UserRole.CURATOR))
    guest = auth_user_response(SimpleNamespace(id=uuid4(), username="guest", role=UserRole.GUEST))

    assert admin.capabilities.can_view_admin
    assert admin.capabilities.can_manage_users
    assert curator.capabilities.can_manage_collections
    assert curator.capabilities.can_upload_assets
    assert not curator.capabilities.can_manage_sources
    assert not curator.capabilities.can_view_admin
    assert not guest.capabilities.can_view_admin
    assert not guest.capabilities.can_run_scans


def test_authenticate_user_accepts_active_user_and_rejects_disabled(monkeypatch) -> None:
    password_hash = hash_password("secret")
    active_user = SimpleNamespace(status=UserStatus.ACTIVE, password_hash=password_hash)
    disabled_user = SimpleNamespace(status=UserStatus.DISABLED, password_hash=password_hash)

    monkeypatch.setattr("media_indexer_backend.services.user_service.get_user_by_username", lambda _session, _username: active_user)
    assert authenticate_user(object(), "admin", "secret") is active_user

    monkeypatch.setattr("media_indexer_backend.services.user_service.get_user_by_username", lambda _session, _username: disabled_user)
    assert authenticate_user(object(), "admin", "secret") is None


def test_change_password_requires_current_password() -> None:
    user = SimpleNamespace(password_hash=hash_password("old-password"))
    session = SimpleNamespace(flush=lambda: None)

    with pytest.raises(HTTPException):
        change_password(session, user, "wrong-password", "new-password", "new-password")

    updated = change_password(session, user, "old-password", "new-password", "new-password")
    assert updated is user
    assert verify_password(user.password_hash, "new-password")


def test_update_user_prevents_demoting_last_active_admin(monkeypatch) -> None:
    admin_user = SimpleNamespace(id=uuid4(), username="admin", role=UserRole.ADMIN, status=UserStatus.ACTIVE)

    monkeypatch.setattr("media_indexer_backend.services.user_service.get_user_or_404", lambda _session, _user_id: admin_user)
    monkeypatch.setattr("media_indexer_backend.services.user_service._active_admin_count", lambda _session: 1)

    with pytest.raises(HTTPException):
        update_user(object(), admin_user.id, SimpleNamespace(username=None, role=UserRole.GUEST, status=None))


def test_require_admin_rejects_guest() -> None:
    with pytest.raises(HTTPException):
        require_admin(SimpleNamespace(role=UserRole.GUEST))


def test_collection_manager_and_upload_access_accept_curator_and_reject_guest() -> None:
    curator = SimpleNamespace(role=UserRole.CURATOR)
    guest = SimpleNamespace(role=UserRole.GUEST)

    assert require_collection_manager(curator) is curator
    assert require_upload_access(curator) is curator
    with pytest.raises(HTTPException):
        require_collection_manager(guest)
    with pytest.raises(HTTPException):
        require_upload_access(guest)


def test_source_read_redacts_root_path_for_guest() -> None:
    source = SimpleNamespace(
        id=uuid4(),
        name="Images",
        type="mounted_fs",
        root_path="/data/sources/images",
        status="ready",
        last_scan_at=None,
        created_at=datetime(2026, 4, 11, tzinfo=timezone.utc),
    )
    admin = SimpleNamespace(role=UserRole.ADMIN)
    curator = SimpleNamespace(role=UserRole.CURATOR)
    guest = SimpleNamespace(role=UserRole.GUEST)

    admin_view = source_read_for_user(source, admin)
    curator_view = source_read_for_user(source, curator)
    guest_view = source_read_for_user(source, guest)

    assert admin_view.root_path == "/data/sources/images"
    assert curator_view.root_path is None
    assert guest_view.root_path is None
    assert guest_view.display_root_path == "Images / approved root"


def test_build_comfyui_workflow_export_returns_envelope() -> None:
    payload = build_comfyui_workflow_export(
        asset_id=str(uuid4()),
        filename="sample.png",
        normalized_metadata={"generator": "comfyui"},
        raw_metadata={
            "Prompt": '{"10": {"class_type": "CLIPTextEncode"}}',
            "Workflow": '{"nodes": [{"id": 10}]}',
        },
    )

    assert payload is not None
    assert payload["generator"] == "comfyui"
    assert "prompt" in payload
    assert "workflow" in payload


def test_build_comfyui_workflow_export_returns_none_when_not_available() -> None:
    payload = build_comfyui_workflow_export(
        asset_id=str(uuid4()),
        filename="sample.png",
        normalized_metadata={"generator": "automatic1111"},
        raw_metadata={},
    )

    assert payload is None
