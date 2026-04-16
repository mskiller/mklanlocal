"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { AssetCard } from "@/components/asset-card";
import { CollectionPickerModal } from "@/components/collection-picker-modal";
import { ZoomableImageViewer } from "@/components/zoomable-image-viewer";
import { useAuth } from "@/components/auth-provider";
import { useToast } from "@/components/use-toast";
import { DetailTabs } from "@/components/DetailTabs";
import { VisualWorkflowGraph } from "@/components/VisualWorkflowGraph";
import { addAssetsToCollection, assetImageUrl, bulkAnnotateAssets, downloadWorkflow, downloadWorkflowFromFile, fetchAsset, fetchCollections, fetchSimilar, fetchSimilarByImage, mediaUrl } from "@/lib/api";
import { metadataVersion, promptTagStringFromMetadata, promptTagsFromMetadata, stringMetadata } from "@/lib/asset-metadata";
import { sourceFolderBrowseHref } from "@/lib/browse-links";
import { copyTextToClipboard } from "@/lib/clipboard";
import { TagFilterChip } from "@/components/tag-filter-chip";
import { AssetDetail, CollectionSummary, ReviewStatus, SimilarAsset } from "@/lib/types";

export default function AssetDetailPage() {
  const params = useParams<{ id: string }>();
  const { user } = useAuth();
  const { push } = useToast();
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
  const [pendingTags, setPendingTags] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyExtracting, setBusyExtracting] = useState(false);

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

  const preview = mediaUrl(asset?.preview_url ?? asset?.content_url);
  const content = asset ? assetImageUrl(asset.id, { w: 3000, fmt: "webp" }) : undefined;
  const deepzoom = mediaUrl(asset?.deepzoom_url);
  const promptTags = asset ? promptTagsFromMetadata(asset.normalized_metadata, 12) : [];
  const promptTagString = asset ? promptTagStringFromMetadata(asset.normalized_metadata) : null;
  const assetTags = asset ? asset.tags.filter((tag) => !promptTags.includes(tag)) : [];
  const staleMetadata = asset ? metadataVersion(asset.normalized_metadata) < 6 : false;
  const positivePrompt = asset ? stringMetadata(asset.normalized_metadata["prompt"]) : null;
  const negativePrompt = asset ? stringMetadata(asset.normalized_metadata["negative_prompt"]) : null;
  const workflowText = asset ? stringMetadata(asset.normalized_metadata["workflow_text"]) : null;
  const browseHref = asset ? sourceFolderBrowseHref(asset.source_id, asset.relative_path) : "/sources";
  const summaryEntries = asset
    ? Object.entries(asset.normalized_metadata).filter(
        ([key]) => !["prompt", "negative_prompt", "workflow_text", "prompt_tags"].includes(key)
      )
    : [];

  const handleVisualExtract = async () => {
    if (!asset) return;
    setBusyExtracting(true);
    try {
      const response = await fetch(`/api/assets/${asset.id}/workflow/visual-extract`, { method: "POST" });
      if (!response.ok) throw new Error("Processing failed.");
      const nextAsset = await fetchAsset(asset.id);
      setAsset(nextAsset);
      push("Visual extraction complete!", "success");
    } catch {
      push("Failed to process visual workflow.", "error");
    } finally {
      setBusyExtracting(false);
    }
  };

  const tabs = [
    { id: "preview", label: "Preview", icon: "👁️" },
    { id: "metadata", label: "Metadata", icon: "📑" },
    { id: "workflow", label: "Visual Workflow", icon: "⚡" },
    { id: "similar", label: "Related", icon: "🔗" },
  ];

  if (asset?.normalized_metadata["gps_latitude"]) {
    tabs.push({ id: "location", label: "Location", icon: "📍" });
  }

  return (
    <AppShell
      title={asset?.filename ?? "Asset Detail"}
      description={asset ? `Source: ${asset.source_name}` : "Metadata, previews, tags, and similarity shortcuts."}
      actions={
        asset ? (
          <div className="page-actions">
            <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
              <span className="eyebrow">Generation Tools</span>
              <div className="page-actions" style={{ flexWrap: "wrap" }}>
                {promptTagString ? (
                  <button
                    type="button"
                    className="button subtle-button small-button"
                    onClick={async () => {
                      await copyTextToClipboard(promptTagString);
                      push("Copied Danbooru tags!", "success");
                    }}
                  >
                    Copy Danbooru Tags
                  </button>
                ) : null}
                {asset?.workflow_export_available ? (
                  <button
                    type="button"
                    className="button ghost-button small-button"
                    onClick={() => asset && downloadWorkflow(asset.id, asset.filename)}
                  >
                    Download Workflow JSON
                  </button>
                ) : null}
                <button
                  type="button"
                  className="button ghost-button small-button"
                  onClick={() => asset && downloadWorkflowFromFile(asset.id, asset.filename)}
                  title="Attempt to extract workflow directly from the current file, bypassing indexed metadata."
                >
                  🚀 Extract from File
                </button>
                <button
                  type="button"
                  className="button accent-button small-button"
                  disabled={busyExtracting}
                  onClick={handleVisualExtract}
                >
                  {busyExtracting ? "Processing..." : "✨ Visual OCR Extraction"}
                </button>
              </div>
            </div>

            {user?.capabilities.can_manage_collections && asset ? (
              <button type="button" className="button ghost-button small-button" onClick={() => setCollectionOpen(true)}>
                Add to Collection
              </button>
            ) : null}
          </div>
        ) : null
      }
    >
      <main className="asset-detail-container">
        {error && <div className="error-banner">{error}</div>}

        <DetailTabs tabs={tabs}>
          {(activeTab) => (
            <>
              {activeTab === "preview" && (
                <div className="preview-tab">
                  <article className="asset-main stack">
                    <div className="preview-container">
                      {deepzoom ? (
                        <ZoomableImageViewer
                          deepzoomUrl={deepzoom}
                          previewSrc={preview}
                          contentSrc={content}
                          alt={asset?.filename ?? "Asset preview"}
                        />
                      ) : (
                        <div className="static-preview-container">
                          <img src={preview ?? ""} alt={asset?.filename ?? "Preview"} className="asset-preview-image" />
                          <div className="preview-actions">
                            <a href={mediaUrl(asset?.content_url)} target="_blank" rel="noopener noreferrer" className="button ghost-button">
                              View Original High-Res
                            </a>
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="tag-section">
                      <div className="row-between">
                        <span className="eyebrow">Image Tags</span>
                        <Link href={browseHref} className="subdued small">
                          Open source folder
                        </Link>
                      </div>
                      <div className="tag-cloud">
                        {promptTags.map((tag) => (
                          <TagFilterChip key={`prompt-${tag}`} tag={tag} prompt={true} />
                        ))}
                        {assetTags.map((tag) => (
                          <TagFilterChip key={`tag-${tag}`} tag={tag} />
                        ))}
                        {pendingTags.map((tag) => (
                          <button key={`pending-${tag}`} type="button" className="tag-chip pending-tag" onClick={() => setPendingTags((current) => current.filter((t) => t !== tag))}>
                            {tag} (pending)
                          </button>
                        ))}
                      </div>
                    </div>
                  </article>
                </div>
              )}

              {activeTab === "metadata" && (
                <div className="metadata-tab stack">
                  {staleMetadata && (
                    <div className="info-banner" style={{ background: "rgba(255, 145, 0, 0.15)", borderColor: "var(--accent)", color: "var(--accent)" }}>
                      <p>
                        <strong>Update Required:</strong> This asset has legacy metadata.
                        <button className="button small-button" onClick={() => void downloadWorkflowFromFile(asset!.id, asset!.filename)}>Run Extraction</button>
                      </p>
                    </div>
                  )}

                  {positivePrompt && (
                    <article className="panel stack">
                      <p className="eyebrow">Positive Prompt</p>
                      <div className="prompt-content selectable">{positivePrompt}</div>
                      <button type="button" className="button subtle-button small-button" onClick={async () => { await copyTextToClipboard(positivePrompt); push("Copied prompt!", "success"); }}>
                        Copy Prompt
                      </button>
                    </article>
                  )}

                  {negativePrompt && (
                    <article className="panel stack">
                      <p className="eyebrow">Negative Prompt</p>
                      <div className="prompt-content subdued selectable">{negativePrompt}</div>
                      <button type="button" className="button subtle-button small-button" onClick={async () => { await copyTextToClipboard(negativePrompt); push("Copied negative prompt!", "success"); }}>
                        Copy Negative Prompt
                      </button>
                    </article>
                  )}

                  <article className="panel stack">
                    <div>
                      <p className="eyebrow">Technical Metadata</p>
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
                </div>
              )}

              {activeTab === "workflow" && (
                <div className="workflow-tab stack">
                  <div className="row-between">
                    <div>
                      <p className="eyebrow">Visual Analysis</p>
                      <h2>Extracted Workflow Graph</h2>
                    </div>
                    {asset?.visual_workflow_confidence && (
                      <div className="confidence-badge" style={{ color: (asset?.visual_workflow_confidence ?? 0) > 0.7 ? "var(--accent)" : "var(--subdued)" }}>
                        Confidence: {((asset?.visual_workflow_confidence ?? 0) * 100).toFixed(0)}%
                      </div>
                    )}
                  </div>
                  
                  <VisualWorkflowGraph workflow={asset?.visual_workflow_json ? (asset.visual_workflow_json as any) : null} />
                  
                  {workflowText && (
                    <article className="panel stack">
                      <p className="eyebrow">Embedded Workflow JSON (Metadata)</p>
                      <pre className="prompt-content subdued" style={{ maxHeight: "300px", overflow: "auto", fontSize: "0.8rem" }}>
                        {workflowText}
                      </pre>
                    </article>
                  )}
                </div>
              )}

              {activeTab === "similar" && (
                <div className="similar-tab stack">
                  <section className="stack">
                    <span className="eyebrow">Duplicates ({duplicates.length})</span>
                    <div className="similarity-scroll">
                      {duplicates.map((match) => (
                        <AssetCard key={match.asset.id} asset={match.asset} />
                      ))}
                    </div>
                  </section>

                  <section className="stack">
                    <span className="eyebrow">Visually Similar (Semantic)</span>
                    <div className="similarity-scroll">
                      {semantic.map((match) => (
                        <AssetCard key={match.asset.id} asset={match.asset} />
                      ))}
                    </div>
                  </section>

                  <section className="stack">
                    <span className="eyebrow">Similar Tags</span>
                    <div className="similarity-scroll">
                      {tagSimilar.map((match) => (
                        <AssetCard key={match.asset.id} asset={match.asset} />
                      ))}
                    </div>
                  </section>

                  {visualMatches.length > 0 && (
                    <section className="stack">
                      <span className="eyebrow">Live Visual Search Results</span>
                      <div className="similarity-scroll">
                        {visualMatches.map((match) => (
                          <AssetCard key={match.asset.id} asset={match.asset} />
                        ))}
                      </div>
                    </section>
                  )}
                </div>
              )}

              {activeTab === "location" && asset?.normalized_metadata["gps_latitude"] && (
                <div className="location-tab stack">
                  <article className="panel stack">
                    <div>
                      <p className="eyebrow">Location Metadata</p>
                      <h2>GPS Coordinates</h2>
                    </div>
                    <div className="gps-map-container" style={{ borderRadius: "16px", overflow: "hidden", border: "1px solid var(--border)" }}>
                      <iframe
                        width="100%"
                        height="480"
                        style={{ border: 0, filter: "invert(90%) hue-rotate(180deg)" }}
                        loading="lazy"
                        allowFullScreen
                        src={`https://www.google.com/maps/embed/v1/view?key=YOUR_API_KEY_HERE&center=${asset?.normalized_metadata["gps_latitude"]},${asset?.normalized_metadata["gps_longitude"]}&zoom=14&maptype=roadmap`}
                      ></iframe>
                      <div style={{ padding: "0.85rem", background: "rgba(7, 16, 20, 0.44)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span className="subdued">
                          {String(asset?.normalized_metadata["gps_latitude"])}, {String(asset?.normalized_metadata["gps_longitude"])}
                        </span>
                        <a href={`https://www.google.com/maps/search/?api=1&query=${asset?.normalized_metadata["gps_latitude"]},${asset?.normalized_metadata["gps_longitude"]}`} target="_blank" rel="noopener noreferrer" className="button small-button subtle-button">
                          View on Google Maps
                        </a>
                      </div>
                    </div>
                  </article>
                </div>
              )}
            </>
          )}
        </DetailTabs>

        {/* Sidebar / Sidebar equivalent for detail page */}
        <aside className="asset-sidebar stack">
          <section className="panel stack">
            <span className="eyebrow">Management</span>
            <div className="stack" style={{ gap: "0.8rem" }}>
              <div className="row-between">
                <strong>Rating</strong>
                <div className="rating-selector">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button key={star} type="button" className={`star-btn ${rating && rating >= star ? "star-active" : ""}`} onClick={() => setRating(star)}>
                      ★
                    </button>
                  ))}
                </div>
              </div>

              <div className="row-between">
                <strong>Status</strong>
                <select value={reviewStatus} onChange={(e) => setReviewStatus(e.target.value as ReviewStatus)} className="select-input small">
                  <option value="unreviewed">Unreviewed</option>
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                  <option value="favorite">Favorite</option>
                </select>
              </div>

              <div className="row-between">
                <strong>Flagged</strong>
                <input type="checkbox" checked={flagged} onChange={(e) => setFlagged(e.target.checked)} />
              </div>

              <div className="stack">
                <strong>Personal Note</strong>
                <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add a private note..." className="text-input" rows={3} />
              </div>

              <button
                type="button"
                className="button accent-button"
                disabled={annotationBusy}
                onClick={async () => {
                  if (!asset) return;
                  setAnnotationBusy(true);
                  try {
                    await bulkAnnotateAssets({
                      asset_ids: [asset.id],
                      rating,
                      review_status: reviewStatus,
                      flagged,
                      note,
                      tags: pendingTags,
                    });
                    setPendingTags([]);
                    const refreshed = await fetchAsset(asset.id);
                    setAsset(refreshed);
                    push("Saved changes!", "success");
                  } catch (nextError) {
                    setError(nextError instanceof Error ? nextError.message : "Unable to save annotation.");
                    push("Failed to save", "error");
                  } finally {
                    setAnnotationBusy(false);
                  }
                }}
              >
                {annotationBusy ? "Saving..." : "Save Changes"}
              </button>
            </div>
          </section>
        </aside>
      </main>

      {asset && (
        <CollectionPickerModal
          open={collectionOpen}
          collections={collections}
          busy={collectionBusy}
          onClose={() => setCollectionOpen(false)}
          onConfirm={async (collectionId) => {
            setCollectionBusy(true);
            try {
              await addAssetsToCollection(collectionId, [asset.id]);
              const collName = collections.find((c) => c.id === collectionId)?.name || "collection";
              push(`Added to ${collName}`, "success");
              setCollectionOpen(false);
            } catch {
              push("Failed to add to collection", "error");
            } finally {
              setCollectionBusy(false);
            }
          }}
        />
      )}
    </AppShell>
  );
}
