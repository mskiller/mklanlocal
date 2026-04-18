from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from media_indexer_backend.api import dependencies
from media_indexer_backend.api.routes import scan_jobs
from media_indexer_backend.models.enums import UserRole


class FakeSession:
    def commit(self):
        return None


def build_client(user):
    app = FastAPI()
    app.include_router(scan_jobs.router)
    app.dependency_overrides[dependencies.get_session] = lambda: FakeSession()
    app.dependency_overrides[dependencies.get_current_user] = lambda: user
    return TestClient(app)


def test_clear_done_jobs_requires_admin():
    client = build_client(SimpleNamespace(id=uuid4(), username="guest", role=UserRole.GUEST))

    response = client.delete("/scan-jobs/done")

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required."


def test_clear_done_jobs_returns_deleted_count(monkeypatch):
    captured = {}

    monkeypatch.setattr(scan_jobs, "clear_terminal_scan_jobs", lambda session: 3)
    monkeypatch.setattr(
        scan_jobs,
        "record_audit_event",
        lambda session, actor, action, resource_type, resource_id, details: captured.update(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        ),
    )

    client = build_client(SimpleNamespace(id=uuid4(), username="admin", role=UserRole.ADMIN))

    response = client.delete("/scan-jobs/done")

    assert response.status_code == 200
    assert response.json() == {"deleted_count": 3}
    assert captured == {
        "actor": "admin",
        "action": "scan_jobs.cleared",
        "resource_type": "scan_job",
        "resource_id": None,
        "details": {"deleted_count": 3},
    }
