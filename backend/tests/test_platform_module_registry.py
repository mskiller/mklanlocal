from __future__ import annotations

from media_indexer_backend.api.router import CORE_ROUTERS
from media_indexer_backend.platform.registry import discover_manifest_map, iter_backend_router_refs


def test_timeline_is_registered_as_builtin_module():
    manifest = discover_manifest_map()["timeline"]

    assert manifest.kind == "builtin"
    assert manifest.enabled_by_default is False
    assert manifest.backend_router == "media_indexer_backend.api.routes.timeline:router"
    assert manifest.user_mount == "/timeline"
    assert manifest.nav_href == "/timeline"
    assert manifest.user_visible is True
    assert manifest.admin_visible is True


def test_timeline_router_is_loaded_from_module_registry():
    assert "media_indexer_backend.api.routes.timeline:router" in iter_backend_router_refs()


def test_timeline_router_is_not_part_of_core_router_list():
    assert all(router.prefix != "/timeline" for router in CORE_ROUTERS)


def test_characters_is_registered_as_builtin_module():
    manifest = discover_manifest_map()["characters"]

    assert manifest.kind == "builtin"
    assert manifest.backend_router == "media_indexer_backend.api.routes.characters:router"
    assert manifest.user_mount == "/characters"
    assert manifest.nav_href == "/characters"
    assert manifest.user_visible is True
    assert manifest.admin_visible is True


def test_geo_and_people_are_registered_but_disabled_by_default():
    manifest_map = discover_manifest_map()

    assert manifest_map["geo"].kind == "builtin"
    assert manifest_map["geo"].enabled_by_default is False
    assert manifest_map["people"].kind == "builtin"
    assert manifest_map["people"].enabled_by_default is False


def test_characters_router_is_loaded_from_module_registry():
    assert "media_indexer_backend.api.routes.characters:router" in iter_backend_router_refs()


def test_characters_router_is_not_part_of_core_router_list():
    assert all(router.prefix != "/characters" for router in CORE_ROUTERS)
