from __future__ import annotations

from pathlib import Path

from media_indexer_backend.platform.registry import discover_manifest_map, iter_runtime_import_paths


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
