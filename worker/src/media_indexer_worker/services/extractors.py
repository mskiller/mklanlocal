from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from media_indexer_backend.services.character_cards import extract_png_metadata_chunks as shared_extract_png_metadata_chunks

logger = logging.getLogger(__name__)


def _run_json_command(command: list[str]) -> dict | list | None:
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        logger.warning("metadata command failed", extra={"command": command, "error": str(exc)})
        return None

    if not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning("metadata command returned invalid json", extra={"command": command})
        return None


def extract_exiftool(path: Path) -> dict:
    payload = _run_json_command(["exiftool", "-j", "-n", str(path)])
    if isinstance(payload, list) and payload:
        return payload[0]
    return {}


def extract_ffprobe(path: Path) -> dict:
    payload = _run_json_command(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    if isinstance(payload, dict):
        return payload
    return {}


def extract_png_metadata_chunks(path: Path) -> dict:
    return shared_extract_png_metadata_chunks(path)
