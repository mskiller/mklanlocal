from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def _parse_json_value(value: Any) -> dict | list | None:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


def build_comfyui_workflow_export(
    *,
    asset_id: str,
    filename: str,
    normalized_metadata: dict[str, Any],
    raw_metadata: dict[str, Any],
) -> dict[str, Any] | None:
    if normalized_metadata.get("generator") != "comfyui":
        return None

    prompt = _parse_json_value(raw_metadata.get("Prompt"))
    workflow = _parse_json_value(raw_metadata.get("Workflow"))
    if prompt is None and workflow is None:
        return None

    payload: dict[str, Any] = {
        "asset_id": asset_id,
        "filename": filename,
        "generator": "comfyui",
        "exported_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    if prompt is not None:
        payload["prompt"] = prompt
    if workflow is not None:
        payload["workflow"] = workflow
    return payload
