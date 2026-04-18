from __future__ import annotations

from pathlib import Path
import shutil
import uuid

from media_indexer_backend.platform.registry import discover_manifest_map, find_repo_root, iter_runtime_import_paths


def test_first_wave_addons_are_discovered():
    manifest_map = discover_manifest_map()

    assert set(
        [
            "metadata_privacy",
            "export_recipes",
            "background_removal",
            "upscale_restore",
            "object_erase",
        ]
    ).issubset(manifest_map)
    assert manifest_map["export_recipes"].dependencies == ["collections"]
    assert manifest_map["background_removal"].user_mount == "/modules/background_removal"
    assert manifest_map["metadata_privacy"].admin_mount == "/admin/modules/metadata_privacy"
    assert manifest_map["metadata_privacy"].enabled_by_default is True
    assert manifest_map["export_recipes"].enabled_by_default is True
    assert manifest_map["background_removal"].enabled_by_default is True
    assert manifest_map["upscale_restore"].enabled_by_default is True
    assert manifest_map["object_erase"].enabled_by_default is True


def test_vendored_addon_runtime_paths_are_exposed():
    backend_paths = {Path(path).as_posix() for path in iter_runtime_import_paths("backend")}
    worker_paths = {Path(path).as_posix() for path in iter_runtime_import_paths("worker")}

    assert any(path.endswith("addons/background-removal/backend/src") for path in backend_paths)
    assert any(path.endswith("addons/upscale-restore/backend/src") for path in backend_paths)
    assert any(path.endswith("addons/object-erase/backend/src") for path in backend_paths)
    assert any(path.endswith("addons/metadata-privacy/backend/src") for path in backend_paths)
    assert any(path.endswith("addons/export-recipes/backend/src") for path in backend_paths)

    assert any(path.endswith("addons/background-removal/worker/src") for path in worker_paths)
    assert any(path.endswith("addons/export-recipes/worker/src") for path in worker_paths)


def test_find_repo_root_accepts_addon_layout_without_infra():
    scratch_root = Path(__file__).resolve().parent / ".tmp-platform-tests" / f"repo-{uuid.uuid4().hex}"
    repo_root = scratch_root / "repo"
    start_path = repo_root / "backend" / "src" / "media_indexer_backend" / "platform" / "registry.py"
    try:
        start_path.parent.mkdir(parents=True, exist_ok=True)
        start_path.write_text("# placeholder\n", encoding="utf-8")
        (repo_root / "backend").mkdir(exist_ok=True)
        (repo_root / "addons.toml").write_text("", encoding="utf-8")

        assert find_repo_root(start_path) == repo_root
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)
