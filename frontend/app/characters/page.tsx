"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { useModuleRegistry } from "@/components/module-registry-provider";
import { fetchCharacterCards, fetchSources, mediaUrl } from "@/lib/api";
import { CharacterCardListResponse, Source } from "@/lib/types";

const EMPTY_RESULTS: CharacterCardListResponse = {
  items: [],
  total: 0,
  page: 1,
  page_size: 24,
};

export default function CharactersPage() {
  const { getModule, loading: modulesLoading } = useModuleRegistry();
  const [results, setResults] = useState<CharacterCardListResponse>(EMPTY_RESULTS);
  const [sources, setSources] = useState<Source[]>([]);
  const [query, setQuery] = useState("");
  const [creator, setCreator] = useState("");
  const [tag, setTag] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const charactersModule = getModule("characters");
  const moduleActive = Boolean(charactersModule?.enabled && charactersModule.status === "active");

  const load = async (page = 1) => {
    setLoading(true);
    setError(null);
    try {
      const [nextResults, nextSources] = await Promise.all([
        fetchCharacterCards({
          q: query || undefined,
          creator: creator || undefined,
          tag: tag || undefined,
          source_id: sourceId || undefined,
          page,
          page_size: results.page_size || 24,
        }),
        fetchSources(),
      ]);
      setResults(nextResults);
      setSources(nextSources);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load characters.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!modulesLoading && moduleActive) {
      void load(1);
    }
  }, [moduleActive, modulesLoading]);

  if (modulesLoading) {
    return (
      <AppShell title="Characters" description="Loading character-card module status.">
        <section className="panel empty-state">Checking characters module…</section>
      </AppShell>
    );
  }

  if (!charactersModule) {
    return (
      <AppShell title="Characters" description="SillyTavern PNG character-card browsing and editing.">
        <section className="panel empty-state">
          <h2>Characters module not installed</h2>
          <p className="subdued">This surface now comes from the built-in characters module, but it is not available in the module registry.</p>
        </section>
      </AppShell>
    );
  }

  if (!moduleActive) {
    return (
      <AppShell title="Characters" description="SillyTavern PNG character-card browsing and editing.">
        <section className="panel empty-state">
          <h2>Characters is unavailable</h2>
          <p className="subdued">{charactersModule.error ?? `Current status: ${charactersModule.status}.`}</p>
          {charactersModule.admin_mount ? (
            <p>
              <Link href={charactersModule.admin_mount} className="button small-button">Open Module Settings</Link>
            </p>
          ) : null}
        </section>
      </AppShell>
    );
  }

  const hasPreviousPage = results.page > 1;
  const hasNextPage = results.page * results.page_size < results.total;

  return (
    <AppShell
      title="Characters"
      description="Browse embedded SillyTavern PNG cards, then jump straight into editing when you need to tune persona text or greetings."
      actions={
        <div className="page-actions">
          <Link href="/search" className="button subtle-button small-button">Open Search</Link>
          <Link href="/browse-indexed" className="button ghost-button small-button">Browse Indexed</Link>
        </div>
      }
    >
      {error ? <section className="panel empty-state">{error}</section> : null}

      <section className="panel form-grid">
        <div>
          <p className="eyebrow">Library Filters</p>
          <h2>Find a character card fast</h2>
        </div>
        <form
          className="form-grid"
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            void load(1);
          }}
        >
          <div className="two-column">
            <label className="field">
              <span>Search</span>
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name, description, or filename" />
            </label>
            <label className="field">
              <span>Creator</span>
              <input value={creator} onChange={(event) => setCreator(event.target.value)} placeholder="Filter by creator" />
            </label>
          </div>
          <div className="two-column">
            <label className="field">
              <span>Tag</span>
              <input value={tag} onChange={(event) => setTag(event.target.value)} placeholder="Filter by tag" />
            </label>
            <label className="field">
              <span>Source</span>
              <select value={sourceId} onChange={(event) => setSourceId(event.target.value)}>
                <option value="">All visible sources</option>
                {sources.map((source) => (
                  <option key={source.id} value={source.id}>{source.name}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="card-actions">
            <button className="button small-button" type="submit" disabled={loading}>
              {loading ? "Loading..." : "Apply Filters"}
            </button>
            <button
              type="button"
              className="button ghost-button small-button"
              onClick={() => {
                setQuery("");
                setCreator("");
                setTag("");
                setSourceId("");
                void load(1);
              }}
              disabled={loading}
            >
              Reset
            </button>
          </div>
        </form>
      </section>

      <section className="panel stack">
        <div className="row-between">
          <div>
            <p className="eyebrow">Detected Cards</p>
            <h2>{results.total} characters</h2>
          </div>
          <div className="card-actions">
            <button type="button" className="button ghost-button small-button" disabled={!hasPreviousPage || loading} onClick={() => void load(results.page - 1)}>
              Previous
            </button>
            <span className="subdued">Page {results.page}</span>
            <button type="button" className="button ghost-button small-button" disabled={!hasNextPage || loading} onClick={() => void load(results.page + 1)}>
              Next
            </button>
          </div>
        </div>

        {loading ? (
          <div className="empty-state">Loading characters…</div>
        ) : results.items.length ? (
          <div className="collection-grid">
            {results.items.map((character) => (
              <Link key={character.asset_id} href={`/characters/${character.asset_id}`} className="collection-card">
                <div className="collection-card-visual" style={{ minHeight: "240px", overflow: "hidden" }}>
                  <img
                    src={mediaUrl(character.preview_url ?? character.content_url)}
                    alt={character.name}
                    style={{ width: "100%", height: "240px", objectFit: "cover" }}
                  />
                </div>
                <div className="collection-card-body">
                  <strong>{character.name}</strong>
                  <p className="subdued">{character.creator ? `By ${character.creator}` : character.filename}</p>
                  {character.description ? <p className="subdued">{character.description.slice(0, 140)}</p> : null}
                  <div className="chip-row">
                    <span className="chip">{character.source_name}</span>
                    {character.tags.slice(0, 3).map((value) => (
                      <span key={`${character.asset_id}-${value}`} className="chip">{value}</span>
                    ))}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            No character cards match the current filters.
          </div>
        )}
      </section>
    </AppShell>
  );
}
