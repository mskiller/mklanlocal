"use client";

import Link from "next/link";
import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { AssetCard } from "@/components/asset-card";
import { BulkActionBar } from "@/components/bulk-action-bar";
import { CompareSelectionTray } from "@/components/compare-selection-tray";
import { CollectionPickerModal } from "@/components/collection-picker-modal";
import { FilterSidebar } from "@/components/filter-sidebar";
import { addAssetsToCollection, addSearchResultsToCollection, fetchCollections, fetchSearch, fetchTags } from "@/lib/api";
import { buildSearchQuery, DEFAULT_SEARCH_FILTERS, parseSearchFilterState, parseTagList, removeTagFilter } from "@/lib/search-filters";
import { useAuth } from "@/components/auth-provider";
import { AssetListResponse, AssetSummary, CollectionSummary, ReviewStatus, SearchFilterFormState, TagCount } from "@/lib/types";

function SearchPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const searchParamKey = searchParams.toString();
  const [filters, setFilters] = useState<SearchFilterFormState>(DEFAULT_SEARCH_FILTERS);
  const [results, setResults] = useState<AssetListResponse | null>(null);
  const [tagSuggestions, setTagSuggestions] = useState<TagCount[]>([]);
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [selected, setSelected] = useState<AssetSummary[]>([]);
  const [selectionMode, setSelectionMode] = useState(false);
  const [bulkMode, setBulkMode] = useState(false);
  const [bulkSelectedIds, setBulkSelectedIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [page, setPage] = useState(1);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [collectionOpen, setCollectionOpen] = useState(false);
  const [collectionBusy, setCollectionBusy] = useState(false);
  const [collectionMode, setCollectionMode] = useState<"selected" | "search-results">("selected");
  const [pendingCollectionAssetIds, setPendingCollectionAssetIds] = useState<string[]>([]);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const load = async (nextFilters: SearchFilterFormState, nextPage: number, append = false) => {
    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
      setError(null);
    }
    try {
      const apiFilters = {
        ...nextFilters,
        page: nextPage,
        min_rating: nextFilters.min_rating ? Number(nextFilters.min_rating) : undefined,
        review_status: (nextFilters.review_status as ReviewStatus) || undefined,
      };
      const nextResults = await fetchSearch(apiFilters);
      setResults((current) =>
        append && current
          ? {
              ...nextResults,
              items: [...current.items, ...nextResults.items],
            }
          : nextResults
      );
      setHasMore(nextPage * nextResults.page_size < nextResults.total);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load search.");
    } finally {
      if (append) {
        setLoadingMore(false);
      } else {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    const loadTags = async () => {
      try {
        setTagSuggestions(await fetchTags());
      } catch {
        setTagSuggestions([]);
      }
    };
    void loadTags();
  }, []);

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

  useEffect(() => {
    const nextFilters = parseSearchFilterState(searchParams);
    setFilters(nextFilters);
    setPage(1);
    setSelected([]);
    void load(nextFilters, 1, false);
  }, [searchParamKey]);

  useEffect(() => {
    if (page === 1) {
      return;
    }
    void load(filters, page, true);
  }, [page]);

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
      { rootMargin: "800px 0px" }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [hasMore, loading, loadingMore, results?.items.length]);

  const toggleSelection = (asset: AssetSummary) => {
    setSelected((current) => {
      const exists = current.some((item) => item.id === asset.id);
      if (exists) {
        return current.filter((item) => item.id !== asset.id);
      }
      return [...current, asset];
    });
  };

  const selectAllLoaded = () => {
    const loadedItems = results?.items ?? [];
    if (!loadedItems.length) {
      return;
    }
    setSelectionMode(true);
    setSelected(loadedItems);
  };

  const pushFilters = (nextFilters: SearchFilterFormState) => {
    const query = buildSearchQuery(nextFilters);
    router.push(`/search${query ? `?${query}` : ""}`);
  };

  const applyFilters = () => {
    setFiltersOpen(false);
    pushFilters(filters);
  };

  const resetFilters = () => {
    setFiltersOpen(false);
    pushFilters({ ...DEFAULT_SEARCH_FILTERS });
  };

  const activeTags = parseTagList(filters.tags);
  const activeFilters = [
    filters.q ? `Query: ${filters.q}` : null,
    filters.media_type ? `Type: ${filters.media_type}` : null,
    filters.camera_make ? `Make: ${filters.camera_make}` : null,
    filters.camera_model ? `Model: ${filters.camera_model}` : null,
    filters.year ? `Year: ${filters.year}` : null,
    filters.width_min || filters.width_max ? `Width: ${filters.width_min || "0"}-${filters.width_max || "any"}` : null,
    filters.height_min || filters.height_max ? `Height: ${filters.height_min || "0"}-${filters.height_max || "any"}` : null,
    filters.duration_min || filters.duration_max ? `Duration: ${filters.duration_min || "0"}-${filters.duration_max || "any"}` : null,
    filters.sort !== DEFAULT_SEARCH_FILTERS.sort ? `Sort: ${filters.sort}` : null,
  ].filter((value): value is string => Boolean(value));
  const compareHref = selected.length === 2 ? `/compare?a=${selected[0].id}&b=${selected[1].id}` : null;

  return (
    <AppShell
      title="Search"
      description="Indexed discovery with metadata filters, prompt tags, and exact tag search. Browse stays separate for live folder exploration."
      actions={
        compareHref || (user?.capabilities.can_manage_collections && results?.total) ? (
          <div className="page-actions">
            <Link href="/browse-indexed" className="button subtle-button small-button">
              Browse Indexed
            </Link>
            {user?.capabilities.can_manage_collections && results?.total ? (
              <button
                className="button ghost-button small-button"
                type="button"
                onClick={() => {
                  setCollectionMode("search-results");
                  setCollectionOpen(true);
                }}
              >
                Add Search Results
              </button>
            ) : null}
            {compareHref ? (
              <button className="button" type="button" onClick={() => router.push(compareHref)}>
                Compare Selected
              </button>
            ) : null}
          </div>
        ) : undefined
      }
    >
      <CollectionPickerModal
        open={collectionOpen}
        collections={collections}
        busy={collectionBusy}
        onClose={() => setCollectionOpen(false)}
        onConfirm={async (collectionId) => {
          setCollectionBusy(true);
          setError(null);
          try {
            if (collectionMode === "selected") {
              await addAssetsToCollection(
                collectionId,
                pendingCollectionAssetIds.length ? pendingCollectionAssetIds : selected.map((asset) => asset.id)
              );
            } else {
              await addSearchResultsToCollection(collectionId, {
                q: filters.q || undefined,
                media_type: filters.media_type || undefined,
                camera_make: filters.camera_make || undefined,
                camera_model: filters.camera_model || undefined,
                year: filters.year ? Number(filters.year) : undefined,
                width_min: filters.width_min ? Number(filters.width_min) : undefined,
                width_max: filters.width_max ? Number(filters.width_max) : undefined,
                height_min: filters.height_min ? Number(filters.height_min) : undefined,
                height_max: filters.height_max ? Number(filters.height_max) : undefined,
                duration_min: filters.duration_min ? Number(filters.duration_min) : undefined,
                duration_max: filters.duration_max ? Number(filters.duration_max) : undefined,
                tags: parseTagList(filters.tags),
              });
            }
            setCollectionOpen(false);
            setPendingCollectionAssetIds([]);
          } catch (nextError) {
            setError(nextError instanceof Error ? nextError.message : "Unable to add assets to collection.");
          } finally {
            setCollectionBusy(false);
          }
        }}
      />
      <div className="search-layout">
        <button
          type="button"
          aria-label="Close filters"
          className={`search-overlay ${filtersOpen ? "search-overlay-visible" : ""}`}
          onClick={() => setFiltersOpen(false)}
        />
        <aside className={`search-sidebar ${filtersOpen ? "search-sidebar-open" : ""}`}>
          <div className="search-sidebar-header">
            <div>
              <p className="eyebrow">Search Filters</p>
              <h2>Refine the index</h2>
            </div>
            <button className="button ghost-button small-button search-sidebar-close" type="button" onClick={() => setFiltersOpen(false)}>
              Close
            </button>
          </div>
          <FilterSidebar value={filters} onChange={setFilters} tagSuggestions={tagSuggestions} />
          <div className="search-sidebar-actions">
            <button className="button ghost-button small-button" type="button" onClick={resetFilters}>
              Reset
            </button>
            <button className="button small-button" type="button" onClick={applyFilters}>
              Apply Filters
            </button>
          </div>
        </aside>
        <section className="stack search-results">
          <CompareSelectionTray
            selectionMode={selectionMode}
            selectedCount={selected.length}
            compareHref={compareHref}
            onToggleSelectionMode={() => setSelectionMode((value) => !value)}
            onClearSelection={() => setSelected([])}
            hint="Search is metadata-first. Select any number of indexed images for collection work here, and keep exactly two selected when you want to compare."
            canAddToCollection={Boolean(user?.capabilities.can_manage_collections)}
            onAddToCollection={
              user?.capabilities.can_manage_collections
                ? () => {
                  setCollectionMode("selected");
                  setPendingCollectionAssetIds(selected.map((asset) => asset.id));
                  setCollectionOpen(true);
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
            <div style={{ paddingBottom: "0.5rem" }}>
              <button
                type="button"
                className={`button small-button ${bulkMode ? "" : "ghost-button"}`}
                onClick={() => { setBulkMode((v) => !v); setBulkSelectedIds([]); }}
              >
                {bulkMode ? `Bulk Mode (${bulkSelectedIds.length} selected)` : "Bulk Curate"}
              </button>
            </div>
          )}
          <div className="row-between">
            <div>
              <p className="eyebrow">Indexed Results</p>
              <h2>{results?.total ?? 0} assets</h2>
              <p className="subdued">Prompt tags and normal tags are clickable anywhere in the app and flow back into this search filter set.</p>
            </div>
            <div className="card-actions">
              <button className="button ghost-button small-button" type="button" onClick={selectAllLoaded} disabled={!results?.items.length}>
                Select All Loaded
              </button>
              <button className="button ghost-button small-button search-filters-button" type="button" onClick={() => setFiltersOpen(true)}>
                Filters{activeFilters.length || activeTags.length ? ` (${activeFilters.length + activeTags.length})` : ""}
              </button>
              <button className="button small-button desktop-filter-apply" type="button" onClick={applyFilters}>
                Apply Filters
              </button>
            </div>
          </div>
          {activeFilters.length || activeTags.length ? (
            <section className="panel stack">
              <div className="row-between">
                <div>
                  <p className="eyebrow">Active Filters</p>
                  <h2>{activeFilters.length + activeTags.length} active</h2>
                </div>
                <button className="button ghost-button small-button" type="button" onClick={resetFilters}>
                  Clear All
                </button>
              </div>
              <div className="chip-row">
                {activeFilters.map((label) => (
                  <span key={label} className="chip">
                    {label}
                  </span>
                ))}
                {activeTags.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    className="chip buttonless"
                    onClick={() => {
                      const nextFilters = { ...filters, tags: removeTagFilter(filters.tags, tag) };
                      setFilters(nextFilters);
                      pushFilters(nextFilters);
                    }}
                  >
                    {tag} x
                  </button>
                ))}
              </div>
            </section>
          ) : null}
          {error ? <section className="panel empty-state">{error}</section> : null}
          {loading ? <section className="panel empty-state">Loading indexed assets…</section> : null}
          <div className="results-grid">
            {results?.items.map((asset) => (
              <AssetCard
                key={asset.id}
                asset={asset}
                selected={selected.some((item) => item.id === asset.id)}
                onSelect={toggleSelection}
                selectionMode={selectionMode}
                bulkSelected={bulkMode && bulkSelectedIds.includes(asset.id)}
                onBulkToggle={bulkMode ? () => setBulkSelectedIds((ids) => ids.includes(asset.id) ? ids.filter((x) => x !== asset.id) : [...ids, asset.id]) : undefined}
                onAddToCollection={
                  user?.capabilities.can_manage_collections
                    ? (nextAsset) => {
                        setCollectionMode("selected");
                        setPendingCollectionAssetIds([nextAsset.id]);
                        setCollectionOpen(true);
                      }
                    : undefined
                }
              />
            ))}
          </div>
          {results ? (
            <section className="panel stack">
              <div className="row-between">
                <p className="subdued">Showing {results.items.length} of {results.total} indexed assets</p>
                {selected.length ? <p className="subdued">{selected.length} selected for compare</p> : null}
                {loadingMore ? <p className="subdued">Loading more…</p> : null}
              </div>
              {!hasMore && results.items.length ? <p className="subdued">You reached the end of the indexed feed.</p> : null}
              {!results.items.length && !loading ? <p className="subdued">No indexed assets match these filters yet.</p> : null}
              <div ref={sentinelRef} className="infinite-sentinel" />
            </section>
          ) : null}
        </section>
      </div>
    </AppShell>
  );
}

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <AppShell title="Search" description="Indexed discovery with metadata filters, prompt tags, and exact tag search.">
          <section className="panel empty-state">Loading search…</section>
        </AppShell>
      }
    >
      <SearchPageContent />
    </Suspense>
  );
}
