from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from media_indexer_backend.api import dependencies
from media_indexer_backend.api.routes import assets, inbox, search, shares, smart_albums, sources, tags
from media_indexer_backend.models.enums import ReviewStatus, UserRole
from media_indexer_backend.schemas.asset import AssetListResponse
from media_indexer_backend.schemas.auth import AuthCapabilities
from media_indexer_backend.schemas.inbox import InboxItemRead
from media_indexer_backend.schemas.smart_album import SmartAlbumRule, SmartAlbumSummary
from media_indexer_backend.schemas.source import SourceRead
from media_indexer_backend.services import user_service


class FakeExecuteResult:
    def __init__(self, scalar_value=None):
        self._scalar_value = scalar_value

    def scalar_one_or_none(self):
        return self._scalar_value


class FakeSession:
    def __init__(self):
        self.scalar_result = uuid4()

    def add(self, item):
        if hasattr(item, "id") and getattr(item, "id", None) is None:
            item.id = "share-link-1"
        if hasattr(item, "view_count") and getattr(item, "view_count", None) is None:
            item.view_count = 0
        if hasattr(item, "created_at") and getattr(item, "created_at", None) is None:
            item.created_at = datetime.now(tz=timezone.utc)

    def commit(self):
        return None

    def refresh(self, item):
        if hasattr(item, "id") and getattr(item, "id", None) is None:
            item.id = "share-link-1"

    def flush(self):
        return None

    def delete(self, item):
        del item

    def get(self, model, key):
        del model, key
        return None

    def execute(self, query):
        del query
        return FakeExecuteResult()

    def scalar(self, query):
        del query
        return self.scalar_result


def workspace_temp_dir() -> Path:
    root = Path(__file__).resolve().parent / "_tmp"
    path = root / str(uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


def request(client: TestClient, method: str, path: str, payload):
    caller = getattr(client, method)
    if method in {"get", "delete"}:
        return caller(path)
    if payload is None:
        return caller(path)
    return caller(path, json=payload)


def make_user(role: UserRole):
    return SimpleNamespace(
        id=uuid4(),
        username=role.value,
        role=role,
    )


def make_capabilities(role: UserRole) -> AuthCapabilities:
    if role == UserRole.ADMIN:
        return AuthCapabilities(
            can_manage_sources=True,
            can_run_scans=True,
            can_review_compare=True,
            can_curate_assets=True,
            can_reset=True,
            can_manage_users=True,
            can_manage_collections=True,
            can_manage_shares=True,
            can_manage_smart_albums=True,
            can_upload_assets=True,
            can_view_admin=True,
            allowed_source_ids="all",
        )
    if role == UserRole.CURATOR:
        return AuthCapabilities(
            can_manage_sources=False,
            can_run_scans=False,
            can_review_compare=True,
            can_curate_assets=True,
            can_reset=False,
            can_manage_users=False,
            can_manage_collections=True,
            can_manage_shares=True,
            can_manage_smart_albums=True,
            can_upload_assets=True,
            can_view_admin=False,
            allowed_source_ids="all",
        )
    return AuthCapabilities(
        can_manage_sources=False,
        can_run_scans=False,
        can_review_compare=False,
        can_curate_assets=False,
        can_reset=False,
        can_manage_users=False,
        can_manage_collections=False,
        can_manage_shares=False,
        can_manage_smart_albums=False,
        can_upload_assets=False,
        can_view_admin=False,
        allowed_source_ids="all",
    )


def sample_smart_album_summary(owner_id):
    return SmartAlbumSummary(
        id=uuid4(),
        name="Album",
        description="desc",
        owner_id=owner_id,
        enabled=True,
        last_synced_at=None,
        asset_count=0,
        cover_asset_id=None,
        source="user",
        status="active",
        degraded_reason=None,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
        rule=SmartAlbumRule(),
    )


@pytest.fixture
def permission_harness(monkeypatch):
    fake_session = FakeSession()
    state = {
        "user": make_user(UserRole.GUEST),
        "capabilities": make_capabilities(UserRole.GUEST),
    }
    temp_dir = workspace_temp_dir()

    app = FastAPI()
    for router in [assets.router, inbox.router, search.router, shares.router, smart_albums.router, sources.router, tags.router]:
        app.include_router(router)

    app.dependency_overrides[dependencies.get_session] = lambda: fake_session
    app.dependency_overrides[dependencies.get_current_user] = lambda: state["user"]
    app.dependency_overrides[dependencies.get_current_capabilities] = lambda: state["capabilities"]

    monkeypatch.setattr(dependencies, "ensure_platform_module_enabled", lambda session, module_id: None)

    monkeypatch.setattr(assets, "bulk_annotate_assets", lambda *args, **kwargs: None)
    monkeypatch.setattr(assets, "record_audit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        assets,
        "search_assets",
        lambda *args, **kwargs: AssetListResponse(items=[], total=0, page=1, page_size=24),
    )

    asset_file = temp_dir / "asset.png"
    asset_file.write_bytes(b"asset")
    monkeypatch.setattr(
        assets,
        "get_asset_or_404",
        lambda *args, **kwargs: SimpleNamespace(
            id=uuid4(),
            source=SimpleNamespace(root_path=str(temp_dir)),
            relative_path="asset.png",
            visual_workflow_json=None,
            visual_workflow_confidence=None,
            visual_workflow_updated_at=None,
        ),
    )
    monkeypatch.setattr(assets, "resolve_asset_path", lambda *args, **kwargs: asset_file)
    monkeypatch.setattr(
        assets.workflow_extractor,
        "extract_visual_workflow",
        lambda path: {"nodes": [], "edges": [], "confidence": 0.9},
    )

    monkeypatch.setattr(tags, "get_asset_or_404", lambda *args, **kwargs: SimpleNamespace(id=uuid4()))
    monkeypatch.setattr(tags, "log_curation_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(tags, "publish_event", lambda *args, **kwargs: None)

    inbox_item = InboxItemRead(
        id=uuid4(),
        filename="incoming.png",
        inbox_path="incoming.png",
        file_size=4,
        status="pending",
        created_at=datetime.now(tz=timezone.utc),
        target_source_id=None,
        target_source_name=None,
    )
    inbox_thumb = temp_dir / "incoming.png"
    inbox_thumb.write_bytes(b"img")
    monkeypatch.setattr(inbox, "list_inbox_items", lambda *args, **kwargs: [inbox_item])
    monkeypatch.setattr(inbox, "get_inbox_item_or_404", lambda *args, **kwargs: inbox_item)
    monkeypatch.setattr(inbox, "inbox_item_read", lambda item: item)
    monkeypatch.setattr(inbox, "inbox_thumbnail_path", lambda *args, **kwargs: inbox_thumb)
    monkeypatch.setattr(inbox, "inbox_compare_payload", lambda *args, **kwargs: {"item": inbox_item, "nearest_asset": None})
    monkeypatch.setattr(inbox, "approve_inbox_item", lambda *args, **kwargs: SimpleNamespace(id=uuid4()))
    monkeypatch.setattr(inbox, "reject_inbox_item", lambda *args, **kwargs: None)
    monkeypatch.setattr(inbox, "record_audit_event", lambda *args, **kwargs: None)

    monkeypatch.setattr(
        smart_albums,
        "create_smart_album",
        lambda session, owner_id, payload: SimpleNamespace(id=uuid4(), owner_id=owner_id, payload=payload),
    )
    monkeypatch.setattr(
        smart_albums,
        "update_smart_album",
        lambda session, album_id, owner_id, payload: SimpleNamespace(id=album_id, owner_id=owner_id, payload=payload),
    )
    monkeypatch.setattr(smart_albums, "delete_smart_album", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        smart_albums,
        "get_smart_album_or_404",
        lambda session, album_id, owner_id: SimpleNamespace(id=album_id, owner_id=owner_id),
    )
    monkeypatch.setattr(smart_albums, "sync_album", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        smart_albums,
        "smart_album_summary",
        lambda album: sample_smart_album_summary(album.owner_id),
    )

    monkeypatch.setattr(search, "search_assets", lambda *args, **kwargs: AssetListResponse(items=[], total=0, page=1, page_size=24))
    monkeypatch.setattr(
        sources,
        "list_sources",
        lambda *args, **kwargs: [
            SimpleNamespace(
                id=uuid4(),
                name="Library",
                type="mounted_fs",
                root_path=None,
                display_root_path="Library / approved root",
                status="ready",
                last_scan_at=None,
                created_at=datetime.now(tz=timezone.utc),
            )
        ],
    )
    monkeypatch.setattr(
        sources,
        "source_read_for_user",
        lambda source, current_user: SourceRead(
            id=source.id,
            name=source.name,
            type="mounted_fs",
            root_path=None,
            display_root_path=source.display_root_path,
            status="ready",
            last_scan_at=None,
            created_at=source.created_at,
        ),
    )

    client = TestClient(app)
    return client, state, fake_session


@pytest.mark.parametrize(
    ("role", "method", "path", "payload", "expected_status"),
    [
        (UserRole.GUEST, "post", "/assets/bulk-annotate", {"asset_ids": [str(uuid4())]}, 403),
        (UserRole.CURATOR, "post", "/assets/bulk-annotate", {"asset_ids": [str(uuid4())]}, 204),
        (UserRole.ADMIN, "post", "/assets/bulk-annotate", {"asset_ids": [str(uuid4())]}, 204),
        (UserRole.GUEST, "post", f"/assets/{uuid4()}/workflow/visual-extract", None, 403),
        (UserRole.CURATOR, "post", f"/assets/{uuid4()}/workflow/visual-extract", None, 200),
        (UserRole.ADMIN, "post", f"/assets/{uuid4()}/workflow/visual-extract", None, 200),
        (UserRole.GUEST, "post", "/share", {"target_type": "asset", "target_id": str(uuid4()), "allow_download": False}, 403),
        (UserRole.CURATOR, "post", "/share", {"target_type": "asset", "target_id": str(uuid4()), "allow_download": False}, 200),
        (UserRole.ADMIN, "post", "/share", {"target_type": "asset", "target_id": str(uuid4()), "allow_download": False}, 200),
        (UserRole.GUEST, "post", "/smart-albums", {"name": "Album", "rule": {}}, 403),
        (UserRole.CURATOR, "post", "/smart-albums", {"name": "Album", "rule": {}}, 201),
        (UserRole.ADMIN, "post", "/smart-albums", {"name": "Album", "rule": {}}, 201),
        (UserRole.GUEST, "patch", f"/smart-albums/{uuid4()}", {"name": "Album"}, 403),
        (UserRole.CURATOR, "patch", f"/smart-albums/{uuid4()}", {"name": "Album"}, 200),
        (UserRole.ADMIN, "patch", f"/smart-albums/{uuid4()}", {"name": "Album"}, 200),
        (UserRole.GUEST, "delete", f"/smart-albums/{uuid4()}", None, 403),
        (UserRole.CURATOR, "delete", f"/smart-albums/{uuid4()}", None, 204),
        (UserRole.ADMIN, "delete", f"/smart-albums/{uuid4()}", None, 204),
        (UserRole.GUEST, "post", f"/smart-albums/{uuid4()}/sync", None, 403),
        (UserRole.CURATOR, "post", f"/smart-albums/{uuid4()}/sync", None, 200),
        (UserRole.ADMIN, "post", f"/smart-albums/{uuid4()}/sync", None, 200),
        (UserRole.GUEST, "post", "/tags/suggestions/action", {"suggestion_id": 1, "action": "accept"}, 403),
        (UserRole.CURATOR, "post", "/tags/suggestions/action", {"suggestion_id": 1, "action": "accept"}, 200),
        (UserRole.ADMIN, "post", "/tags/suggestions/action", {"suggestion_id": 1, "action": "accept"}, 200),
    ],
)
def test_mutating_route_permissions(permission_harness, role, method, path, payload, expected_status):
    client, state, _session = permission_harness
    state["user"] = make_user(role)
    state["capabilities"] = make_capabilities(role)

    response = request(client, method, path, payload)

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    ("role", "method", "path", "payload", "expected_status"),
    [
        (UserRole.GUEST, "get", "/inbox", None, 403),
        (UserRole.GUEST, "get", f"/inbox/{uuid4()}", None, 403),
        (UserRole.GUEST, "get", f"/inbox/{uuid4()}/thumbnail", None, 403),
        (UserRole.GUEST, "get", f"/inbox/{uuid4()}/compare", None, 403),
        (UserRole.GUEST, "post", f"/inbox/{uuid4()}/approve", {"target_source_id": str(uuid4())}, 403),
        (UserRole.GUEST, "post", f"/inbox/{uuid4()}/reject", None, 403),
        (UserRole.CURATOR, "get", "/inbox", None, 200),
        (UserRole.CURATOR, "get", f"/inbox/{uuid4()}", None, 200),
        (UserRole.CURATOR, "get", f"/inbox/{uuid4()}/thumbnail", None, 200),
        (UserRole.CURATOR, "get", f"/inbox/{uuid4()}/compare", None, 200),
        (UserRole.CURATOR, "post", f"/inbox/{uuid4()}/approve", {"target_source_id": str(uuid4())}, 204),
        (UserRole.CURATOR, "post", f"/inbox/{uuid4()}/reject", None, 204),
        (UserRole.ADMIN, "get", "/inbox", None, 200),
        (UserRole.ADMIN, "post", f"/inbox/{uuid4()}/approve", {"target_source_id": str(uuid4())}, 204),
    ],
)
def test_inbox_route_permissions(permission_harness, role, method, path, payload, expected_status):
    client, state, _session = permission_harness
    state["user"] = make_user(role)
    state["capabilities"] = make_capabilities(role)

    response = request(client, method, path, payload)

    assert response.status_code == expected_status


def test_guest_readonly_routes_still_work(permission_harness):
    client, state, _session = permission_harness
    state["user"] = make_user(UserRole.GUEST)
    state["capabilities"] = make_capabilities(UserRole.GUEST)

    sources_response = client.get("/sources")
    search_response = client.get("/search")
    assets_response = client.get("/assets")

    assert sources_response.status_code == 200
    assert search_response.status_code == 200
    assert assets_response.status_code == 200


def test_role_defaults_include_new_capabilities():
    guest_caps = user_service.resolve_capabilities(SimpleNamespace(role=UserRole.GUEST), [])
    curator_caps = user_service.resolve_capabilities(SimpleNamespace(role=UserRole.CURATOR), [])
    admin_caps = user_service.resolve_capabilities(SimpleNamespace(role=UserRole.ADMIN), [])

    assert not guest_caps.can_curate_assets
    assert not guest_caps.can_manage_shares
    assert not guest_caps.can_manage_smart_albums
    assert curator_caps.can_curate_assets
    assert curator_caps.can_manage_shares
    assert curator_caps.can_manage_smart_albums
    assert admin_caps.can_curate_assets
    assert admin_caps.can_manage_shares
    assert admin_caps.can_manage_smart_albums
