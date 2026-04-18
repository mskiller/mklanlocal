from __future__ import annotations

from collections import Counter
from pathlib import Path
import uuid

import numpy as np
from sklearn.cluster import KMeans
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from media_indexer_backend.models.tables import Asset, AssetSimilarity
from media_indexer_backend.schemas.clustering import ClusterProposal
from media_indexer_backend.services.metadata import prompt_tags_from_normalized

GENERIC_CLUSTER_LABEL_TERMS = {
    "1girl",
    "1boy",
    "2girls",
    "2boys",
    "solo",
    "best quality",
    "high quality",
    "highres",
    "absurdres",
    "safe",
    "sensitive",
    "questionable",
    "explicit",
    "looking at viewer",
    "simple background",
    "white background",
    "black background",
}


def _humanize_cluster_term(value: str) -> str:
    cleaned = " ".join(part for part in value.replace("_", " ").replace("-", " ").split() if part)
    return cleaned.title()


def _is_cluster_label_candidate(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower().replace("_", " ").replace("-", " ")
    if not normalized or ":" in normalized or normalized in GENERIC_CLUSTER_LABEL_TERMS:
        return False
    if sum(character.isalpha() for character in normalized) < 3:
        return False
    return True


def _asset_prompt_tags(asset: Asset) -> list[str]:
    normalized = asset.metadata_record.normalized_json if asset.metadata_record else {}
    return [tag for tag in prompt_tags_from_normalized(normalized) if _is_cluster_label_candidate(tag)]


def _asset_label_tags(asset: Asset) -> list[str]:
    prompt_tags = _asset_prompt_tags(asset)
    prompt_tag_set = set(prompt_tags)
    extra_tags = [
        tag.tag
        for tag in asset.tags
        if _is_cluster_label_candidate(tag.tag) and tag.tag not in prompt_tag_set
    ]
    return [*prompt_tags, *extra_tags]


def _top_cluster_terms(counter: Counter[str], minimum_support: int) -> list[str]:
    return [
        tag
        for tag, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        if count >= minimum_support
    ]


def _filename_cluster_label(filename: str) -> str | None:
    stem = Path(filename).stem
    if not _is_cluster_label_candidate(stem):
        return None
    return _humanize_cluster_term(stem)


def _build_cluster_label(member_assets: list[Asset], centroid_asset: Asset, fallback_index: int) -> str:
    minimum_support = max(2, int(np.ceil(len(member_assets) * 0.35)))
    prompt_counter: Counter[str] = Counter()
    tag_counter: Counter[str] = Counter()
    centroid_prompt_tags = _asset_prompt_tags(centroid_asset)
    centroid_all_tags = _asset_label_tags(centroid_asset)

    for asset in member_assets:
        prompt_counter.update(set(_asset_prompt_tags(asset)))
        tag_counter.update(set(_asset_label_tags(asset)))

    chosen_terms: list[str] = []
    for candidates in (
        [tag for tag in centroid_prompt_tags if prompt_counter[tag] >= minimum_support],
        _top_cluster_terms(prompt_counter, minimum_support),
        [tag for tag in centroid_all_tags if tag_counter[tag] >= minimum_support],
        _top_cluster_terms(tag_counter, minimum_support),
        centroid_all_tags,
    ):
        for candidate in candidates:
            if candidate not in chosen_terms:
                chosen_terms.append(candidate)
            if len(chosen_terms) >= 2:
                break
        if len(chosen_terms) >= 2:
            break

    if len(chosen_terms) >= 2:
        return " ".join(_humanize_cluster_term(term) for term in chosen_terms[:2])
    if chosen_terms:
        return f"{_humanize_cluster_term(chosen_terms[0])} Collection"

    filename_label = _filename_cluster_label(centroid_asset.filename)
    if filename_label:
        return filename_label
    return f"Cluster {fallback_index}"


def _deduplicate_suggested_labels(proposals: list[ClusterProposal]) -> None:
    seen: Counter[str] = Counter()
    for proposal in proposals:
        base_label = proposal.suggested_label
        seen[base_label] += 1
        if seen[base_label] > 1:
            proposal.suggested_label = f"{base_label} {seen[base_label]}"


def run_clustering(
    session: Session,
    k: int = 20,
    min_size: int = 5
) -> list[ClusterProposal]:
    # 1. Fetch all assets with embeddings
    query = (
        select(AssetSimilarity)
        .where(AssetSimilarity.embedding.is_not(None))
        .options(
            selectinload(AssetSimilarity.asset).selectinload(Asset.metadata_record),
            selectinload(AssetSimilarity.asset).selectinload(Asset.tags),
        )
    )
    similarities = session.execute(query).scalars().all()
    
    if not similarities:
        return []
    
    asset_ids = [s.asset_id for s in similarities]
    embeddings = np.array([s.embedding for s in similarities])
    
    # 2. Run k-means
    # If we have fewer samples than k, reduce k
    actual_k = min(k, len(embeddings))
    if actual_k < 1:
        return []
        
    kmeans = KMeans(n_clusters=actual_k, random_state=42, n_init="auto")
    labels = kmeans.fit_predict(embeddings)
    centroids = kmeans.cluster_centers_
    
    # 3. Organize clusters
    clusters: dict[int, list[uuid.UUID]] = {}
    for i, label in enumerate(labels):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(asset_ids[i])
        
    proposals = []
    for label, members in clusters.items():
        if len(members) < min_size:
            continue
            
        # Find asset closest to centroid as "centroid_id"
        cluster_indices = [i for i, l in enumerate(labels) if l == label]
        cluster_embeddings = embeddings[cluster_indices]
        centroid = centroids[label]
        
        # Calculate distances to centroid
        distances = np.linalg.norm(cluster_embeddings - centroid, axis=1)
        sort_idx = np.argsort(distances)
        
        centroid_asset_id = asset_ids[cluster_indices[sort_idx[0]]]
        cover_asset_ids = [asset_ids[cluster_indices[idx]] for idx in sort_idx[:4]]
        member_assets = [
            similarities[cluster_indices[idx]].asset
            for idx in sort_idx
            if similarities[cluster_indices[idx]].asset is not None
        ]
        centroid_asset = similarities[cluster_indices[sort_idx[0]]].asset

        proposals.append(ClusterProposal(
            centroid_id=centroid_asset_id,
            cover_asset_ids=cover_asset_ids,
            asset_ids=members,
            size=len(members),
            suggested_label=(
                _build_cluster_label(member_assets, centroid_asset, label + 1)
                if centroid_asset is not None and member_assets
                else f"Cluster {label + 1}"
            ),
        ))
        
    # Sort by size descending
    proposals.sort(key=lambda x: x.size, reverse=True)
    _deduplicate_suggested_labels(proposals)
    return proposals
