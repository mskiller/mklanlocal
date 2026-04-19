"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { useModuleRegistry } from "@/components/module-registry-provider";
import { createAddonPreset, fetchAddonPresets, fetchAdminModule, updateAddonPreset, updateAdminModule } from "@/lib/api";
import { AddonPreset, ModuleSettingFieldRead, PlatformModule } from "@/lib/types";

function normalizeDraftValue(field: ModuleSettingFieldRead, rawValue: unknown) {
  if (field.type === "boolean") {
    return Boolean(rawValue);
  }
  if (rawValue === null || rawValue === undefined) {
    return "";
  }
  return String(rawValue);
}

export default function AdminModuleDetailPage() {
  const params = useParams<{ moduleId: string }>();
  const { user } = useAuth();
  const { refresh: refreshRegistry } = useModuleRegistry();
  const [moduleItem, setModuleItem] = useState<PlatformModule | null>(null);
  const [presets, setPresets] = useState<AddonPreset[]>([]);
  const [presetDrafts, setPresetDrafts] = useState<Record<string, { name: string; description: string; configText: string }>>({});
  const [newPresetName, setNewPresetName] = useState("");
  const [newPresetDescription, setNewPresetDescription] = useState("");
  const [newPresetConfigText, setNewPresetConfigText] = useState("{\n  \n}");
  const [presetBusy, setPresetBusy] = useState<string | null>(null);
  const [presetError, setPresetError] = useState<string | null>(null);
  const [presetMessage, setPresetMessage] = useState<string | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [settingsDraft, setSettingsDraft] = useState<Record<string, string | boolean>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadPresets = async (nextModule: PlatformModule) => {
    if (nextModule.kind !== "addon") {
      setPresets([]);
      setPresetDrafts({});
      setPresetError(null);
      return;
    }
    try {
      const nextPresets = await fetchAddonPresets(nextModule.module_id);
      setPresets(nextPresets);
      setPresetDrafts(
        Object.fromEntries(
          nextPresets.map((preset) => [
            preset.id,
            {
              name: preset.name,
              description: preset.description ?? "",
              configText: JSON.stringify(preset.config_json, null, 2),
            },
          ])
        )
      );
      setPresetError(null);
    } catch (nextError) {
      setPresets([]);
      setPresetDrafts({});
      setPresetError(nextError instanceof Error ? nextError.message : "Unable to load addon presets.");
    }
  };

  const load = async () => {
    try {
      const nextModule = await fetchAdminModule(params.moduleId);
      setModuleItem(nextModule);
      setEnabled(nextModule.enabled);
      setSettingsDraft(
        Object.fromEntries(
          nextModule.settings_schema.map((field) => [
            field.key,
            normalizeDraftValue(field, nextModule.settings_json[field.key] ?? field.default),
          ])
        )
      );
      await loadPresets(nextModule);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load module.");
    }
  };

  useEffect(() => {
    if (user?.capabilities.can_view_admin) {
      void load();
    }
  }, [params.moduleId, user?.capabilities.can_view_admin]);

  if (user && !user.capabilities.can_view_admin) {
    return (
      <AppShell title="Module" description="Module configuration and dependency health.">
        <section className="panel empty-state">
          <h2>Admin only</h2>
          <p className="subdued">This page is only available to admin users.</p>
        </section>
      </AppShell>
    );
  }

  return (
    <AppShell
      title={moduleItem?.name ?? "Module"}
      description={moduleItem ? `${moduleItem.module_id} · ${moduleItem.status}` : "Module configuration and dependency health."}
      actions={
        <div className="page-actions">
          <Link href="/admin/modules" className="button subtle-button small-button">All Modules</Link>
          {moduleItem?.user_mount ? <Link href={moduleItem.user_mount} className="button ghost-button small-button">Open User Surface</Link> : null}
        </div>
      }
    >
      {error ? <section className="panel empty-state">{error}</section> : null}
      {message ? <section className="panel empty-state">{message}</section> : null}
      {presetError ? <section className="panel empty-state">{presetError}</section> : null}
      {presetMessage ? <section className="panel empty-state">{presetMessage}</section> : null}

      {moduleItem ? (
        <>
          <section className="two-column">
            <section className="panel stack">
              <div>
                <p className="eyebrow">Status</p>
                <h2>Module health</h2>
              </div>
              <div className="chip-row">
                <span className="chip">{moduleItem.status}</span>
                <span className="chip">{moduleItem.enabled ? "enabled" : "disabled"}</span>
                <span className="chip">API v{moduleItem.platform_api_version}</span>
              </div>
              {moduleItem.description ? <p className="subdued">{moduleItem.description}</p> : null}
              {moduleItem.error ? <p className="subdued">{moduleItem.error}</p> : null}
              <div className="list-stack compact-list-stack">
                <div className="metadata-row">
                  <strong>Source</strong>
                  <p className="subdued">{moduleItem.source_ref ?? "built-in"}</p>
                </div>
                <div className="metadata-row">
                  <strong>Manifest</strong>
                  <p className="subdued">{moduleItem.manifest_path ?? "Not reported"}</p>
                </div>
                <div className="metadata-row">
                  <strong>Backend entrypoint</strong>
                  <p className="subdued">{moduleItem.backend_entrypoint ?? "None"}</p>
                </div>
                <div className="metadata-row">
                  <strong>Worker entrypoint</strong>
                  <p className="subdued">{moduleItem.worker_entrypoint ?? "None"}</p>
                </div>
                <div className="metadata-row">
                  <strong>Frontend entrypoint</strong>
                  <p className="subdued">{moduleItem.frontend_entrypoint ?? "None"}</p>
                </div>
                <div className="metadata-row">
                  <strong>Migrations</strong>
                  <p className="subdued">{moduleItem.backend_migrations ?? "None"}</p>
                </div>
              </div>
              <div className="chip-row">
                {moduleItem.dependencies.map((dependency) => (
                  <span key={`${moduleItem.module_id}-dep-${dependency}`} className="chip">depends on {dependency}</span>
                ))}
                {moduleItem.permissions.map((permission) => (
                  <span key={`${moduleItem.module_id}-perm-${permission}`} className="chip">{permission}</span>
                ))}
              </div>
            </section>

            <form
              className="panel form-grid"
              onSubmit={async (event: FormEvent) => {
                event.preventDefault();
                setBusy(true);
                setError(null);
                setMessage(null);
                try {
                  const settingsPayload = Object.fromEntries(
                    moduleItem.settings_schema.map((field) => {
                      const rawValue = settingsDraft[field.key];
                      if (field.type === "boolean") {
                        return [field.key, Boolean(rawValue)];
                      }
                      if (field.type === "integer") {
                        return [field.key, rawValue === "" ? null : Number.parseInt(String(rawValue), 10)];
                      }
                      if (field.type === "number") {
                        return [field.key, rawValue === "" ? null : Number(rawValue)];
                      }
                      return [field.key, String(rawValue ?? "")];
                    })
                  );
                  const updated = await updateAdminModule(moduleItem.module_id, {
                    enabled,
                    settings_json: settingsPayload,
                  });
                  setModuleItem(updated);
                  setEnabled(updated.enabled);
                  setSettingsDraft(
                    Object.fromEntries(
                      updated.settings_schema.map((field) => [
                        field.key,
                        normalizeDraftValue(field, updated.settings_json[field.key] ?? field.default),
                      ])
                    )
                  );
                  await refreshRegistry();
                  setMessage("Module configuration saved.");
                } catch (nextError) {
                  setError(nextError instanceof Error ? nextError.message : "Unable to save module settings.");
                } finally {
                  setBusy(false);
                }
              }}
            >
              <div>
                <p className="eyebrow">Configuration</p>
                <h2>Runtime settings</h2>
              </div>
              <label className="field checkbox-field">
                <span>Enabled</span>
                <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />
              </label>
              {moduleItem.settings_schema.length === 0 ? (
                <p className="subdued">This module does not expose configurable settings yet.</p>
              ) : (
                moduleItem.settings_schema.map((field) => (
                  <label key={field.key} className={`field ${field.type === "boolean" ? "checkbox-field" : ""}`.trim()}>
                    <span>{field.label}</span>
                    {field.type === "boolean" ? (
                      <input
                        type="checkbox"
                        checked={Boolean(settingsDraft[field.key])}
                        onChange={(event) => setSettingsDraft((current) => ({ ...current, [field.key]: event.target.checked }))}
                      />
                    ) : (
                      <input
                        type={field.type === "string" ? "text" : "number"}
                        value={String(settingsDraft[field.key] ?? "")}
                        onChange={(event) => setSettingsDraft((current) => ({ ...current, [field.key]: event.target.value }))}
                      />
                    )}
                    {field.description ? <small className="subdued">{field.description}</small> : null}
                  </label>
                ))
              )}
              <button className="button small-button" type="submit" disabled={busy}>
                {busy ? "Saving..." : "Save Module"}
              </button>
            </form>
          </section>
          {moduleItem.kind === "addon" ? (
            <section className="panel stack">
              <div className="row-between">
                <div>
                  <p className="eyebrow">Addon Presets</p>
                  <h2>Recipe library</h2>
                </div>
                <span className="chip">{presets.length} presets</span>
              </div>
              <form
                className="form-grid"
                onSubmit={async (event) => {
                  event.preventDefault();
                  setPresetBusy("new");
                  setPresetError(null);
                  setPresetMessage(null);
                  try {
                    const configJson = newPresetConfigText.trim() ? JSON.parse(newPresetConfigText) : {};
                    await createAddonPreset(moduleItem.module_id, {
                      name: newPresetName,
                      description: newPresetDescription || null,
                      config_json: configJson,
                    });
                    setNewPresetName("");
                    setNewPresetDescription("");
                    setNewPresetConfigText("{\n  \n}");
                    await loadPresets(moduleItem);
                    setPresetMessage("Preset created.");
                  } catch (nextError) {
                    setPresetError(nextError instanceof Error ? nextError.message : "Unable to create preset.");
                  } finally {
                    setPresetBusy(null);
                  }
                }}
              >
                <label className="field">
                  <span>Preset name</span>
                  <input value={newPresetName} onChange={(event) => setNewPresetName(event.target.value)} placeholder="Web share 1600px" />
                </label>
                <label className="field">
                  <span>Description</span>
                  <input value={newPresetDescription} onChange={(event) => setNewPresetDescription(event.target.value)} placeholder="When and why the team should use it" />
                </label>
                <label className="field">
                  <span>Config JSON</span>
                  <textarea value={newPresetConfigText} onChange={(event) => setNewPresetConfigText(event.target.value)} rows={8} />
                </label>
                <button className="button small-button" type="submit" disabled={presetBusy === "new"}>
                  {presetBusy === "new" ? "Creating..." : "Create Preset"}
                </button>
              </form>
              {presets.length ? (
                presets.map((preset) => {
                  const draft = presetDrafts[preset.id] ?? {
                    name: preset.name,
                    description: preset.description ?? "",
                    configText: JSON.stringify(preset.config_json, null, 2),
                  };
                  return (
                    <form
                      key={preset.id}
                      className="panel form-grid"
                      onSubmit={async (event) => {
                        event.preventDefault();
                        if (preset.is_builtin) {
                          return;
                        }
                        setPresetBusy(preset.id);
                        setPresetError(null);
                        setPresetMessage(null);
                        try {
                          const configJson = draft.configText.trim() ? JSON.parse(draft.configText) : {};
                          await updateAddonPreset(moduleItem.module_id, preset.id, {
                            name: draft.name,
                            description: draft.description || null,
                            config_json: configJson,
                          });
                          await loadPresets(moduleItem);
                          setPresetMessage(`Saved preset ${draft.name}.`);
                        } catch (nextError) {
                          setPresetError(nextError instanceof Error ? nextError.message : "Unable to save preset.");
                        } finally {
                          setPresetBusy(null);
                        }
                      }}
                    >
                      <div className="row-between">
                        <div>
                          <p className="eyebrow">{preset.is_builtin ? "Built-in preset" : "Custom preset"}</p>
                          <h3>{preset.name}</h3>
                        </div>
                        <div className="chip-row">
                          <span className="chip">v{preset.version}</span>
                          {preset.is_builtin ? <span className="chip">read-only</span> : null}
                        </div>
                      </div>
                      <label className="field">
                        <span>Name</span>
                        <input
                          value={draft.name}
                          onChange={(event) =>
                            setPresetDrafts((current) => ({
                              ...current,
                              [preset.id]: { ...draft, name: event.target.value },
                            }))
                          }
                          disabled={preset.is_builtin}
                        />
                      </label>
                      <label className="field">
                        <span>Description</span>
                        <input
                          value={draft.description}
                          onChange={(event) =>
                            setPresetDrafts((current) => ({
                              ...current,
                              [preset.id]: { ...draft, description: event.target.value },
                            }))
                          }
                          disabled={preset.is_builtin}
                        />
                      </label>
                      <label className="field">
                        <span>Config JSON</span>
                        <textarea
                          value={draft.configText}
                          onChange={(event) =>
                            setPresetDrafts((current) => ({
                              ...current,
                              [preset.id]: { ...draft, configText: event.target.value },
                            }))
                          }
                          rows={8}
                          disabled={preset.is_builtin}
                        />
                      </label>
                      {!preset.is_builtin ? (
                        <button className="button small-button" type="submit" disabled={presetBusy === preset.id}>
                          {presetBusy === preset.id ? "Saving..." : "Save Preset"}
                        </button>
                      ) : null}
                    </form>
                  );
                })
              ) : (
                <p className="subdued">No presets discovered for this addon yet.</p>
              )}
            </section>
          ) : null}
        </>
      ) : null}
    </AppShell>
  );
}
