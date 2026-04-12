"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { BulkActionBar } from "@/components/bulk-action-bar";
import { CompareSelectionTray } from "@/components/compare-selection-tray";
import { CollectionPickerModal } from "@/components/collection-picker-modal";
import { GalleryTile } from "@/components/gallery-tile";
import { ImageExplorerOverlay } from "@/components/image-explorer-overlay";
import { JustifiedGallery } from "@/components/justified-gallery";
import { useAuth } from "@/components/auth-provider";
import {
  addAssetsToCollection,
  fetchAssetBrowse,
  fetchCollections,
  fetchSources,
  mediaUrl,
} from "@/lib/api";
import { formatBytes, formatDate } from "@/lib/asset-metadata";
import { sourceFolderBrowseHref } from "@/lib/browse-links";
import { copyTextToClipboard } from "@/lib/clipboard";
import { AssetBrowseItem, CollectionSummary, Source } from "@/lib/types";

type BrowseSortMode = "modified_at" | "created_at" | "filename";
type BrowseDisplayMode = "gallery" | "explorer";

export default function BrowseIndexedPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [sources, setSources] = useState<Source[]>([]);
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [items, setItems] = useState<AssetBrowseItem[]>([]);
  const [total, setTotal] = useState(0);
  const [sourceId, setSourceId] = useState("");
  const [sortMode, setSortMode] = useState<BrowseSortMode>("modified_at");
  const [displayMode, setDisplayMode] = useState<BrowseDisplayMode>("gallery");
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedAssets, setSelectedAssets] = useState<Array<{ id: string; name: string }>>([]);
  const [bulkMode, setBulkMode] = useState(false);
  const [bulkSelectedIds, setBulkSelectedIds] = useState<string[]>([]);
  const [explorerIndex, setExplorerIndex] = useState<number | null>(null);
  const [collectionModalOpen, setCollectionModalOpen] = useState(false);
  const [collectionBusy, setCollectionBusy] = useState(false);
  const [pendingCollectionAssetIds, setPendingCollectionAssetIds] = useState<string[]>([]);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const loadStatic = async () => {
      try {
        const [nextSources, nextCollections] = await Promise.all([
          fetchSources(),
          user?.capabilities.can_manage_collections ? fetchCollections() : Promise.resolve([]),
        ]);
        setSources(nextSources);
        setCollections(nextCollections);
      } catch {
        setSources([]);
        setCollections([]);
      }
    };
    void loadStatic();
  }, [user?.capabilities.can_manage_collections]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      setPage(1);
      setSelectedAssets([]);
      try {
        const response = await fetchAssetBrowse({ source_id: sourceId || undefined, sort: sortMode, page: 1, page_size: 36 });
        setItems(response.items);
        setTotal(response.total);
        setHasMore(response.page * response.page_size < response.total);
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "Unable to load indexed browse.");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [sourceId, sortMode]);

  useEffect(() => {
    if (page === 1) {
      return;
    }
    const loadMore = async () => {
      setLoadingMore(true);
      try {
        const response = await fetchAssetBrowse({ source_id: sourceId || undefined, sort: sortMode, page, page_size: 36 });
        setItems((current) => [...current, ...response.items]);
        setTotal(response.total);
        setHasMore(response.page * response.page_size < response.total);
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "Unable to load more indexed images.");
      } finally {
        setLoadingMore(false);
      }
    };
    void loadMore();
  }, [page, sourceId, sortMode]);

  useEffect(() => {
    const target = sentinelRef.current;
    if (!target || !hasMore || loading || loadingMore) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setPage((current) => current + 1);
        }
      },
      { rootMargin: "900px 0px" }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [hasMore, loading, loadingMore, items.length]);

  const toggleSelection = (assetId: string, name: string) => {
    setSelectedAssets((current) => {
      const exists = current.some((item) => item.id === assetId);
      if (exists) {
        return current.filter((item) => item.id !== assetId);
      }
      const next = { id: assetId, name };
      if (current.length === 2) {
        return [current[1], next];
      }
      return [...current, next];
    });
  };

  const compareHref = selectedAssets.length === 2 ? `/compare?a=${selectedAssets[0].id}&b=${selectedAssets[1].id}` : null;
  const explorerItems = useMemo(
    () =>
      items.map((item) => ({
        key: item.id,
        title: item.filename,
        subtitle: [item.source_name, item.generator].filter(Boolean).join(" · ") || undefined,
        promptExcerpt: item.prompt_excerpt,
        promptTags: item.prompt_tags,
        previewSrc: mediaUrl(item.preview_url),
        contentSrc: mediaUrl(item.content_url),
        deepzoomUrl: mediaUrl(item.deepzoom_url),
        detailHref: `/assets/${item.id}`,
        similarHref: `/assets/${item.id}/similar`,
        sourceContext: item.relative_path,
        metadataSummary: [
          ...(item.width && item.height ? [{ label: "Dimensions", value: `${item.width} x ${item.height}` }] : []),
          { label: "Modified", value: formatDate(item.modified_at) },
          { label: "Size", value: formatBytes(item.size_bytes) },
        ],
      })),
    [items]
  );

  useEffect(() => {
    if (displayMode === "explorer" && items.length && explorerIndex === null) {
      setExplorerIndex(0);
    }
    if (displayMode === "gallery" && explorerIndex !== null) {
      setExplorerIndex(null);
    }
  }, [displayMode, explorerIndex, items.length]);

  useEffect(() => {
    if (explorerIndex === null) {
      return;
    }
    if (!explorerItems.length) {
      setExplorerIndex(null);
      return;
    }
    if (explorerIndex >= explorerItems.length) {
      setExplorerIndex(explorerItems.length - 1);
    }
  }, [explorerIndex, explorerItems.length]);

  return (
    <AppShell
      title="Browse Indexed"
      description="Gallery-first exploration of already indexed images. Search stays separate for dense filters and metadata work."
      actions={
        <div className="page-actions">
          <Link href="/sources" className="button subtle-button small-button">
            Open Sources
          </Link>
          <Link href="/search" className="button ghost-button small-button">
            Open Search
          </Link>
        </div>
      }
    >
      <CollectionPickerModal
        open={collectionModalOpen}
        collections={collections}
        busy={collectionBusy}
        onClose={() => setCollectionModalOpen(false)}
        onConfirm={async (collectionId) => {
          setCollectionBusy(true);
          setError(null);
          try {
            await addAssetsToCollection(collectionId, pendingCollectionAssetIds);
            setCollectionModalOpen(false);
          } catch (nextError) {
            setError(nextError instanceof Error ? nextError.message : "Unable to add assets to collection.");
          } finally {
            setCollectionBusy(false);
          }
        }}
      />
      <ImageExplorerOverlay
        open={explorerIndex !== null}
        items={explorerItems}
        activeIndex={explorerIndex ?? 0}
        onClose={() => {
          setExplorerIndex(null);
          if (displayMode === "explorer") {
            setDisplayMode("gallery");
          }
        }}
        onActiveIndexChange={(next) => setExplorerIndex(next)}
        renderActions={(item) => {
          const sourceItem = items.find((entry) => entry.id === item.key);
          if (!sourceItem) {
            return null;
          }
          const selected = selectedAssets.some((entry) => entry.id === sourceItem.id);
          const compareTarget = selectedAssets.find((entry) => entry.id !== sourceItem.id);
          return (
            <>
              <div className="card-actions">
                <button type="button" className="button small-button" onClick={() => toggleSelection(sourceItem.id, sourceItem.filename)}>
                  {selected ? "Deselect for Compare" : "Stage for Compare"}
                </button>
                {compareTarget ? (
                  <button
                    type="button"
                    className="button ghost-button small-button"
                    onClick={() => router.push(`/compare?a=${compareTarget.id}&b=${sourceItem.id}`)}
                  >
                    Compare with Selected
                  </button>
                ) : null}
              </div>
              <div className="card-actions">
                {user?.capabilities.can_manage_collections ? (
                  <button
                    type="button"
                    className="button subtle-button small-button"
                    onClick={() => {
                      setPendingCollectionAssetIds([sourceItem.id]);
                      setCollectionModalOpen(true);
                    }}
                  >
                    Add to Collection
                  </button>
                ) : null}
                <button
                  type="button"
                  className="button ghost-button small-button"
                  disabled={!sourceItem.prompt_tag_string}
                  onClick={async () => {
                    if (sourceItem.prompt_tag_string) {
                      await copyTextToClipboard(sourceItem.prompt_tag_string);
                    }
                  }}
                >
                  Copy Danbooru Tags
                </button>
              </div>
              <div className="card-actions">
                <button
                  type="button"
                  className="button ghost-button small-button"
                  onClick={() => window.open(mediaUrl(sourceItem.content_url) ?? sourceItem.content_url, "_blank", "noopener,noreferrer")}
                >
                  Open Original File
                </button>
                <Link href={sourceFolderBrowseHref(sourceItem.source_id, sourceItem.relative_path)} className="button ghost-button small-button">
                  Open Live Folder
                </Link>
              </div>
            </>
          );
        }}
      />
      <CompareSelectionTray
        selectionMode={selectionMode}
        selectedCount={selectedAssets.length}
        compareHref={compareHref}
        onToggleSelectionMode={() => setSelectionMode((value) => !value)}
        onClearSelection={() => setSelectedAssets([])}
        hint="This page is for visual browsing only. Hover or long-press for prompt tags, quick actions, and collection shortcuts."
        canAddToCollection={Boolean(user?.capabilities.can_manage_collections)}
        onAddToCollection={
          user?.capabilities.can_manage_collections
            ? () => {
                setPendingCollectionAssetIds(selectedAssets.map((item) => item.id));
                setCollectionModalOpen(true);
              }
            : undefined
        }
      />
      {bulkMode && bulkSelectedIds.length > 0 && (
        <BulkActionBar
          selectedIds={bulkSelectedIds}
          onClear={() => setBulkSelectedIds([])}
          onDone={() => { setBulkSelectedIds([]); setBulkMode(false); }}
        />
      )}
      {!selectionMode && (
        <div style={{ padding: "0.5rem 1rem" }}>
          <button
            type="button"
            className={`button small-button ${bulkMode ? "" : "ghost-button"}`}
            onClick={() => { setBulkMode((v) => !v); setBulkSelectedIds([]); }}
          >
            {bulkMode ? `Bulk Mode (${bulkSelectedIds.length} selected)` : "Bulk Curate"}
          </button>
        </div>
      )}
      <section className="gallery-layout">
        <aside className="panel stack gallery-sidebar">
          <div>
            <p className="eyebrow">Indexed Controls</p>
            <h2>Gallery filters</h2>
          </div>
          <label className="field">
            <span>Source</span>
            <select value={sourceId} onChange={(event) => setSourceId(event.target.value)}>
              <option value="">All sources</option>
              {sources.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.name}
                </option>
              ))}
            </select>
          </label>
          <div className="browse-toolbar-group">
            <span className="subdued">Mode</span>
            <div className="chip-row">
              <button className={`button small-button ${displayMode === "gallery" ? "" : "ghost-button"}`} type="button" onClick={() => setDisplayMode("gallery")}>
                Gallery
              </button>
              <button
                className={`button small-button ${displayMode === "explorer" ? "" : "ghost-button"}`}
                type="button"
                onClick={() => setDisplayMode("explorer")}
                disabled={!items.length}
              >
                Explorer
              </button>
            </div>
          </div>
          <div className="browse-toolbar-group">
            <span className="subdued">Sort</span>
            <div className="chip-row">
              <button className={`button small-button ${sortMode === "modified_at" ? "" : "ghost-button"}`} type="button" onClick={() => setSortMode("modified_at")}>
                Modified
              </button>
              <button className={`button small-button ${sortMode === "created_at" ? "" : "ghost-button"}`} type="button" onClick={() => setSortMode("created_at")}>
                Created
              </button>
              <button className={`button small-button ${sortMode === "filename" ? "" : "ghost-button"}`} type="button" onClick={() => setSortMode("filename")}>
                Name
              </button>
            </div>
          </div>
          <div className="chip-row">
            <span className="chip">{total} indexed images</span>
            {sourceId ? <span className="chip">Filtered source</span> : null}
          </div>
        </aside>
        <section className="stack">
          {error ? <section className="panel empty-state">{error}</section> : null}
          {loading ? <section className="panel empty-state">Loading indexed gallery…</section> : null}
          <JustifiedGallery
            className="gallery-surface"
            items={items.map((item, index) => {
              const selected = selectedAssets.some((entry) => entry.id === item.id);
              const compareTarget = selectedAssets.find((entry) => entry.id !== item.id);
              return {
                key: item.id,
                ratio: item.width && item.height ? item.width / item.height : 1,
                content: (
                  <GalleryTile
                    key={item.id}
                    className="gallery-tile-justified"
                    tileStyle={{ height: "100%" }}
                    imageButtonStyle={{ height: "100%", aspectRatio: "auto" }}
                    imageSrc={mediaUrl(item.preview_url)}
                    alt={item.filename}
                    title={item.filename}
                    subtitle={[item.source_name, item.generator].filter(Boolean).join(" · ") || undefined}
                    promptExcerpt={item.prompt_excerpt}
                    promptTags={item.prompt_tags}
                    selected={selected}
                    selectionMode={selectionMode}
                    onOpen={() => setExplorerIndex(index)}
                    onToggleSelect={() => toggleSelection(item.id, item.filename)}
                    menuActions={[
                      { label: "Open Explorer", onSelect: () => setExplorerIndex(index) },
                      { label: "Open Detail", onSelect: () => router.push(`/assets/${item.id}`), variant: "subtle" },
                      { label: "Open Similar", onSelect: () => router.push(`/assets/${item.id}/similar`), variant: "subtle" },
                      { label: selected ? "Deselect for Compare" : "Select for Compare", onSelect: () => toggleSelection(item.id, item.filename), variant: "ghost" },
                      ...(bulkMode
                        ? [{ label: bulkSelectedIds.includes(item.id) ? "Remove from Bulk" : "Add to Bulk", onSelect: () => setBulkSelectedIds((ids) => ids.includes(item.id) ? ids.filter((x) => x !== item.id) : [...ids, item.id]), variant: "ghost" as const }]
                        : []),
                      ...(compareTarget
                        ? [{ label: "Compare with Selected", onSelect: () => router.push(`/compare?a=${compareTarget.id}&b=${item.id}`), variant: "subtle" as const }]
                        : []),
                      ...(user?.capabilities.can_manage_collections
                        ? [{ label: "Add to Collection", onSelect: () => { setPendingCollectionAssetIds([item.id]); setCollectionModalOpen(true); }, variant: "subtle" as const }]
                        : []),
                      {
                        label: "Copy Danbooru Tags",
                        onSelect: async () => {
                          if (item.prompt_tag_string) {
                            await copyTextToClipboard(item.prompt_tag_string);
                          }
                        },
                        variant: "ghost",
                        disabled: !item.prompt_tag_string,
                      },
                      {
                        label: "Open Live Folder",
                        onSelect: () => router.push(sourceFolderBrowseHref(item.source_id, item.relative_path)),
                        variant: "ghost",
                      },
                      {
                        label: "Open Original File",
                        onSelect: () => window.open(mediaUrl(item.content_url) ?? item.content_url, "_blank", "noopener,noreferrer"),
                        variant: "ghost",
                      },
                    ]}
                  />
                ),
              };
            })}
          />
          {!loading ? (
            <section className="panel stack">
              <div className="row-between">
                <p className="subdued">Showing {items.length} of {total} indexed images</p>
                {loadingMore ? <p className="subdued">Loading more…</p> : null}
              </div>
              <div ref={sentinelRef} className="infinite-sentinel" />
            </section>
          ) : null}
        </section>
      </section>
    </AppShell>
  );
}
