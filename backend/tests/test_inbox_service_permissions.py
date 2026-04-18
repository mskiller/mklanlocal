from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException

from media_indexer_backend.services import inbox_service


class FakeExecuteResult:
    def scalar_one_or_none(self):
        return None


class FakeSession:
    def execute(self, query):
        del query
        return FakeExecuteResult()

    def delete(self, item):
        del item

    def flush(self):
        return None


def workspace_temp_dir() -> Path:
    root = Path(__file__).resolve().parent / "_tmp"
    path = root / str(uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_approve_inbox_item_uses_current_user_for_target_source_scope(monkeypatch):
    current_user = SimpleNamespace(id=uuid4())
    temp_dir = workspace_temp_dir()
    upload_root = temp_dir / "upload"
    upload_root.mkdir()
    source_file = upload_root / "incoming.png"
    source_file.write_bytes(b"image")

    target_root = temp_dir / "target"
    target_root.mkdir()

    inbox_item = SimpleNamespace(
        id=uuid4(),
        status="pending",
        target_source_id=uuid4(),
        inbox_path="incoming.png",
        filename="incoming.png",
        reviewed_at=None,
        reviewed_by=None,
    )

    captured = {}

    monkeypatch.setattr(inbox_service, "get_inbox_item_or_404", lambda session, item_id: inbox_item)
    monkeypatch.setattr(inbox_service, "_upload_source", lambda session: SimpleNamespace(root_path=str(upload_root)))

    def fake_get_source_or_404(session, source_id, current_user=None):
        captured["current_user"] = current_user
        return SimpleNamespace(id=source_id, root_path=str(target_root))

    monkeypatch.setattr(inbox_service, "get_source_or_404", fake_get_source_or_404)
    monkeypatch.setattr(
        inbox_service,
        "resolve_asset_path",
        lambda root_path, relative_path: SimpleNamespace(unlink=lambda missing_ok=True: None),
    )
    monkeypatch.setattr(
        inbox_service,
        "resolve_writable_directory_path",
        lambda root_path, relative_path: (Path(root_path), ""),
    )
    monkeypatch.setattr(inbox_service.shutil, "copy2", lambda source, destination: None)
    monkeypatch.setattr(inbox_service, "queue_scan", lambda session, source_id: SimpleNamespace(id=uuid4()))

    session = FakeSession()
    inbox_service.approve_inbox_item(session, inbox_item.id, current_user=current_user)

    assert captured["current_user"] is current_user


def test_inbox_compare_hides_nearest_asset_outside_scope(monkeypatch):
    current_user = SimpleNamespace(id=uuid4())
    item = SimpleNamespace(
        id=uuid4(),
        filename="incoming.png",
        inbox_path="incoming.png",
        file_size=4,
        phash=None,
        clip_distance_min=None,
        nearest_asset_id=uuid4(),
        status="pending",
        target_source_id=None,
        target_source=None,
        created_at=datetime.now(tz=timezone.utc),
        reviewed_at=None,
        reviewed_by=None,
        error_message=None,
    )

    monkeypatch.setattr(inbox_service, "get_inbox_item_or_404", lambda session, item_id: item)
    monkeypatch.setattr(
        inbox_service,
        "get_asset_or_404",
        lambda session, asset_id, current_user=None: (_ for _ in ()).throw(
            HTTPException(status_code=404, detail="Asset not found.")
        ),
    )

    payload = inbox_service.inbox_compare_payload(SimpleNamespace(), item.id, current_user=current_user)

    assert payload["item"].id == item.id
    assert payload["nearest_asset"] is None
