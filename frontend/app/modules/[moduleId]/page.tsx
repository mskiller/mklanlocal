"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { useModuleRegistry } from "@/components/module-registry-provider";
import { useToast } from "@/components/use-toast";
import {
  assetImageUrl,
  createAddonJob,
  fetchAddonAssetArtifacts,
  fetchAddonJobs,
  fetchAddonPresets,
  mediaUrl,
  promoteAddonArtifact,
} from "@/lib/api";
import { formatBytes } from "@/lib/asset-metadata";
import { AddonArtifact, AddonJob, AddonPreset } from "@/lib/types";

const PARAM_EXAMPLES: Record<string, Record<string, unknown>> = {
  metadata_privacy: {
    preserve_profile: "share_safe",
    preserve_gps: false,
    preserve_prompt: false,
  },
  export_recipes: {
    resize_width: 2048,
    output_format: "webp",
    watermark_text: "",
  },
  background_removal: {
    threshold: 40,
    soften_radius: 1.5,
    export_mask: true,
  },
  upscale_restore: {
    scale: 2,
    denoise_strength: 0.3,
    sharpen_strength: 1.0,
  },
  object_erase: {
    fill_mode: "blur",
    feather_radius: 6,
    mask_rects: [{ x: 0.2, y: 0.2, width: 0.18, height: 0.18 }],
  },
};

function isAddonImage(artifact: AddonArtifact) {
  return artifact.mime_type.startsWith("image/");
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) {
    return "Not available";
  }
  return new Date(value).toLocaleString();
}

function parseAssetIds(value: string) {
  return value
    .split(/[\s,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function ArtifactPanel({
  artifact,
  busyArtifactId,
  onPromote,
}: {
  artifact: AddonArtifact;
  busyArtifactId: string | null;
  onPromote: (artifactId: string) => Promise<void>;
}) {
  const artifactUrl = mediaUrl(artifact.content_url) ?? artifact.content_url;
  const originalUrl = artifact.asset_id ? assetImageUrl(artifact.asset_id, { w: 1200, fmt: "jpeg" }) : undefined;
  const cacheHit = artifact.metadata_json?.cache_hit === true;

  return (
    <article className="panel stack">
      <div className="row-between">
        <div>
          <p className="eyebrow">{artifact.label}</p>
          <h3>{artifact.filename}</h3>
        </div>
        <div className="chip-row">
          <span className="chip">{artifact.status}</span>
          {cacheHit ? <span className="chip">cache hit</span> : null}
          {artifact.promoted_at ? <span className="chip">promoted</span> : null}
        </div>
      </div>
      {isAddonImage(artifact) ? (
        <div
          style={{
            display: "grid",
            gap: "1rem",
            gridTemplateColumns: artifact.asset_id ? "repeat(auto-fit, minmax(220px, 1fr))" : "minmax(220px, 1fr)",
          }}
        >
          {originalUrl ? (
            <div className="stack">
              <strong>Original</strong>
              <img
                src={originalUrl}
                alt="Original asset preview"
                style={{ width: "100%", borderRadius: "1rem", objectFit: "cover", background: "rgba(255,255,255,0.04)" }}
              />
            </div>
          ) : null}
          <div className="stack">
            <strong>Result</strong>
            <img
              src={artifactUrl}
              alt={artifact.filename}
              style={{ width: "100%", borderRadius: "1rem", objectFit: "cover", background: "rgba(255,255,255,0.04)" }}
            />
          </div>
        </div>
      ) : null}
      <div className="metadata-grid">
        <div className="metadata-row">
          <strong>Created</strong>
          <div className="subdued">{formatTimestamp(artifact.created_at)}</div>
        </div>
        <div className="metadata-row">
          <strong>Size</strong>
          <div className="subdued">{formatBytes(artifact.size_bytes)}</div>
        </div>
        <div className="metadata-row">
          <strong>Dimensions</strong>
          <div className="subdued">
            {artifact.width && artifact.height ? `${artifact.width} x ${artifact.height}` : "Not image-sized"}
          </div>
        </div>
        <div className="metadata-row">
          <strong>Recipe version</strong>
          <div className="subdued">{artifact.recipe_version}</div>
        </div>
      </div>
      {Object.keys(artifact.metadata_json ?? {}).length ? (
        <label className="field">
          <span>Artifact metadata</span>
          <textarea value={JSON.stringify(artifact.metadata_json, null, 2)} rows={6} readOnly />
        </label>
      ) : null}
      {artifact.promoted_inbox_path ? (
        <p className="subdued">Draft upload: {artifact.promoted_inbox_path}</p>
      ) : null}
      <div className="card-actions">
        <Link href={artifactUrl} target="_blank" rel="noreferrer" className="button subtle-button small-button">
          Open Artifact
        </Link>
        <button
          type="button"
          className="button ghost-button small-button"
          disabled={busyArtifactId === artifact.id}
          onClick={() => void onPromote(artifact.id)}
        >
          {busyArtifactId === artifact.id ? "Promoting..." : "Promote to Draft"}
        </button>
        <Link href={`/inbox`} className="button ghost-button small-button">
          Open Inbox
        </Link>
      </div>
    </article>
  );
}

export default function ModuleAliasPage() {
  const params = useParams<{ moduleId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { push } = useToast();
  const { getModule, loading } = useModuleRegistry();
  const moduleItem = getModule(params.moduleId);
  const canonicalMount = moduleItem?.user_mount ?? null;
  const queryAssetId = searchParams.get("assetId") ?? "";
  const queryAssetIds = searchParams.get("assetIds") ?? "";
  const queryCollectionId = searchParams.get("collectionId") ?? "";

  const [scopeMode, setScopeMode] = useState<"asset" | "batch" | "collection">("asset");
  const [assetIdInput, setAssetIdInput] = useState("");
  const [assetIdsInput, setAssetIdsInput] = useState("");
  const [collectionIdInput, setCollectionIdInput] = useState("");
  const [selectedPresetId, setSelectedPresetId] = useState("");
  const [paramsText, setParamsText] = useState("{}");
  const [presets, setPresets] = useState<AddonPreset[]>([]);
  const [jobs, setJobs] = useState<AddonJob[]>([]);
  const [assetArtifacts, setAssetArtifacts] = useState<AddonArtifact[]>([]);
  const [busy, setBusy] = useState(false);
  const [busyArtifactId, setBusyArtifactId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!moduleItem || !canonicalMount) {
      return;
    }
    const aliasPath = `/modules/${params.moduleId}`;
    if (canonicalMount !== aliasPath) {
      router.replace(canonicalMount);
    }
  }, [canonicalMount, moduleItem, params.moduleId, router]);

  useEffect(() => {
    if (queryCollectionId) {
      setScopeMode("collection");
    } else if (queryAssetIds) {
      setScopeMode("batch");
    } else {
      setScopeMode("asset");
    }
    setAssetIdInput(queryAssetId);
    setAssetIdsInput(queryAssetIds.replaceAll(",", ", "));
    setCollectionIdInput(queryCollectionId);
    setParamsText(JSON.stringify(PARAM_EXAMPLES[params.moduleId] ?? {}, null, 2));
    setMessage(null);
    setError(null);
  }, [params.moduleId, queryAssetId, queryAssetIds, queryCollectionId]);

  const loadAddonData = async () => {
    if (!moduleItem || moduleItem.kind !== "addon") {
      return;
    }
    setRefreshing(true);
    try {
      const [nextPresets, nextJobs] = await Promise.all([fetchAddonPresets(moduleItem.module_id), fetchAddonJobs(moduleItem.module_id, 25)]);
      setPresets(nextPresets);
      setJobs(nextJobs);
      setSelectedPresetId((current) => {
        if (current && nextPresets.some((preset) => preset.id === current)) {
          return current;
        }
        return nextPresets[0]?.id ?? "";
      });
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load addon state.");
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (moduleItem?.kind === "addon" && moduleItem.enabled && moduleItem.status === "active") {
      void loadAddonData();
    }
  }, [moduleItem?.module_id, moduleItem?.kind, moduleItem?.enabled, moduleItem?.status]);

  useEffect(() => {
    if (moduleItem?.kind !== "addon" || scopeMode !== "asset" || !assetIdInput.trim()) {
      setAssetArtifacts([]);
      return;
    }
    let cancelled = false;
    void fetchAddonAssetArtifacts(moduleItem.module_id, assetIdInput.trim())
      .then((nextArtifacts) => {
        if (!cancelled) {
          setAssetArtifacts(nextArtifacts);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAssetArtifacts([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [assetIdInput, moduleItem?.kind, moduleItem?.module_id, scopeMode]);

  const selectedPreset = useMemo(
    () => presets.find((preset) => preset.id === selectedPresetId) ?? null,
    [presets, selectedPresetId]
  );

  if (loading) {
    return (
      <AppShell title="Module" description="Resolving module entrypoint.">
        <section className="panel empty-state">
          <h2>Loading module</h2>
          <p className="subdued">Checking the installed module registry.</p>
        </section>
      </AppShell>
    );
  }

  if (!moduleItem) {
    return (
      <AppShell title="Module Not Found" description="The requested module is not installed.">
        <section className="panel empty-state">
          <h2>Unknown module</h2>
          <p className="subdued">No installed module matches {params.moduleId}.</p>
        </section>
      </AppShell>
    );
  }

  if (!moduleItem.enabled || moduleItem.status !== "active") {
    return (
      <AppShell title={moduleItem.name} description="Module status and fallback routing.">
        <section className="panel empty-state">
          <h2>{moduleItem.name} is unavailable</h2>
          <p className="subdued">{moduleItem.error ?? `Current status: ${moduleItem.status}.`}</p>
          {moduleItem.admin_mount ? (
            <p>
              <Link href={moduleItem.admin_mount} className="button small-button">
                Open Admin Module
              </Link>
            </p>
          ) : null}
        </section>
      </AppShell>
    );
  }

  if (moduleItem.kind !== "addon") {
    return (
      <AppShell title={moduleItem.name} description="Standardized module route alias.">
        <section className="panel empty-state">
          <h2>{moduleItem.name}</h2>
          <p className="subdued">This module does not use the generic addon workbench.</p>
          {canonicalMount ? (
            <Link href={canonicalMount} className="button small-button">
              Continue
            </Link>
          ) : null}
        </section>
      </AppShell>
    );
  }

  return (
    <AppShell
      title={moduleItem.name}
      description={moduleItem.description ?? `${moduleItem.module_id} addon workbench`}
      actions={
        <div className="page-actions">
          <button type="button" className="button ghost-button small-button" onClick={() => void loadAddonData()} disabled={refreshing}>
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
          {moduleItem.admin_mount ? (
            <Link href={moduleItem.admin_mount} className="button subtle-button small-button">
              Admin Settings
            </Link>
          ) : null}
        </div>
      }
    >
      {error ? <section className="panel empty-state">{error}</section> : null}
      {message ? <section className="panel empty-state">{message}</section> : null}

      <section className="two-column">
        <form
          className="panel form-grid"
          onSubmit={async (event: FormEvent) => {
            event.preventDefault();
            setBusy(true);
            setError(null);
            setMessage(null);
            try {
              const parsedParams = paramsText.trim() ? JSON.parse(paramsText) : {};
              if (!parsedParams || Array.isArray(parsedParams) || typeof parsedParams !== "object") {
                throw new Error("Parameters must be a JSON object.");
              }
              const payload: {
                asset_id?: string;
                asset_ids?: string[];
                collection_id?: string;
                preset_id?: string;
                params_json?: Record<string, unknown>;
              } = {
                preset_id: selectedPresetId || undefined,
                params_json: parsedParams as Record<string, unknown>,
              };

              if (scopeMode === "asset") {
                if (!assetIdInput.trim()) {
                  throw new Error("Enter an asset id or launch the addon from Explorer.");
                }
                payload.asset_id = assetIdInput.trim();
              } else if (scopeMode === "batch") {
                const nextAssetIds = parseAssetIds(assetIdsInput);
                if (!nextAssetIds.length) {
                  throw new Error("Enter one or more asset ids for a batch job.");
                }
                payload.asset_ids = nextAssetIds;
              } else {
                if (!collectionIdInput.trim()) {
                  throw new Error("Enter a collection id or launch from a collection page.");
                }
                payload.collection_id = collectionIdInput.trim();
              }

              const created = await createAddonJob(moduleItem.module_id, payload);
              setJobs((current) => [created, ...current.filter((job) => job.id !== created.id)]);
              setMessage(`Queued ${moduleItem.name} job and stored ${created.artifact_count} artifacts.`);
              push(`${moduleItem.name} job completed. Review artifacts below.`, "success");
              if (scopeMode === "asset" && payload.asset_id) {
                setAssetArtifacts(await fetchAddonAssetArtifacts(moduleItem.module_id, payload.asset_id));
              }
            } catch (nextError) {
              const detail = nextError instanceof Error ? nextError.message : "Unable to run addon job.";
              setError(detail);
              push(detail, "error");
            } finally {
              setBusy(false);
            }
          }}
        >
          <div>
            <p className="eyebrow">Run Job</p>
            <h2>Scope and recipe</h2>
          </div>
          <div className="chip-row">
            <button type="button" className={`button small-button ${scopeMode === "asset" ? "" : "ghost-button"}`} onClick={() => setScopeMode("asset")}>
              Asset
            </button>
            <button type="button" className={`button small-button ${scopeMode === "batch" ? "" : "ghost-button"}`} onClick={() => setScopeMode("batch")}>
              Batch
            </button>
            <button type="button" className={`button small-button ${scopeMode === "collection" ? "" : "ghost-button"}`} onClick={() => setScopeMode("collection")}>
              Collection
            </button>
          </div>
          {scopeMode === "asset" ? (
            <label className="field">
              <span>Asset id</span>
              <input value={assetIdInput} onChange={(event) => setAssetIdInput(event.target.value)} placeholder="UUID from explorer or asset detail" />
            </label>
          ) : null}
          {scopeMode === "batch" ? (
            <label className="field">
              <span>Asset ids</span>
              <textarea
                value={assetIdsInput}
                onChange={(event) => setAssetIdsInput(event.target.value)}
                rows={4}
                placeholder="Paste comma-separated asset ids from multi-select"
              />
            </label>
          ) : null}
          {scopeMode === "collection" ? (
            <label className="field">
              <span>Collection id</span>
              <input value={collectionIdInput} onChange={(event) => setCollectionIdInput(event.target.value)} placeholder="UUID from collection page" />
            </label>
          ) : null}
          <label className="field">
            <span>Preset</span>
            <select value={selectedPresetId} onChange={(event) => setSelectedPresetId(event.target.value)}>
              <option value="">No preset</option>
              {presets.map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.name}{preset.is_builtin ? " (built-in)" : ""}
                </option>
              ))}
            </select>
            {selectedPreset?.description ? <small className="subdued">{selectedPreset.description}</small> : null}
          </label>
          <label className="field">
            <span>Params override (JSON)</span>
            <textarea value={paramsText} onChange={(event) => setParamsText(event.target.value)} rows={10} />
            <small className="subdued">Preset config is merged first, then these JSON values override it for this job.</small>
          </label>
          <div className="card-actions">
            <button className="button small-button" type="submit" disabled={busy}>
              {busy ? "Running..." : `Run ${moduleItem.name}`}
            </button>
            <button
              className="button ghost-button small-button"
              type="button"
              onClick={() => setParamsText(JSON.stringify(PARAM_EXAMPLES[moduleItem.module_id] ?? {}, null, 2))}
            >
              Reset Example
            </button>
          </div>
        </form>

        <section className="panel stack">
          <div>
            <p className="eyebrow">Module Contract</p>
            <h2>Derivative-first review flow</h2>
          </div>
          <p className="subdued">
            Jobs create separate artifacts, keep per-asset history, and only move outputs into drafts when you explicitly promote them.
          </p>
          <div className="chip-row">
            <span className="chip">{moduleItem.module_id}</span>
            <span className="chip">{moduleItem.version}</span>
            <span className="chip">{presets.length} presets</span>
            <span className="chip">{jobs.length} recent jobs</span>
          </div>
          <div className="metadata-grid">
            <div className="metadata-row">
              <strong>User surface</strong>
              <div className="subdued">{moduleItem.user_mount ?? "None"}</div>
            </div>
            <div className="metadata-row">
              <strong>API mount</strong>
              <div className="subdued">{moduleItem.api_mount ?? "None"}</div>
            </div>
            <div className="metadata-row">
              <strong>Admin surface</strong>
              <div className="subdued">{moduleItem.admin_mount ?? "None"}</div>
            </div>
            <div className="metadata-row">
              <strong>Dependencies</strong>
              <div className="subdued">{moduleItem.dependencies.length ? moduleItem.dependencies.join(", ") : "None"}</div>
            </div>
          </div>
          {selectedPreset ? (
            <label className="field">
              <span>Selected preset config</span>
              <textarea value={JSON.stringify(selectedPreset.config_json, null, 2)} rows={6} readOnly />
            </label>
          ) : null}
          <div className="card-actions">
            <Link href="/browse-indexed" className="button subtle-button small-button">
              Open Explorer
            </Link>
            <Link href="/search" className="button ghost-button small-button">
              Open Search
            </Link>
            <Link href="/collections" className="button ghost-button small-button">
              Open Collections
            </Link>
          </div>
        </section>
      </section>

      {scopeMode === "asset" && assetIdInput.trim() ? (
        <section className="panel stack">
          <div className="row-between">
            <div>
              <p className="eyebrow">Asset History</p>
              <h2>{assetArtifacts.length} artifacts for this asset</h2>
            </div>
          </div>
          {assetArtifacts.length ? (
            assetArtifacts.map((artifact) => (
              <ArtifactPanel
                key={`history-${artifact.id}`}
                artifact={artifact}
                busyArtifactId={busyArtifactId}
                onPromote={async (artifactId) => {
                  setBusyArtifactId(artifactId);
                  setError(null);
                  setMessage(null);
                  try {
                    const response = await promoteAddonArtifact(moduleItem.module_id, artifactId, moduleItem.module_id);
                    setMessage(`Promoted artifact to ${response.uploaded_files[0]}.`);
                    push("Artifact promoted to Inbox draft.", "success");
                    setAssetArtifacts(await fetchAddonAssetArtifacts(moduleItem.module_id, assetIdInput.trim()));
                    await loadAddonData();
                  } catch (nextError) {
                    const detail = nextError instanceof Error ? nextError.message : "Unable to promote artifact.";
                    setError(detail);
                    push(detail, "error");
                  } finally {
                    setBusyArtifactId(null);
                  }
                }}
              />
            ))
          ) : (
            <p className="subdued">No artifact history for this asset yet.</p>
          )}
        </section>
      ) : null}

      <section className="stack">
        <div className="row-between">
          <div>
            <p className="eyebrow">Recent Jobs</p>
            <h2>{jobs.length} recent runs</h2>
          </div>
        </div>
        {jobs.length ? (
          jobs.map((job) => (
            <section key={job.id} className="panel stack">
              <div className="row-between">
                <div>
                  <p className="eyebrow">{job.scope_type}</p>
                  <h3>{job.id}</h3>
                </div>
                <div className="chip-row">
                  <span className="chip">{job.status}</span>
                  <span className="chip">{job.progress}%</span>
                  <span className="chip">{job.artifact_count} artifacts</span>
                </div>
              </div>
              <p className="subdued">{job.error_message ?? job.message ?? "No status message."}</p>
              <div className="metadata-grid">
                <div className="metadata-row">
                  <strong>Created</strong>
                  <div className="subdued">{formatTimestamp(job.created_at)}</div>
                </div>
                <div className="metadata-row">
                  <strong>Started</strong>
                  <div className="subdued">{formatTimestamp(job.started_at)}</div>
                </div>
                <div className="metadata-row">
                  <strong>Finished</strong>
                  <div className="subdued">{formatTimestamp(job.finished_at)}</div>
                </div>
                <div className="metadata-row">
                  <strong>Scope</strong>
                  <div className="subdued">{JSON.stringify(job.scope_json)}</div>
                </div>
              </div>
              <label className="field">
                <span>Resolved params</span>
                <textarea value={JSON.stringify(job.params_json, null, 2)} rows={6} readOnly />
              </label>
              {job.artifacts.length ? (
                job.artifacts.map((artifact) => (
                  <ArtifactPanel
                    key={artifact.id}
                    artifact={artifact}
                    busyArtifactId={busyArtifactId}
                    onPromote={async (artifactId) => {
                      setBusyArtifactId(artifactId);
                      setError(null);
                      setMessage(null);
                      try {
                        const response = await promoteAddonArtifact(moduleItem.module_id, artifactId, moduleItem.module_id);
                        setMessage(`Promoted artifact to ${response.uploaded_files[0]}.`);
                        push("Artifact promoted to Inbox draft.", "success");
                        await loadAddonData();
                        if (scopeMode === "asset" && assetIdInput.trim()) {
                          setAssetArtifacts(await fetchAddonAssetArtifacts(moduleItem.module_id, assetIdInput.trim()));
                        }
                      } catch (nextError) {
                        const detail = nextError instanceof Error ? nextError.message : "Unable to promote artifact.";
                        setError(detail);
                        push(detail, "error");
                      } finally {
                        setBusyArtifactId(null);
                      }
                    }}
                  />
                ))
              ) : (
                <p className="subdued">This job has not produced artifacts yet.</p>
              )}
            </section>
          ))
        ) : (
          <section className="panel empty-state">
            <h2>No addon jobs yet</h2>
            <p className="subdued">Launch this module from explorer, bulk selection, or collections to prefill the workbench.</p>
          </section>
        )}
      </section>
    </AppShell>
  );
}
