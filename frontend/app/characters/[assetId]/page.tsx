"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { useModuleRegistry } from "@/components/module-registry-provider";
import { fetchCharacterCard, mediaUrl, updateCharacterCard } from "@/lib/api";
import { CharacterCardDetail, CharacterCardUpdateRequest } from "@/lib/types";

type CharacterDraft = {
  name: string;
  description: string;
  personality: string;
  scenario: string;
  first_message: string;
  message_examples: string;
  creator_notes: string;
  system_prompt: string;
  post_history_instructions: string;
  creator: string;
  character_version: string;
  tags: string;
  alternate_greetings: string;
  group_only_greetings: string;
};

const EMPTY_DRAFT: CharacterDraft = {
  name: "",
  description: "",
  personality: "",
  scenario: "",
  first_message: "",
  message_examples: "",
  creator_notes: "",
  system_prompt: "",
  post_history_instructions: "",
  creator: "",
  character_version: "",
  tags: "",
  alternate_greetings: "",
  group_only_greetings: "",
};

function splitLines(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function splitCommaList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function draftFromDetail(detail: CharacterCardDetail): CharacterDraft {
  return {
    name: detail.name ?? "",
    description: detail.description ?? "",
    personality: detail.personality ?? "",
    scenario: detail.scenario ?? "",
    first_message: detail.first_message ?? "",
    message_examples: detail.message_examples ?? "",
    creator_notes: detail.creator_notes ?? "",
    system_prompt: detail.system_prompt ?? "",
    post_history_instructions: detail.post_history_instructions ?? "",
    creator: detail.creator ?? "",
    character_version: detail.character_version ?? "",
    tags: detail.tags.join(", "),
    alternate_greetings: detail.alternate_greetings.join("\n"),
    group_only_greetings: detail.group_only_greetings.join("\n"),
  };
}

export default function CharacterDetailPage() {
  const params = useParams<{ assetId: string }>();
  const { user } = useAuth();
  const { getModule, loading: modulesLoading } = useModuleRegistry();
  const [detail, setDetail] = useState<CharacterCardDetail | null>(null);
  const [draft, setDraft] = useState<CharacterDraft>(EMPTY_DRAFT);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const charactersModule = getModule("characters");
  const moduleActive = Boolean(charactersModule?.enabled && charactersModule.status === "active");
  const canEdit = Boolean(user?.capabilities.can_curate_assets);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const nextDetail = await fetchCharacterCard(params.assetId);
      setDetail(nextDetail);
      setDraft(draftFromDetail(nextDetail));
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load character.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!modulesLoading && moduleActive) {
      void load();
    }
  }, [moduleActive, modulesLoading, params.assetId]);

  if (modulesLoading) {
    return (
      <AppShell title="Character" description="Loading character-card module status.">
        <section className="panel empty-state">Checking characters module…</section>
      </AppShell>
    );
  }

  if (!charactersModule) {
    return (
      <AppShell title="Character" description="SillyTavern PNG character-card editing.">
        <section className="panel empty-state">
          <h2>Characters module not installed</h2>
          <p className="subdued">The built-in characters module is missing from the module registry.</p>
        </section>
      </AppShell>
    );
  }

  if (!moduleActive) {
    return (
      <AppShell title="Character" description="SillyTavern PNG character-card editing.">
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

  const save = async () => {
    const payload: CharacterCardUpdateRequest = {
      name: draft.name,
      description: draft.description,
      personality: draft.personality,
      scenario: draft.scenario,
      first_message: draft.first_message,
      message_examples: draft.message_examples,
      creator_notes: draft.creator_notes,
      system_prompt: draft.system_prompt,
      post_history_instructions: draft.post_history_instructions,
      creator: draft.creator || null,
      character_version: draft.character_version || null,
      tags: splitCommaList(draft.tags),
      alternate_greetings: splitLines(draft.alternate_greetings),
      group_only_greetings: splitLines(draft.group_only_greetings),
    };
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const nextDetail = await updateCharacterCard(params.assetId, payload);
      setDetail(nextDetail);
      setDraft(draftFromDetail(nextDetail));
      setMessage("Character card saved and re-indexed.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to save character.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell
      title={detail?.name ?? "Character"}
      description={detail ? `${detail.source_name} · ${detail.filename}` : "SillyTavern PNG character-card editor."}
      actions={
        <div className="page-actions">
          <Link href="/characters" className="button subtle-button small-button">All Characters</Link>
          {detail ? <Link href={`/assets/${detail.asset_id}`} className="button ghost-button small-button">Open Asset</Link> : null}
        </div>
      }
    >
      {error ? <section className="panel empty-state">{error}</section> : null}
      {message ? <section className="panel empty-state">{message}</section> : null}

      {!canEdit ? (
        <section className="panel empty-state">
          <p className="subdued">You can inspect this character card, but editing is reserved for curator and admin roles.</p>
        </section>
      ) : null}

      {loading ? (
        <section className="panel empty-state">Loading character…</section>
      ) : detail ? (
        <>
          <section className="two-column">
            <article className="panel stack">
              <div>
                <p className="eyebrow">Preview</p>
                <h2>{detail.name}</h2>
              </div>
              <img
                src={mediaUrl(detail.preview_url ?? detail.content_url)}
                alt={detail.name}
                style={{ width: "100%", borderRadius: "1rem", border: "1px solid var(--border)", objectFit: "cover" }}
              />
              <div className="chip-row">
                <span className="chip">{detail.source_name}</span>
                <span className="chip">{detail.spec}</span>
                <span className="chip">v{detail.spec_version}</span>
              </div>
              <p className="subdued">{detail.relative_path}</p>
            </article>

            <article className="panel stack">
              <div>
                <p className="eyebrow">Summary</p>
                <h2>Embedded card status</h2>
              </div>
              <div className="metadata-grid">
                <div className="metadata-row">
                  <strong>Name</strong>
                  <div className="subdued">{detail.name}</div>
                </div>
                <div className="metadata-row">
                  <strong>Creator</strong>
                  <div className="subdued">{detail.creator ?? "n/a"}</div>
                </div>
                <div className="metadata-row">
                  <strong>Updated</strong>
                  <div className="subdued">{new Date(detail.updated_at).toLocaleString()}</div>
                </div>
                <div className="metadata-row">
                  <strong>Tags</strong>
                  <div className="subdued">{detail.tags.length ? detail.tags.join(", ") : "n/a"}</div>
                </div>
              </div>
              <a href={mediaUrl(detail.content_url)} target="_blank" rel="noopener noreferrer" className="button ghost-button small-button">
                Open Original PNG
              </a>
            </article>
          </section>

          <section className="panel form-grid">
            <div>
              <p className="eyebrow">Editor</p>
              <h2>Core persona fields</h2>
            </div>
            <div className="two-column">
              <label className="field">
                <span>Name</span>
                <input value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} disabled={!canEdit} />
              </label>
              <label className="field">
                <span>Creator</span>
                <input value={draft.creator} onChange={(event) => setDraft((current) => ({ ...current, creator: event.target.value }))} disabled={!canEdit} />
              </label>
            </div>
            <label className="field">
              <span>Description</span>
              <textarea value={draft.description} onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))} rows={5} disabled={!canEdit} />
            </label>
            <div className="two-column">
              <label className="field">
                <span>Personality</span>
                <textarea value={draft.personality} onChange={(event) => setDraft((current) => ({ ...current, personality: event.target.value }))} rows={5} disabled={!canEdit} />
              </label>
              <label className="field">
                <span>Scenario</span>
                <textarea value={draft.scenario} onChange={(event) => setDraft((current) => ({ ...current, scenario: event.target.value }))} rows={5} disabled={!canEdit} />
              </label>
            </div>
            <label className="field">
              <span>First Message</span>
              <textarea value={draft.first_message} onChange={(event) => setDraft((current) => ({ ...current, first_message: event.target.value }))} rows={5} disabled={!canEdit} />
            </label>
            <label className="field">
              <span>Message Examples</span>
              <textarea value={draft.message_examples} onChange={(event) => setDraft((current) => ({ ...current, message_examples: event.target.value }))} rows={6} disabled={!canEdit} />
            </label>
          </section>

          <section className="two-column">
            <article className="panel form-grid">
              <div>
                <p className="eyebrow">Advanced</p>
                <h2>Prompts and guidance</h2>
              </div>
              <label className="field">
                <span>Creator Notes</span>
                <textarea value={draft.creator_notes} onChange={(event) => setDraft((current) => ({ ...current, creator_notes: event.target.value }))} rows={4} disabled={!canEdit} />
              </label>
              <label className="field">
                <span>System Prompt</span>
                <textarea value={draft.system_prompt} onChange={(event) => setDraft((current) => ({ ...current, system_prompt: event.target.value }))} rows={6} disabled={!canEdit} />
              </label>
              <label className="field">
                <span>Post-History Instructions</span>
                <textarea value={draft.post_history_instructions} onChange={(event) => setDraft((current) => ({ ...current, post_history_instructions: event.target.value }))} rows={4} disabled={!canEdit} />
              </label>
              <label className="field">
                <span>Character Version</span>
                <input value={draft.character_version} onChange={(event) => setDraft((current) => ({ ...current, character_version: event.target.value }))} disabled={!canEdit} />
              </label>
            </article>

            <article className="panel form-grid">
              <div>
                <p className="eyebrow">Greetings & Tags</p>
                <h2>Conversation starters</h2>
              </div>
              <label className="field">
                <span>Tags</span>
                <input value={draft.tags} onChange={(event) => setDraft((current) => ({ ...current, tags: event.target.value }))} placeholder="comma, separated, tags" disabled={!canEdit} />
              </label>
              <label className="field">
                <span>Alternate Greetings</span>
                <textarea value={draft.alternate_greetings} onChange={(event) => setDraft((current) => ({ ...current, alternate_greetings: event.target.value }))} rows={6} placeholder="One greeting per line" disabled={!canEdit} />
              </label>
              <label className="field">
                <span>Group-Only Greetings</span>
                <textarea value={draft.group_only_greetings} onChange={(event) => setDraft((current) => ({ ...current, group_only_greetings: event.target.value }))} rows={6} placeholder="One greeting per line" disabled={!canEdit} />
              </label>
            </article>
          </section>

          <section className="panel stack">
            <div className="row-between">
              <div>
                <p className="eyebrow">Canonical JSON</p>
                <h2>Read-only payload</h2>
              </div>
              <button type="button" className="button small-button" disabled={!canEdit || saving} onClick={() => void save()}>
                {saving ? "Saving..." : "Save Character"}
              </button>
            </div>
            <pre className="prompt-content subdued" style={{ maxHeight: "420px", overflow: "auto", fontSize: "0.82rem" }}>
              {JSON.stringify(detail.canonical_card, null, 2)}
            </pre>
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
