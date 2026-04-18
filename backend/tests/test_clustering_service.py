from __future__ import annotations

from types import SimpleNamespace

from media_indexer_backend.services.clustering_service import _build_cluster_label


def make_asset(filename: str, prompt_tags: list[str] | None = None, tags: list[str] | None = None):
    normalized = {"prompt_tags": prompt_tags or []}
    return SimpleNamespace(
        filename=filename,
        metadata_record=SimpleNamespace(normalized_json=normalized),
        tags=[SimpleNamespace(tag=tag) for tag in (tags or [])],
    )


def test_build_cluster_label_prefers_shared_prompt_terms():
    centroid = make_asset("cyberpunk-portrait.png", ["cyberpunk", "portrait", "1girl"], ["neon"])
    members = [
        centroid,
        make_asset("alt-1.png", ["cyberpunk", "portrait", "city_lights"]),
        make_asset("alt-2.png", ["cyberpunk", "portrait", "rain"]),
        make_asset("alt-3.png", ["cyberpunk", "portrait"], ["night"]),
        make_asset("alt-4.png", ["cyberpunk", "portrait", "solo"]),
    ]

    label = _build_cluster_label(members, centroid, fallback_index=1)

    assert label == "Cyberpunk Portrait"


def test_build_cluster_label_falls_back_to_centroid_filename():
    centroid = make_asset("midnight-train-scene.png", [], [])
    members = [
        centroid,
        make_asset("image-2.png", [], []),
        make_asset("image-3.png", [], []),
        make_asset("image-4.png", [], []),
        make_asset("image-5.png", [], []),
    ]

    label = _build_cluster_label(members, centroid, fallback_index=2)

    assert label == "Midnight Train Scene"
