"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { AssetCard } from "@/components/asset-card";
import { CollectionPickerModal } from "@/components/collection-picker-modal";
import { ZoomableImageViewer } from "@/components/zoomable-image-viewer";
import { useAuth } from "@/components/auth-provider";
import { addAssetsToCollection, assetImageUrl, bulkAnnotateAssets, fetchAsset, fetchCollections, fetchSimilar, fetchSimilarByImage, mediaUrl } from "@/lib/api";
import { metadataVersion, promptTagStringFromMetadata, promptTagsFromMetadata, stringMetadata } from "@/lib/asset-metadata";
import { sourceFolderBrowseHref } from "@/lib/browse-links";
import { copyTextToClipboard } from "@/lib/clipboard";
import { TagFilterChip } from "@/components/tag-filter-chip";
import { AssetDetail, CollectionSummary, ReviewStatus, SimilarAsset } from "@/lib/types";

export default function AssetDetailPage() {
  const params = useParams<{ id: string }>();
  const { user } = useAuth();
  const [asset, setAsset] = useState<AssetDetail | null>(null);
  const [duplicates, setDuplicates] = useState<SimilarAsset[]>([]);
  const [semantic, setSemantic] = useState<SimilarAsset[]>([]);
  const [tagSimilar, setTagSimilar] = useState<SimilarAsset[]>([]);
  const [visualMatches, setVisualMatches] = useState<SimilarAsset[]>([]);
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [collectionOpen, setCollectionOpen] = useState(false);
  const [collectionBusy, setCollectionBusy] = useState(false);
  const [annotationBusy, setAnnotationBusy] = useState(false);
  const [rating, setRating] = useState<number | null>(null);
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus>("unreviewed");
  const [flagged, setFlagged] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [nextAsset, nextDuplicates, nextSemantic, nextTagSimilar] = await Promise.all([
          fetchAsset(params.id),
          fetchSimilar(params.id, "duplicate", 6),
          fetchSimilar(params.id, "semantic", 6),
          fetchSimilar(params.id, "tag", 6),
        ]);
        setAsset(nextAsset);
        setRating(nextAsset.annotation?.rating ?? null);
        setReviewStatus(nextAsset.annotation?.review_status ?? "unreviewed");
        setFlagged(nextAsset.annotation?.flagged ?? false);
        setNote(nextAsset.annotation?.note ?? "");
        setDuplicates(nextDuplicates);
        setSemantic(nextSemantic);
        setTagSimilar(nextTagSimilar);
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "Unable to load asset detail.");
      }
    };
    void load();
  }, [params.id]);

  useEffect(() => {
    if (!user?.capabilities.can_manage_collections) {
      return;
    }
    const loadCollections = async () => {
      try {
        setCollections(await fetchCollections());
      } catch {
        setCollections([]);
      }
    };
    void loadCollections();
  }, [user?.capabilities.can_manage_collections]);

  const preview = mediaUrl(asset?.preview_url ?? asset?.content_url ?? null);
  const content = asset ? assetImageUrl(asset.id, { w: 3000, fmt: "webp" }) : null;
  const deepzoom = mediaUrl(asset?.deepzoom_url ?? null);
  const promptTags = asset ? promptTagsFromMetadata(asset.normalized_metadata, 12) : [];
  const promptTagString = asset ? promptTagStringFromMetadata(asset.normalized_metadata) : null;
  const assetTags = asset ? asset.tags.filter((tag) => !promptTags.includes(tag)) : [];
  const staleMetadata = asset ? metadataVersion(asset.normalized_metadata) < 6 : false;
  const positivePrompt = asset ? stringMetadata(asset.normalized_metadata.prompt) : null;
  const negativePrompt = asset ? stringMetadata(asset.normalized_metadata.negative_prompt) : null;
  const workflowText = asset ? stringMetadata(asset.normalized_metadata.workflow_text) : null;
  const browseHref = asset ? sourceFolderBrowseHref(asset.source_id, asset.relative_path) : "/sources";
  const summaryEntries = asset
    ? Object.entries(asset.normalized_metadata).filter(
        ([key]) => !["prompt", "negative_prompt", "workflow_text", "prompt_tags"].includes(key)
      )
    : [];

  return (
    <AppShell
      title={asset?.filename ?? "Asset Detail"}
      description={asset ? `Source: ${asset.source_name}` : "Metadata, previews, tags, and similarity shortcuts."}
      actions={
        asset ? (
          <div className="page-actions">
            {asset.workflow_export_available && asset.workflow_export_url ? (
              <a href={mediaUrl(asset.workflow_export_url) ?? asset.workflow_export_url} className="button ghost-button small-button">
                Download Workflow JSON
              </a>
            ) : null}
            {promptTagString ? (
              <button
                type="button"
                className="button subtle-button small-button"
                onClick={async () => {
                  await copyTextToClipboard(promptTagString);
                }}
              >
                Copy Danbooru Tags
              </button>
            ) : null}
            {user?.capabilities.can_manage_collections && asset ? (
              <button type="button" className="button ghost-button small-button" onClick={() => setCollectionOpen(true)}>
                Add to Collection
              </button>
            ) : null}
            {asset?.media_type === "image" ? (
              <button
                type="button"
                className="button ghost-button small-button"
                onClick={async () => {
                  if (!asset) {
                    return;
                  }
                  try {
                    setVisualMatches(await fetchSimilarByImage(asset.id, 6));
                  } catch (nextError) {
                    setError(nextError instanceof Error ? nextError.message : "Unable to find visually similar assets.");
                  }
                }}
              >
                Find Visually Similar
              </button>
            ) : null}
            <Link href={`/assets/${asset.id}/similar`} className="button">
              View Similar
            </Link>
            <Link href={browseHref} className="button ghost-button small-button">
              Open Browse
            </Link>
          </div>
        ) : null
      }
    >
      <CollectionPickerModal
        open={collectionOpen}
        collections={collections}
        busy={collectionBusy}
        onClose={() => setCollectionOpen(false)}
        onConfirm={async (collectionId) => {
          if (!asset) {
            return;
          }
          setCollectionBusy(true);
          try {
            await addAssetsToCollection(collectionId, [asset.id]);
            setCollectionOpen(false);
          } catch (nextError) {
            setError(nextError instanceof Error ? nextError.message : "Unable to add asset to collection.");
          } finally {
            setCollectionBusy(false);
          }
        }}
      />
      {error ? <section className="panel empty-state">{error}</section> : null}
      {asset ? (
        <>
          {staleMetadata ? (
            <section className="panel stack">
              <div className="row-between">
                <div>
                  <p className="eyebrow">Metadata Refresh</p>
                  <h2>Prompt extraction can be refreshed</h2>
                  <p className="subdued">This asset was indexed with an older metadata schema. Start a new source scan to refresh prompt parsing and prompt tags.</p>
                </div>
                <Link href={browseHref} className="button small-button">
                  Refresh via Rescan
                </Link>
              </div>
            </section>
          ) : null}
          <section className="asset-detail-layout">
            <article className="panel stack">
              <div className="asset-detail-preview">
                {asset.media_type === "image" && preview ? (
                  <ZoomableImageViewer
                    previewSrc={preview}
                    contentSrc={content}
                    deepzoomUrl={deepzoom}
                    alt={asset.filename}
                    defaultMode="auto"
                  />
                ) : preview ? (
                  <video src={preview} controls />
                ) : (
                  <div className="asset-placeholder">No preview</div>
                )}
              </div>
              <div className="chip-row">
                {promptTags.map((tag) => (
                  <TagFilterChip key={tag} tag={tag} prompt className="chip chip-prompt buttonless" />
                ))}
                {assetTags.map((tag) => (
                  <TagFilterChip key={tag} tag={tag} className="chip buttonless" />
                ))}
              </div>
            </article>

            <article className="panel stack">
              <div className="stack">
                <p className="eyebrow">Curation</p>
                <h2>Review and rating</h2>
                <div className="chip-row">
                  {[1, 2, 3, 4, 5].map((value) => (
                    <button
                      key={value}
                      type="button"
                      className={`button small-button ${rating === value ? "" : "ghost-button"}`}
                      onClick={() => setRating(rating === value ? null : value)}
                    >
                      {"★".repeat(value)}
                    </button>
                  ))}
                  <button type="button" className="button ghost-button small-button" onClick={() => setRating(null)}>
                    Clear Rating
                  </button>
                </div>
                <label className="field">
                  <span>Review Status</span>
                  <select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value as ReviewStatus)}>
                    <option value="unreviewed">Unreviewed</option>
                    <option value="approved">Approved</option>
                    <option value="rejected">Rejected</option>
                    <option value="favorite">Favorite</option>
                  </select>
                </label>
                <label className="field checkbox-field">
                  <span>Flagged for attention</span>
                  <input type="checkbox" checked={flagged} onChange={(event) => setFlagged(event.target.checked)} />
                </label>
                <label className="field">
                  <span>Curator Note</span>
                  <textarea rows={4} value={note} onChange={(event) => setNote(event.target.value)} />
                </label>
                <div className="card-actions">
                  <button
                    type="button"
                    className="button"
                    disabled={annotationBusy}
                    onClick={async () => {
                      if (!asset) {
                        return;
                      }
                      setAnnotationBusy(true);
                      setError(null);
                      try {
                        await bulkAnnotateAssets({
                          asset_ids: [asset.id],
                          rating,
                          review_status: reviewStatus,
                          flagged,
                          note,
                        });
                        const refreshed = await fetchAsset(asset.id);
                        setAsset(refreshed);
                      } catch (nextError) {
                        setError(nextError instanceof Error ? nextError.message : "Unable to save annotation.");
                      } finally {
                        setAnnotationBusy(false);
                      }
                    }}
                  >
                    {annotationBusy ? "Saving..." : "Save Review"}
                  </button>
                </div>
              </div>
            </article>

            <article className="panel stack">
              <div>
                <p className="eyebrow">Prompt Extraction</p>
                <h2>Generated image prompts</h2>
              </div>
              <div className="prompt-sections">
                <div className="prompt-panel">
                  <strong>Positive Prompt</strong>
                  <pre className="prompt-block">{positivePrompt ?? "No positive prompt extracted."}</pre>
                </div>
                {negativePrompt ? (
                  <div className="prompt-panel">
                    <strong>Negative Prompt</strong>
                    <pre className="prompt-block">{negativePrompt}</pre>
                  </div>
                ) : null}
                {workflowText ? (
                  <div className="prompt-panel">
                    <strong>Workflow Summary</strong>
                    <pre className="prompt-block">{workflowText}</pre>
                  </div>
                ) : null}
              </div>
            </article>

            <article className="panel stack">
              <div>
                <p className="eyebrow">Normalized Metadata</p>
                <h2>Summary</h2>
              </div>
              <div className="metadata-grid">
                {summaryEntries.map(([key, value]) => (
                  <div key={key} className="metadata-row">
                    <strong>{key}</strong>
                    <div className="subdued">{String(value ?? "n/a")}</div>
                  </div>
                ))}
              </div>
            </article>
          </section>

          <section className="panel stack">
            <div>
              <p className="eyebrow">Raw Metadata</p>
              <h2>Extractor output</h2>
            </div>
            <pre className="json-block">{JSON.stringify(asset.raw_metadata, null, 2)}</pre>
          </section>

          <section className="panel stack">
            <div className="row-between">
              <div>
                <p className="eyebrow">Quick Similarity</p>
                <h2>Duplicate, semantic, and tag neighbors</h2>
              </div>
              <Link href={`/assets/${asset.id}/similar`} className="button subtle-button">
                Open Full Similarity View
              </Link>
            </div>
            <div className="results-grid">
              {duplicates.concat(semantic, tagSimilar).slice(0, 6).map((match) => (
                <AssetCard
                  key={`${match.match_type}-${match.asset.id}`}
                  asset={match.asset}
                  contextBadges={
                    match.shared_prompt_tags.length
                      ? [`${match.prompt_tag_overlap} shared prompt tag${match.prompt_tag_overlap === 1 ? "" : "s"}`]
                      : [match.match_type === "duplicate" ? "Near duplicate" : match.match_type === "tag" ? "Tag match" : "Semantic match"]
                  }
                />
              ))}
            </div>
          </section>

          {visualMatches.length ? (
            <section className="panel stack">
              <div>
                <p className="eyebrow">Search By Image</p>
                <h2>Visually similar results</h2>
              </div>
              <div className="results-grid">
                {visualMatches.map((match) => (
                  <AssetCard key={`visual-${match.asset.id}`} asset={match.asset} contextBadges={["Visual match"]} />
                ))}
              </div>
            </section>
          ) : null}
        </>
      ) : (
        <section className="panel empty-state">Loading asset detail…</section>
      )}
    </AppShell>
  );
}
