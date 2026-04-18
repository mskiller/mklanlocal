from __future__ import annotations

import base64
import copy
import json
import os
import struct
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy.orm import Session

from media_indexer_backend.models.tables import CharacterCard


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHARACTER_CARD_TEXT_KEYS = ("ccv3", "chara")


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    if isinstance(value, (int, float)):
        text = str(value).strip()
        return text if text else None
    return None


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        candidate = value.strip()
        return [candidate] if candidate else []
    if not isinstance(value, list):
        return []
    values: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _string_or_none(item)
        if text is None:
            continue
        if text in seen:
            continue
        seen.add(text)
        values.append(text)
    return values


def _chunk_keyword(chunk_type: bytes, chunk_data: bytes) -> str | None:
    if chunk_type in {b"tEXt", b"zTXt"}:
        if b"\x00" not in chunk_data:
            return None
        return chunk_data.split(b"\x00", 1)[0].decode("latin-1", errors="replace")
    if chunk_type == b"iTXt":
        try:
            end = chunk_data.index(b"\x00")
        except ValueError:
            return None
        return chunk_data[:end].decode("latin-1", errors="replace")
    return None


def _iter_png_chunks(blob: bytes) -> list[tuple[bytes, bytes]]:
    if len(blob) < len(PNG_SIGNATURE) or blob[: len(PNG_SIGNATURE)] != PNG_SIGNATURE:
        return []
    offset = len(PNG_SIGNATURE)
    chunks: list[tuple[bytes, bytes]] = []
    while offset + 12 <= len(blob):
        length = struct.unpack(">I", blob[offset : offset + 4])[0]
        chunk_type = blob[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if crc_end > len(blob):
            return []
        chunks.append((chunk_type, blob[data_start:data_end]))
        offset = crc_end
        if chunk_type == b"IEND":
            break
    return chunks


def _decode_png_text_chunk(chunk_type: bytes, chunk_data: bytes) -> tuple[str, str] | None:
    try:
        if chunk_type == b"tEXt":
            keyword, text = chunk_data.split(b"\x00", 1)
            return keyword.decode("latin-1", errors="replace"), text.decode("latin-1", errors="replace")
        if chunk_type == b"zTXt":
            keyword, payload = chunk_data.split(b"\x00", 1)
            if not payload:
                return None
            text = zlib.decompress(payload[1:]).decode("latin-1", errors="replace")
            return keyword.decode("latin-1", errors="replace"), text
        if chunk_type == b"iTXt":
            keyword_end = chunk_data.index(b"\x00")
            keyword = chunk_data[:keyword_end].decode("latin-1", errors="replace")
            compression_flag = chunk_data[keyword_end + 1]
            text_start = keyword_end + 3
            language_end = chunk_data.index(b"\x00", text_start)
            translated_end = chunk_data.index(b"\x00", language_end + 1)
            text_payload = chunk_data[translated_end + 1 :]
            if compression_flag == 1:
                text_payload = zlib.decompress(text_payload)
            return keyword, text_payload.decode("utf-8", errors="replace")
    except (ValueError, zlib.error, UnicodeDecodeError):
        return None
    return None


def read_png_text_chunks(path: Path) -> dict[str, str]:
    try:
        blob = path.read_bytes()
    except OSError:
        return {}

    text_chunks: dict[str, str] = {}
    for chunk_type, chunk_data in _iter_png_chunks(blob):
        if chunk_type not in {b"tEXt", b"zTXt", b"iTXt"}:
            continue
        decoded = _decode_png_text_chunk(chunk_type, chunk_data)
        if decoded is None:
            continue
        keyword, text = decoded
        text_chunks[keyword] = text
    return text_chunks


def read_stealth_png_chunks(path: Path) -> dict[str, str]:
    try:
        import numpy as np
        from PIL import Image
    except Exception:  # noqa: BLE001
        return {}

    result: dict[str, str] = {}
    try:
        with Image.open(path) as img:
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            alpha = np.array(img)[:, :, 3].flatten()
    except Exception:  # noqa: BLE001
        return {}

    if len(alpha) < 64:
        return {}

    magic_bits = alpha[:32] & 1
    magic_val = int("".join(str(bit) for bit in magic_bits), 2)
    magic_uncompressed = 0x53746C73
    magic_compressed = 0x53746C63
    if magic_val not in {magic_uncompressed, magic_compressed}:
        return {}

    length_bits = alpha[32:64] & 1
    payload_length = int("".join(str(bit) for bit in length_bits), 2)
    if payload_length <= 0 or (64 + payload_length) > len(alpha):
        return {}

    bit_stream = alpha[64 : 64 + payload_length] & 1
    byte_count = payload_length // 8
    if byte_count <= 0:
        return {}

    try:
        raw_bytes = bytes(
            int("".join(str(bit) for bit in bit_stream[index * 8 : (index + 1) * 8]), 2)
            for index in range(byte_count)
        )
        if magic_val == magic_compressed:
            raw_bytes = zlib.decompress(raw_bytes)
        payload = json.loads(raw_bytes.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return {}

    if not isinstance(payload, dict):
        return {}
    for key, value in payload.items():
        if isinstance(value, str):
            result.setdefault(str(key).capitalize(), value)
        else:
            result.setdefault(str(key).capitalize(), json.dumps(value))
    return result


def extract_png_metadata_chunks(path: Path) -> dict[str, str]:
    result = read_png_text_chunks(path)
    for key, value in read_stealth_png_chunks(path).items():
        result.setdefault(key, value)
    return result


def _character_card_value(raw_metadata: Mapping[str, Any], key: str) -> str | None:
    for raw_key, raw_value in raw_metadata.items():
        if str(raw_key).strip().lower() != key:
            continue
        if isinstance(raw_value, bytes):
            return raw_value.decode("utf-8", errors="replace")
        if isinstance(raw_value, str):
            return raw_value
    return None


def normalize_character_card_payload(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None

    card = copy.deepcopy(dict(payload))
    raw_data = card.get("data")
    data = copy.deepcopy(raw_data) if isinstance(raw_data, Mapping) else {}

    name = _string_or_none(data.get("name")) or _string_or_none(card.get("name")) or "Unnamed Character"
    description = _string_or_none(data.get("description")) or _string_or_none(card.get("description")) or ""
    personality = _string_or_none(data.get("personality")) or _string_or_none(card.get("personality")) or ""
    scenario = _string_or_none(data.get("scenario")) or _string_or_none(card.get("scenario")) or ""
    first_message = _string_or_none(data.get("first_mes")) or _string_or_none(card.get("first_mes")) or ""
    message_examples = _string_or_none(data.get("mes_example")) or _string_or_none(card.get("mes_example")) or ""
    creator_notes = _string_or_none(data.get("creator_notes")) or _string_or_none(card.get("creatorcomment")) or ""
    system_prompt = _string_or_none(data.get("system_prompt")) or ""
    post_history_instructions = _string_or_none(data.get("post_history_instructions")) or ""
    creator = _string_or_none(data.get("creator")) or _string_or_none(card.get("creator"))
    character_version = _string_or_none(data.get("character_version"))
    tags = _string_list(data.get("tags") if data.get("tags") is not None else card.get("tags"))
    alternate_greetings = _string_list(data.get("alternate_greetings"))
    group_only_greetings = _string_list(data.get("group_only_greetings"))
    extensions = copy.deepcopy(data.get("extensions")) if isinstance(data.get("extensions"), Mapping) else {}

    card["spec"] = "chara_card_v3"
    card["spec_version"] = "3.0"
    card["name"] = name
    card["description"] = description
    card["personality"] = personality
    card["scenario"] = scenario
    card["first_mes"] = first_message
    card["mes_example"] = message_examples
    card["creatorcomment"] = creator_notes
    card["tags"] = tags
    if creator is not None or "creator" in card:
        card["creator"] = creator

    card["data"] = {
        **data,
        "name": name,
        "description": description,
        "personality": personality,
        "scenario": scenario,
        "first_mes": first_message,
        "mes_example": message_examples,
        "creator_notes": creator_notes,
        "system_prompt": system_prompt,
        "post_history_instructions": post_history_instructions,
        "creator": creator,
        "character_version": character_version,
        "tags": tags,
        "alternate_greetings": alternate_greetings,
        "group_only_greetings": group_only_greetings,
        "extensions": extensions,
    }
    return card


def extract_character_card_from_raw_metadata(raw_metadata: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not raw_metadata:
        return None
    for key in CHARACTER_CARD_TEXT_KEYS:
        encoded = _character_card_value(raw_metadata, key)
        if encoded is None:
            continue
        try:
            decoded = json.loads(base64.b64decode(encoded).decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        canonical = normalize_character_card_payload(decoded)
        if canonical is not None:
            return canonical
    return None


def character_card_search_fields(card: Mapping[str, Any] | None) -> dict[str, Any]:
    if not card:
        return {"character_card_detected": False}

    data = card.get("data") if isinstance(card.get("data"), Mapping) else {}
    return {
        "character_card_detected": True,
        "character_name": _string_or_none(data.get("name")) or _string_or_none(card.get("name")),
        "character_creator": _string_or_none(data.get("creator")) or _string_or_none(card.get("creator")),
        "character_description": _string_or_none(data.get("description")) or _string_or_none(card.get("description")),
        "character_personality": _string_or_none(data.get("personality")) or _string_or_none(card.get("personality")),
        "character_scenario": _string_or_none(data.get("scenario")) or _string_or_none(card.get("scenario")),
        "character_first_message": _string_or_none(data.get("first_mes")) or _string_or_none(card.get("first_mes")),
        "character_message_examples": _string_or_none(data.get("mes_example")) or _string_or_none(card.get("mes_example")),
        "character_creator_notes": _string_or_none(data.get("creator_notes")) or _string_or_none(card.get("creatorcomment")),
        "character_system_prompt": _string_or_none(data.get("system_prompt")),
        "character_post_history_instructions": _string_or_none(data.get("post_history_instructions")),
        "character_version": _string_or_none(data.get("character_version")),
        "character_tags": _string_list(data.get("tags") if data.get("tags") is not None else card.get("tags")),
        "character_alternate_greetings": _string_list(data.get("alternate_greetings")),
        "character_group_only_greetings": _string_list(data.get("group_only_greetings")),
        "character_card_spec": _string_or_none(card.get("spec")) or "chara_card_v3",
        "character_card_spec_version": _string_or_none(card.get("spec_version")) or "3.0",
    }


def character_card_summary_fields(card: Mapping[str, Any]) -> dict[str, Any]:
    data = card.get("data") if isinstance(card.get("data"), Mapping) else {}
    return {
        "name": _string_or_none(data.get("name")) or _string_or_none(card.get("name")) or "Unnamed Character",
        "creator": _string_or_none(data.get("creator")) or _string_or_none(card.get("creator")),
        "description": _string_or_none(data.get("description")) or _string_or_none(card.get("description")),
        "spec": _string_or_none(card.get("spec")) or "chara_card_v3",
        "spec_version": _string_or_none(card.get("spec_version")) or "3.0",
        "tags_json": _string_list(data.get("tags") if data.get("tags") is not None else card.get("tags")),
        "card_json": copy.deepcopy(dict(card)),
    }


def sync_character_card_record(
    session: Session,
    asset_id,
    card: Mapping[str, Any] | None,
    *,
    extracted_at: datetime | None = None,
) -> CharacterCard | None:
    existing = session.get(CharacterCard, asset_id)
    if card is None:
        if existing is not None:
            session.delete(existing)
            session.flush()
        return None

    timestamp = extracted_at or utcnow()
    payload = character_card_summary_fields(card)
    if existing is None:
        existing = CharacterCard(
            asset_id=asset_id,
            extracted_at=timestamp,
            updated_at=timestamp,
            **payload,
        )
        session.add(existing)
    else:
        existing.name = payload["name"]
        existing.creator = payload["creator"]
        existing.description = payload["description"]
        existing.spec = payload["spec"]
        existing.spec_version = payload["spec_version"]
        existing.tags_json = payload["tags_json"]
        existing.card_json = payload["card_json"]
        existing.extracted_at = timestamp
        existing.updated_at = timestamp
    session.flush()
    return existing


def build_legacy_character_card(card: Mapping[str, Any]) -> dict[str, Any]:
    legacy = copy.deepcopy(dict(card))
    data = legacy.get("data") if isinstance(legacy.get("data"), Mapping) else {}
    legacy["spec"] = "chara_card_v2"
    legacy["spec_version"] = "2.0"
    legacy["name"] = _string_or_none(data.get("name")) or _string_or_none(legacy.get("name")) or "Unnamed Character"
    legacy["description"] = _string_or_none(data.get("description")) or _string_or_none(legacy.get("description")) or ""
    legacy["personality"] = _string_or_none(data.get("personality")) or _string_or_none(legacy.get("personality")) or ""
    legacy["scenario"] = _string_or_none(data.get("scenario")) or _string_or_none(legacy.get("scenario")) or ""
    legacy["first_mes"] = _string_or_none(data.get("first_mes")) or _string_or_none(legacy.get("first_mes")) or ""
    legacy["mes_example"] = _string_or_none(data.get("mes_example")) or _string_or_none(legacy.get("mes_example")) or ""
    legacy["creatorcomment"] = _string_or_none(data.get("creator_notes")) or _string_or_none(legacy.get("creatorcomment")) or ""
    legacy["tags"] = _string_list(data.get("tags") if data.get("tags") is not None else legacy.get("tags"))
    legacy["data"] = {
        **data,
        "name": legacy["name"],
        "description": legacy["description"],
        "personality": legacy["personality"],
        "scenario": legacy["scenario"],
        "first_mes": legacy["first_mes"],
        "mes_example": legacy["mes_example"],
        "creator_notes": legacy["creatorcomment"],
        "tags": legacy["tags"],
        "alternate_greetings": _string_list(data.get("alternate_greetings")),
        "group_only_greetings": _string_list(data.get("group_only_greetings")),
        "extensions": copy.deepcopy(data.get("extensions")) if isinstance(data.get("extensions"), Mapping) else {},
    }
    return legacy


def _encode_character_card_value(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _encode_text_chunk(keyword: str, value: str) -> bytes:
    return keyword.encode("latin-1") + b"\x00" + value.encode("latin-1")


def write_character_card_png(path: Path, card: Mapping[str, Any]) -> None:
    blob = path.read_bytes()
    chunks = _iter_png_chunks(blob)
    if not chunks:
        raise ValueError("File is not a valid PNG.")

    ccv3_value = _encode_character_card_value(card)
    chara_value = _encode_character_card_value(build_legacy_character_card(card))

    rewritten_chunks: list[tuple[bytes, bytes]] = []
    wrote_character_chunks = False
    for chunk_type, chunk_data in chunks:
        keyword = _chunk_keyword(chunk_type, chunk_data)
        if keyword is not None and keyword.lower() in CHARACTER_CARD_TEXT_KEYS:
            continue
        if chunk_type == b"IEND" and not wrote_character_chunks:
            rewritten_chunks.append((b"tEXt", _encode_text_chunk("chara", chara_value)))
            rewritten_chunks.append((b"tEXt", _encode_text_chunk("ccv3", ccv3_value)))
            wrote_character_chunks = True
        rewritten_chunks.append((chunk_type, chunk_data))

    if not wrote_character_chunks:
        raise ValueError("PNG is missing an IEND chunk.")

    temp_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        with temp_path.open("wb") as handle:
            handle.write(PNG_SIGNATURE)
            for chunk_type, chunk_data in rewritten_chunks:
                handle.write(struct.pack(">I", len(chunk_data)))
                handle.write(chunk_type)
                handle.write(chunk_data)
                crc = zlib.crc32(chunk_type)
                crc = zlib.crc32(chunk_data, crc)
                handle.write(struct.pack(">I", crc & 0xFFFFFFFF))
        try:
            os.replace(temp_path, path)
        except PermissionError:
            path.write_bytes(temp_path.read_bytes())
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink(missing_ok=True)
            except PermissionError:
                pass
