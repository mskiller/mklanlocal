from __future__ import annotations

import base64
import json
import struct
import zlib
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from media_indexer_backend.api import dependencies
from media_indexer_backend.api.routes import characters
from media_indexer_backend.models.enums import MediaType, UserRole
from media_indexer_backend.schemas.auth import AuthCapabilities
from media_indexer_backend.schemas.character import CharacterCardDetail, CharacterCardListResponse, CharacterCardSummary
from media_indexer_backend.services.character_cards import (
    extract_character_card_from_raw_metadata,
    normalize_character_card_payload,
    read_png_text_chunks,
    sync_character_card_record,
    write_character_card_png,
)
from media_indexer_backend.services.extractors import extract_png_metadata_from_file
from media_indexer_backend.services.metadata import normalize_metadata


def workspace_temp_dir() -> Path:
    root = Path(__file__).resolve().parent / "_tmp"
    path = root / str(uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


def sample_card_payload(name: str = "Candice") -> dict:
    return {
        "name": name,
        "description": "Quiet but observant.",
        "personality": "Calm, witty, and slightly teasing.",
        "scenario": "A rainy evening in the city.",
        "first_mes": "You found me at the cafe window again.",
        "mes_example": "<START> Example dialog.",
        "creatorcomment": "Original creator note.",
        "avatar": "none",
        "chat": "Candice",
        "talkativeness": 0.45,
        "fav": False,
        "tags": ["rain", "city", "slice-of-life"],
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "create_date": "2026-04-18",
        "data": {
            "name": name,
            "description": "Quiet but observant.",
            "personality": "Calm, witty, and slightly teasing.",
            "scenario": "A rainy evening in the city.",
            "first_mes": "You found me at the cafe window again.",
            "mes_example": "<START> Example dialog.",
            "creator_notes": "Original creator note.",
            "system_prompt": "Stay in character.",
            "post_history_instructions": "Keep the tone intimate.",
            "creator": "MsKiller",
            "character_version": "v1",
            "tags": ["rain", "city", "slice-of-life"],
            "alternate_greetings": ["I saved you a seat."],
            "group_only_greetings": ["Looks like everyone made it."],
            "extensions": {"mood": "soft"},
        },
    }


def create_png(path: Path) -> Path:
    Image.new("RGBA", (4, 4), (255, 255, 255, 255)).save(path, "PNG")
    return path


def _encode_text_chunk(keyword: str, value: str) -> bytes:
    return keyword.encode("latin-1") + b"\x00" + value.encode("latin-1")


def inject_text_chunks(path: Path, *, payloads: dict[str, dict]) -> None:
    blob = path.read_bytes()
    assert blob[:8] == b"\x89PNG\r\n\x1a\n"
    offset = 8
    chunks: list[tuple[bytes, bytes]] = []
    while offset + 12 <= len(blob):
        length = struct.unpack(">I", blob[offset : offset + 4])[0]
        chunk_type = blob[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        chunks.append((chunk_type, blob[data_start:data_end]))
        offset = crc_end
        if chunk_type == b"IEND":
            break

    rewritten: list[tuple[bytes, bytes]] = []
    for chunk_type, chunk_data in chunks:
        if chunk_type == b"IEND":
            for key, payload in payloads.items():
                encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).decode("ascii")
                rewritten.append((b"tEXt", _encode_text_chunk(key, encoded)))
        rewritten.append((chunk_type, chunk_data))

    with path.open("wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        for chunk_type, chunk_data in rewritten:
            handle.write(struct.pack(">I", len(chunk_data)))
            handle.write(chunk_type)
            handle.write(chunk_data)
            crc = zlib.crc32(chunk_type)
            crc = zlib.crc32(chunk_data, crc)
            handle.write(struct.pack(">I", crc & 0xFFFFFFFF))


def character_detail(asset_id: str) -> CharacterCardDetail:
    return CharacterCardDetail(
        asset_id=asset_id,
        source_id=str(uuid4()),
        source_name="Sample Source",
        filename="candice.png",
        relative_path="candice.png",
        preview_url="/assets/preview",
        content_url="/assets/content",
        name="Candice",
        creator="MsKiller",
        description="Quiet but observant.",
        spec="chara_card_v3",
        spec_version="3.0",
        tags=["rain", "city"],
        extracted_at="2026-04-18T00:00:00Z",
        updated_at="2026-04-18T00:00:00Z",
        first_message="Hi.",
        message_examples="Example",
        personality="Calm",
        scenario="Cafe",
        creator_notes="Note",
        system_prompt="Prompt",
        post_history_instructions="History",
        character_version="v1",
        alternate_greetings=["Hello"],
        group_only_greetings=["Group hello"],
        canonical_card={"spec": "chara_card_v3", "data": {"name": "Candice"}},
    )


class FakeCharacterSession:
    def __init__(self):
        self.records = {}

    def get(self, model, key):
        del model
        return self.records.get(key)

    def add(self, item):
        self.records[item.asset_id] = item

    def delete(self, item):
        self.records.pop(item.asset_id, None)

    def flush(self):
        return None


def make_capabilities(can_curate: bool) -> AuthCapabilities:
    return AuthCapabilities(
        can_manage_sources=False,
        can_run_scans=False,
        can_review_compare=can_curate,
        can_curate_assets=can_curate,
        can_reset=False,
        can_manage_users=False,
        can_manage_collections=can_curate,
        can_manage_shares=can_curate,
        can_manage_smart_albums=can_curate,
        can_upload_assets=can_curate,
        can_view_admin=False,
        allowed_source_ids="all",
    )


def build_character_client(role: UserRole, monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(characters.router)
    fake_session = SimpleNamespace(commit=lambda: None)
    user = SimpleNamespace(id=uuid4(), username=role.value, role=role)
    app.dependency_overrides[dependencies.get_session] = lambda: fake_session
    app.dependency_overrides[dependencies.get_current_user] = lambda: user
    app.dependency_overrides[dependencies.get_current_capabilities] = lambda: make_capabilities(role in {UserRole.ADMIN, UserRole.CURATOR})

    monkeypatch.setattr(dependencies, "ensure_platform_module_enabled", lambda session, module_id: None)
    monkeypatch.setattr(
        characters,
        "list_character_cards",
        lambda *args, **kwargs: CharacterCardListResponse(
            items=[
                CharacterCardSummary(
                    asset_id=uuid4(),
                    source_id=uuid4(),
                    source_name="Sample Source",
                    filename="candice.png",
                    relative_path="candice.png",
                    preview_url="/assets/preview",
                    content_url="/assets/content",
                    name="Candice",
                    creator="MsKiller",
                    description="Quiet but observant.",
                    spec="chara_card_v3",
                    spec_version="3.0",
                    tags=["rain"],
                    extracted_at="2026-04-18T00:00:00Z",
                    updated_at="2026-04-18T00:00:00Z",
                )
            ],
            total=1,
            page=1,
            page_size=24,
        ),
    )
    monkeypatch.setattr(characters, "get_character_card_detail", lambda *args, **kwargs: character_detail(str(uuid4())))
    monkeypatch.setattr(characters, "update_character_card", lambda *args, **kwargs: character_detail(str(uuid4())))
    monkeypatch.setattr(characters, "record_audit_event", lambda *args, **kwargs: None)
    return TestClient(app)


def test_extract_png_metadata_reads_raw_ccv3_text_chunk():
    path = create_png(workspace_temp_dir() / "card.png")
    inject_text_chunks(path, payloads={"ccv3": sample_card_payload()})

    raw = extract_png_metadata_from_file(path)
    card = extract_character_card_from_raw_metadata(raw)

    assert "ccv3" in raw
    assert card is not None
    assert card["spec"] == "chara_card_v3"
    assert card["data"]["creator"] == "MsKiller"


def test_extract_character_card_falls_back_to_legacy_chara_chunk():
    path = create_png(workspace_temp_dir() / "legacy.png")
    legacy = sample_card_payload("Legacy Candice")
    legacy["spec"] = "chara_card_v2"
    legacy["spec_version"] = "2.0"
    inject_text_chunks(path, payloads={"chara": legacy})

    raw = read_png_text_chunks(path)
    card = extract_character_card_from_raw_metadata(raw)

    assert card is not None
    assert card["spec"] == "chara_card_v3"
    assert card["name"] == "Legacy Candice"


def test_plain_png_without_card_returns_no_character_payload():
    path = create_png(workspace_temp_dir() / "plain.png")

    raw = extract_png_metadata_from_file(path)

    assert extract_character_card_from_raw_metadata(raw) is None


def test_normalize_metadata_adds_searchable_character_fields():
    path = create_png(workspace_temp_dir() / "metadata.png")
    inject_text_chunks(path, payloads={"ccv3": sample_card_payload()})

    raw = extract_png_metadata_from_file(path)
    normalized = normalize_metadata(media_type=MediaType.IMAGE, exif=raw, ffprobe={})

    assert normalized["metadata_version"] == 7
    assert normalized["character_card_detected"] is True
    assert normalized["character_name"] == "Candice"
    assert normalized["character_creator"] == "MsKiller"
    assert normalized["character_tags"] == ["rain", "city", "slice-of-life"]


def test_sync_character_card_record_creates_and_removes_records():
    session = FakeCharacterSession()
    asset_id = uuid4()
    card = normalize_character_card_payload(sample_card_payload())

    record = sync_character_card_record(session, asset_id, card)

    assert record is not None
    assert session.records[asset_id].name == "Candice"
    assert session.records[asset_id].creator == "MsKiller"

    removed = sync_character_card_record(session, asset_id, None)

    assert removed is None
    assert asset_id not in session.records


def test_write_character_card_png_round_trip_updates_ccv3_and_chara():
    path = create_png(workspace_temp_dir() / "roundtrip.png")
    base_card = normalize_character_card_payload(sample_card_payload())
    assert base_card is not None

    write_character_card_png(path, base_card)
    first_raw = read_png_text_chunks(path)
    first_ccv3 = json.loads(base64.b64decode(first_raw["ccv3"]).decode("utf-8"))
    first_chara = json.loads(base64.b64decode(first_raw["chara"]).decode("utf-8"))

    assert first_ccv3["spec"] == "chara_card_v3"
    assert first_chara["spec"] == "chara_card_v2"

    updated = normalize_character_card_payload(first_ccv3)
    assert updated is not None
    updated["name"] = "Candice Updated"
    updated["data"]["name"] = "Candice Updated"
    updated["data"]["alternate_greetings"] = ["I kept the window seat for you."]

    write_character_card_png(path, updated)
    second_raw = read_png_text_chunks(path)
    second_ccv3 = json.loads(base64.b64decode(second_raw["ccv3"]).decode("utf-8"))
    second_chara = json.loads(base64.b64decode(second_raw["chara"]).decode("utf-8"))

    assert second_ccv3["name"] == "Candice Updated"
    assert second_ccv3["data"]["alternate_greetings"] == ["I kept the window seat for you."]
    assert second_chara["name"] == "Candice Updated"
    assert second_chara["spec"] == "chara_card_v2"


def test_guest_can_read_character_routes(monkeypatch):
    client = build_character_client(UserRole.GUEST, monkeypatch)

    list_response = client.get("/characters")
    detail_response = client.get(f"/characters/{uuid4()}")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200


def test_guest_cannot_patch_character_route(monkeypatch):
    client = build_character_client(UserRole.GUEST, monkeypatch)

    response = client.patch(f"/characters/{uuid4()}", json={"name": "Nope"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Asset curation access required."


def test_curator_can_patch_character_route(monkeypatch):
    client = build_character_client(UserRole.CURATOR, monkeypatch)

    response = client.patch(f"/characters/{uuid4()}", json={"name": "Candice Updated"})

    assert response.status_code == 200


def test_admin_can_patch_character_route(monkeypatch):
    client = build_character_client(UserRole.ADMIN, monkeypatch)

    response = client.patch(f"/characters/{uuid4()}", json={"name": "Candice Updated"})

    assert response.status_code == 200
