from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from media_indexer_backend.api import dependencies
from media_indexer_backend.api.routes import assets, sources
from media_indexer_backend.models.enums import MediaType, UserRole
from media_indexer_backend.schemas.auth import AuthCapabilities
from media_indexer_backend.schemas.image_ops import CropSpec
from media_indexer_backend.schemas.source import SourceUploadRead
from media_indexer_backend.services import asset_service, source_service


class FakeSession:
    def commit(self):
        return None


def _make_user(role: UserRole):
    return SimpleNamespace(id=uuid4(), username=role.value, role=role)


def _make_capabilities(*, can_upload_assets: bool) -> AuthCapabilities:
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
        can_upload_assets=can_upload_assets,
        can_view_admin=False,
        allowed_source_ids="all",
    )


def _test_upload_file(name: str = "image.png"):
    image = Image.new("RGB", (60, 40), (20, 60, 120))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return ("file", (name, buffer.getvalue(), "image/png"))


def test_upload_edited_route_uses_crop_spec(monkeypatch):
    app = FastAPI()
    app.include_router(sources.router)
    app.dependency_overrides[dependencies.get_session] = lambda: FakeSession()
    app.dependency_overrides[dependencies.get_current_user] = lambda: _make_user(UserRole.CURATOR)
    app.dependency_overrides[dependencies.get_current_capabilities] = lambda: _make_capabilities(can_upload_assets=True)

    captured: dict = {}
    source_id = uuid4()
    upload_response = SourceUploadRead(
        source_id=source_id,
        folder="drafts",
        uploaded_files=["drafts/image-crop.png"],
        scan_job_id=None,
    )
    monkeypatch.setattr(sources, "get_source_or_404", lambda *args, **kwargs: SimpleNamespace(id=source_id, name="upload"))
    monkeypatch.setattr(
        sources,
        "upload_edited_image_to_source",
        lambda session, passed_source_id, **kwargs: captured.update(
            {
                "source_id": passed_source_id,
                "folder": kwargs["folder"],
                "crop_spec": kwargs["crop_spec"].model_dump(),
                "filename": kwargs["file"].filename,
            }
        )
        or upload_response,
    )
    monkeypatch.setattr(sources, "record_audit_event", lambda *args, **kwargs: None)

    client = TestClient(app)
    response = client.post(
        f"/sources/{source_id}/upload-edited",
        files=[_test_upload_file()],
        data={
            "folder": "drafts",
            "rotation_quadrants": "1",
            "crop_x": "4",
            "crop_y": "6",
            "crop_width": "20",
            "crop_height": "12",
        },
    )

    assert response.status_code == 200
    assert captured == {
        "source_id": source_id,
        "folder": "drafts",
        "crop_spec": {
            "rotation_quadrants": 1,
            "crop_x": 4,
            "crop_y": 6,
            "crop_width": 20,
            "crop_height": 12,
        },
        "filename": "image.png",
    }


def test_asset_crop_draft_route_requires_upload_access(monkeypatch):
    app = FastAPI()
    app.include_router(assets.router)
    app.dependency_overrides[dependencies.get_session] = lambda: FakeSession()
    app.dependency_overrides[dependencies.get_current_user] = lambda: _make_user(UserRole.GUEST)
    app.dependency_overrides[dependencies.get_current_capabilities] = lambda: _make_capabilities(can_upload_assets=False)
    monkeypatch.setattr(assets, "record_audit_event", lambda *args, **kwargs: None)

    client = TestClient(app)
    response = client.post(
        f"/assets/{uuid4()}/crop-draft",
        json={
            "folder": "explorer-crops",
            "rotation_quadrants": 0,
            "crop_x": 1,
            "crop_y": 2,
            "crop_width": 30,
            "crop_height": 20,
        },
    )

    assert response.status_code == 403


def test_asset_crop_draft_route_returns_upload_payload(monkeypatch):
    app = FastAPI()
    app.include_router(assets.router)
    app.dependency_overrides[dependencies.get_session] = lambda: FakeSession()
    app.dependency_overrides[dependencies.get_current_user] = lambda: _make_user(UserRole.CURATOR)
    app.dependency_overrides[dependencies.get_current_capabilities] = lambda: _make_capabilities(can_upload_assets=True)

    captured: dict = {}
    payload = SourceUploadRead(
        source_id=uuid4(),
        folder="explorer-crops",
        uploaded_files=["explorer-crops/example-crop.png"],
        scan_job_id=None,
    )
    monkeypatch.setattr(
        assets,
        "create_asset_crop_draft",
        lambda session, asset_id, **kwargs: captured.update(
            {
                "asset_id": asset_id,
                "folder": kwargs["folder"],
                "crop_spec": kwargs["crop_spec"].model_dump(),
            }
        )
        or payload,
    )
    monkeypatch.setattr(assets, "record_audit_event", lambda *args, **kwargs: None)

    client = TestClient(app)
    asset_id = uuid4()
    response = client.post(
        f"/assets/{asset_id}/crop-draft",
        json={
            "rotation_quadrants": 3,
            "crop_x": 12,
            "crop_y": 14,
            "crop_width": 128,
            "crop_height": 96,
        },
    )

    assert response.status_code == 200
    assert response.json()["uploaded_files"] == ["explorer-crops/example-crop.png"]
    assert captured == {
        "asset_id": asset_id,
        "folder": None,
        "crop_spec": {
            "folder": None,
            "rotation_quadrants": 3,
            "crop_x": 12,
            "crop_y": 14,
            "crop_width": 128,
            "crop_height": 96,
        },
    }


def test_create_asset_crop_draft_rejects_non_image(monkeypatch):
    monkeypatch.setattr(
        asset_service,
        "get_asset_or_404",
        lambda *args, **kwargs: SimpleNamespace(media_type=MediaType.VIDEO),
    )

    with pytest.raises(HTTPException) as exc_info:
        source_service.create_asset_crop_draft(
            SimpleNamespace(),
            uuid4(),
            folder=None,
            crop_spec=CropSpec(rotation_quadrants=0, crop_x=0, crop_y=0, crop_width=10, crop_height=10),
            current_user=None,
        )

    assert exc_info.value.status_code == 400
    assert "Only image assets" in exc_info.value.detail
