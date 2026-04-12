from __future__ import annotations

from pathlib import Path, PurePosixPath

from fastapi import HTTPException, status

from media_indexer_backend.core.config import get_settings


def validate_source_root(root_path: str) -> str:
    settings = get_settings()
    candidate = Path(root_path).expanduser()
    if not candidate.is_absolute():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source root must be absolute.")

    resolved = candidate.resolve(strict=False)
    if not resolved.exists() or not resolved.is_dir():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source root does not exist on the server.")

    allowed = settings.allowed_source_root_paths
    if not any(resolved == base or resolved.is_relative_to(base) for base in allowed):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source root is outside the approved server roots.",
        )
    return str(resolved)


def normalize_relative_path(relative_path: str | None) -> str:
    if not relative_path:
        return ""

    normalized = relative_path.replace("\\", "/").strip()
    parts: list[str] = []
    for part in PurePosixPath(normalized).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Relative path escapes the approved root.")
        parts.append(part)
    return "/".join(parts)


def _resolve_source_path(root_path: str, relative_path: str | None) -> tuple[Path, str]:
    root = Path(validate_source_root(root_path)).resolve(strict=True)
    normalized = normalize_relative_path(relative_path)
    candidate = (root / Path(*normalized.split("/"))).resolve(strict=True) if normalized else root
    if not candidate.is_relative_to(root):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Asset path escapes the approved root.")
    return candidate, normalized


def resolve_directory_path(root_path: str, relative_path: str | None) -> tuple[Path, str]:
    directory_path, normalized = _resolve_source_path(root_path, relative_path)
    if not directory_path.is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found.")
    return directory_path, normalized


def resolve_asset_path(root_path: str, relative_path: str) -> Path:
    asset_path, _ = _resolve_source_path(root_path, relative_path)
    if not asset_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset file not found.")
    return asset_path


def resolve_writable_directory_path(root_path: str, relative_path: str | None) -> tuple[Path, str]:
    root = Path(validate_source_root(root_path)).resolve(strict=True)
    normalized = normalize_relative_path(relative_path)
    candidate = (root / Path(*normalized.split("/"))).resolve(strict=False) if normalized else root
    if not candidate.is_relative_to(root):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Asset path escapes the approved root.")
    if candidate.exists() and not candidate.is_dir():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload folder path is not a directory.")
    return candidate, normalized
