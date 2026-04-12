"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import {
  cancelScanJob,
  createAdminUser,
  createCollection,
  createSource,
  deleteSource,
  fetchAdminSettings,
  fetchAdminUsers,
  fetchAuditLogs,
  fetchCollections,
  fetchScanJobs,
  fetchSources,
  rebuildTagSimilarity,
  resetAdminUserPassword,
  resetApplicationData,
  triggerScan,
  updateAdminSettings,
  updateAdminUser,
} from "@/lib/api";
import { formatDate } from "@/lib/asset-metadata";
import { AdminSettings, AuditLogEntry, CollectionSummary, ScanJob, Source, UserSummary, UserRole, UserStatus } from "@/lib/types";

function findActiveJob(source: Source, jobs: ScanJob[]) {
  return jobs.find((job) => job.source_id === source.id && (job.status === "queued" || job.status === "running"));
}

export default function AdminPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [jobs, setJobs] = useState<ScanJob[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<UserRole>("guest");
  const [sourceName, setSourceName] = useState("New Source");
  const [sourceRootPath, setSourceRootPath] = useState("/data/sources/sample");
  const [collectionName, setCollectionName] = useState("");
  const [collectionDescription, setCollectionDescription] = useState("");
  const [drafts, setDrafts] = useState<Record<string, { username: string; role: UserRole; status: UserStatus }>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = async () => {
    try {
      const [nextUsers, nextSources, nextJobs, nextAuditLogs, nextCollections, nextSettings] = await Promise.all([
        fetchAdminUsers(),
        fetchSources(),
        fetchScanJobs(),
        fetchAuditLogs(40),
        fetchCollections(),
        fetchAdminSettings(),
      ]);
      setUsers(nextUsers);
      setSources(nextSources);
      setJobs(nextJobs);
      setAuditLogs(nextAuditLogs);
      setCollections(nextCollections);
      setSettings(nextSettings);
      setDrafts(
        Object.fromEntries(
          nextUsers.map((entry) => [entry.id, { username: entry.username, role: entry.role, status: entry.status }])
        )
      );
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load admin center.");
    }
  };

  useEffect(() => {
    if (user?.capabilities.can_view_admin) {
      void load();
    }
  }, [user?.capabilities.can_view_admin]);

  const activeJobs = useMemo(
    () => jobs.filter((job) => job.status === "queued" || job.status === "running"),
    [jobs]
  );

  if (user && !user.capabilities.can_view_admin) {
    return (
      <AppShell title="Admin" description="Administrative controls for users, sources, scans, and maintenance.">
        <section className="panel empty-state">
          <h2>Admin only</h2>
          <p className="subdued">This page is only available to admin users.</p>
        </section>
      </AppShell>
    );
  }

  const setDraft = (id: string, patch: Partial<{ username: string; role: UserRole; status: UserStatus }>) => {
    setDrafts((current) => ({
      ...current,
      [id]: { ...current[id], ...patch },
    }));
  };

  return (
    <AppShell title="Admin Center" description="Manage users, sources, scans, maintenance, and audit activity in one place.">
      {error ? <section className="panel empty-state">{error}</section> : null}
      {message ? <section className="panel empty-state">{message}</section> : null}

      <section className="stats-grid">
        <article className="panel">
          <p className="eyebrow">Users</p>
          <p className="stat-card-value">{users.length}</p>
          <p className="subdued">Admin and guest accounts</p>
        </article>
        <article className="panel">
          <p className="eyebrow">Active Scans</p>
          <p className="stat-card-value">{activeJobs.length}</p>
          <p className="subdued">Queued or running jobs</p>
        </article>
        <article className="panel">
          <p className="eyebrow">Sources</p>
          <p className="stat-card-value">{sources.length}</p>
          <p className="subdued">Approved browse roots</p>
        </article>
      </section>

      <section className="two-column">
        <form
          className="panel form-grid"
          onSubmit={async (event: FormEvent) => {
            event.preventDefault();
            setBusy("create-user");
            setError(null);
            setMessage(null);
            try {
              await createAdminUser({ username: newUsername, password: newPassword, role: newRole });
              setNewUsername("");
              setNewPassword("");
              setNewRole("guest");
              setMessage("User created.");
              await load();
            } catch (nextError) {
              setError(nextError instanceof Error ? nextError.message : "Unable to create user.");
            } finally {
              setBusy(null);
            }
          }}
        >
          <div>
            <p className="eyebrow">User Management</p>
            <h2>Create user</h2>
          </div>
          <label className="field">
            <span>Username</span>
            <input value={newUsername} onChange={(event) => setNewUsername(event.target.value)} />
          </label>
          <label className="field">
            <span>Password</span>
            <input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
          </label>
          <label className="field">
            <span>Role</span>
            <select value={newRole} onChange={(event) => setNewRole(event.target.value as UserRole)}>
              <option value="guest">Guest</option>
              <option value="curator">Curator</option>
              <option value="admin">Admin</option>
            </select>
          </label>
          <button className="button" type="submit" disabled={busy === "create-user"}>
            {busy === "create-user" ? "Creating..." : "Create User"}
          </button>
        </form>

        <form
          className="panel form-grid"
          onSubmit={async (event: FormEvent) => {
            event.preventDefault();
            setBusy("create-source");
            setError(null);
            setMessage(null);
            try {
              await createSource({ name: sourceName, root_path: sourceRootPath, type: "mounted_fs" });
              setMessage("Source added.");
              await load();
            } catch (nextError) {
              setError(nextError instanceof Error ? nextError.message : "Unable to create source.");
            } finally {
              setBusy(null);
            }
          }}
        >
          <div>
            <p className="eyebrow">Source Management</p>
            <h2>Add approved root</h2>
          </div>
          <label className="field">
            <span>Name</span>
            <input value={sourceName} onChange={(event) => setSourceName(event.target.value)} />
          </label>
          <label className="field">
            <span>Container-visible root path</span>
            <input value={sourceRootPath} onChange={(event) => setSourceRootPath(event.target.value)} />
          </label>
          <button className="button" type="submit" disabled={busy === "create-source"}>
            {busy === "create-source" ? "Saving..." : "Save Source"}
          </button>
        </form>
      </section>

      <section className="two-column">
        <form
          className="panel form-grid"
          onSubmit={async (event: FormEvent) => {
            event.preventDefault();
            setBusy("create-collection");
            setError(null);
            setMessage(null);
            try {
              await createCollection({ name: collectionName, description: collectionDescription });
              setCollectionName("");
              setCollectionDescription("");
              setMessage("Collection created.");
              await load();
            } catch (nextError) {
              setError(nextError instanceof Error ? nextError.message : "Unable to create collection.");
            } finally {
              setBusy(null);
            }
          }}
        >
          <div>
            <p className="eyebrow">Collections</p>
            <h2>Create shared collection</h2>
          </div>
          <label className="field">
            <span>Name</span>
            <input value={collectionName} onChange={(event) => setCollectionName(event.target.value)} />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea value={collectionDescription} onChange={(event) => setCollectionDescription(event.target.value)} rows={3} />
          </label>
          <button className="button" type="submit" disabled={busy === "create-collection"}>
            {busy === "create-collection" ? "Creating..." : "Create Collection"}
          </button>
        </form>

        <section className="panel stack">
          <div>
            <p className="eyebrow">Tag Similarity</p>
            <h2>Global settings</h2>
          </div>
          <label className="field">
            <span>Threshold percent</span>
            <input
              type="number"
              min={1}
              max={100}
              value={settings?.tag_similarity_threshold_percent ?? 75}
              onChange={(event) =>
                setSettings((current) => ({
                  ...(current as AdminSettings),
                  tag_similarity_threshold_percent: Number(event.target.value),
                } as AdminSettings))
              }
            />
          </label>
          <div className="card-actions">
            <button
              className="button small-button"
              type="button"
              disabled={!settings || busy === "save-settings"}
              onClick={async () => {
                if (!settings) {
                  return;
                }
                setBusy("save-settings");
                setError(null);
                setMessage(null);
                try {
                  const updated = await updateAdminSettings(settings);
                  setSettings(updated);
                  setMessage("Settings updated.");
                } catch (nextError) {
                  setError(nextError instanceof Error ? nextError.message : "Unable to update settings.");
                } finally {
                  setBusy(null);
                }
              }}
            >
              Save Settings
            </button>
            <button
              className="button ghost-button small-button"
              type="button"
              disabled={busy === "rebuild-tags"}
              onClick={async () => {
                setBusy("rebuild-tags");
                setError(null);
                setMessage(null);
                try {
                  const result = await rebuildTagSimilarity();
                  setMessage(`Rebuilt tag similarity for ${result.rebuilt_assets} assets and ${result.rebuilt_links} links.`);
                } catch (nextError) {
                  setError(nextError instanceof Error ? nextError.message : "Unable to rebuild tag similarity.");
                } finally {
                  setBusy(null);
                }
              }}
            >
              Rebuild Tag Similarity
            </button>
          </div>
          <div className="chip-row">
            <span className="chip">{collections.length} collections</span>
            {settings ? <span className="chip">{settings.tag_similarity_threshold_percent}% threshold</span> : null}
          </div>
        </section>
      </section>

      <section className="panel stack">
        <div>
          <p className="eyebrow">Users</p>
          <h2>Accounts and permissions</h2>
        </div>
        <div className="list-stack">
          {users.map((entry) => {
            const draft = drafts[entry.id] ?? { username: entry.username, role: entry.role, status: entry.status };
            return (
              <article key={entry.id} className="panel stack">
                <div className="row-between">
                  <div>
                    <h3>{entry.username}</h3>
                    <p className="subdued">Created {formatDate(entry.created_at)}</p>
                  </div>
                  <span className="pill">{entry.role}</span>
                </div>
                <div className="field-grid admin-user-grid">
                  <label className="field">
                    <span>Username</span>
                    <input value={draft.username} onChange={(event) => setDraft(entry.id, { username: event.target.value })} />
                  </label>
                  <label className="field">
                    <span>Role</span>
                    <select value={draft.role} onChange={(event) => setDraft(entry.id, { role: event.target.value as UserRole })}>
                      <option value="guest">Guest</option>
                      <option value="curator">Curator</option>
                      <option value="admin">Admin</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>Status</span>
                    <select value={draft.status} onChange={(event) => setDraft(entry.id, { status: event.target.value as UserStatus })}>
                      <option value="active">Active</option>
                      <option value="disabled">Disabled</option>
                    </select>
                  </label>
                </div>
                <div className="card-actions">
                  <button
                    className="button small-button"
                    type="button"
                    onClick={async () => {
                      setBusy(`save-user-${entry.id}`);
                      setError(null);
                      setMessage(null);
                      try {
                        await updateAdminUser(entry.id, draft);
                        setMessage(`Updated ${draft.username}.`);
                        await load();
                      } catch (nextError) {
                        setError(nextError instanceof Error ? nextError.message : "Unable to update user.");
                      } finally {
                        setBusy(null);
                      }
                    }}
                    disabled={busy === `save-user-${entry.id}`}
                  >
                    Save Changes
                  </button>
                  <button
                    className="button ghost-button small-button"
                    type="button"
                    onClick={async () => {
                      const password = window.prompt(`Set a new password for ${entry.username}`);
                      if (!password) {
                        return;
                      }
                      setBusy(`password-user-${entry.id}`);
                      setError(null);
                      setMessage(null);
                      try {
                        await resetAdminUserPassword(entry.id, password);
                        setMessage(`Password reset for ${entry.username}.`);
                      } catch (nextError) {
                        setError(nextError instanceof Error ? nextError.message : "Unable to reset password.");
                      } finally {
                        setBusy(null);
                      }
                    }}
                    disabled={busy === `password-user-${entry.id}`}
                  >
                    Set Password
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="panel stack">
        <div className="row-between">
          <div>
            <p className="eyebrow">Sources</p>
            <h2>Scan and browse roots</h2>
          </div>
          <Link href="/sources" className="button subtle-button small-button">
            Open Browse Hub
          </Link>
        </div>
        <div className="list-stack">
          {sources.map((source) => {
            const activeJob = findActiveJob(source, jobs);
            return (
              <article key={source.id} className="panel stack">
                <div className="row-between">
                  <div>
                    <h3>{source.name}</h3>
                    <p className="subdued">{source.root_path ?? source.display_root_path}</p>
                  </div>
                  <span className="pill">{source.status}</span>
                </div>
                <div className="card-actions">
                  <Link href={`/sources/${source.id}`} className="button subtle-button small-button">
                    Browse
                  </Link>
                  {activeJob ? (
                    <>
                      <Link href={`/scan-jobs/${activeJob.id}`} className="button ghost-button small-button">
                        View Scan
                      </Link>
                      <button
                        className="button ghost-button small-button"
                        type="button"
                        onClick={async () => {
                          setBusy(`cancel-source-${source.id}`);
                          setError(null);
                          setMessage(null);
                          try {
                            await cancelScanJob(activeJob.id);
                            setMessage(`Cancelled scan for ${source.name}.`);
                            await load();
                          } catch (nextError) {
                            setError(nextError instanceof Error ? nextError.message : "Unable to cancel scan.");
                          } finally {
                            setBusy(null);
                          }
                        }}
                        disabled={busy === `cancel-source-${source.id}`}
                      >
                        Cancel Scan
                      </button>
                    </>
                  ) : (
                    <button
                      className="button small-button"
                      type="button"
                      onClick={async () => {
                        setBusy(`scan-source-${source.id}`);
                        setError(null);
                        setMessage(null);
                        try {
                          await triggerScan(source.id);
                          setMessage(`Scan queued for ${source.name}.`);
                          await load();
                        } catch (nextError) {
                          setError(nextError instanceof Error ? nextError.message : "Unable to trigger scan.");
                        } finally {
                          setBusy(null);
                        }
                      }}
                      disabled={busy === `scan-source-${source.id}`}
                    >
                      Scan / Refresh Metadata
                    </button>
                  )}
                  <button
                    className="button ghost-button small-button"
                    type="button"
                    onClick={async () => {
                      if (!window.confirm(`Delete source ${source.name}?`)) {
                        return;
                      }
                      setBusy(`delete-source-${source.id}`);
                      setError(null);
                      setMessage(null);
                      try {
                        await deleteSource(source.id);
                        setMessage(`Deleted ${source.name}.`);
                        await load();
                      } catch (nextError) {
                        setError(nextError instanceof Error ? nextError.message : "Unable to delete source.");
                      } finally {
                        setBusy(null);
                      }
                    }}
                    disabled={busy === `delete-source-${source.id}` || Boolean(activeJob)}
                  >
                    Delete
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="two-column">
        <section className="panel stack">
          <div>
            <p className="eyebrow">Maintenance</p>
            <h2>Reset and re-index</h2>
          </div>
          <div className="card-actions">
            <button
              className="button ghost-button small-button"
              type="button"
              disabled={Boolean(busy)}
              onClick={async () => {
                if (!window.confirm("Clear indexed assets, tags, previews, and scan history while keeping approved sources?")) {
                  return;
                }
                setBusy("reset-index");
                setError(null);
                setMessage(null);
                try {
                  const result = await resetApplicationData("index");
                  setMessage(`Cleared ${result.deleted_assets} assets and ${result.deleted_scan_jobs} scan jobs.`);
                  await load();
                } catch (nextError) {
                  setError(nextError instanceof Error ? nextError.message : "Unable to clear indexed data.");
                } finally {
                  setBusy(null);
                }
              }}
            >
              Clear Indexed Data
            </button>
            <button
              className="button small-button"
              type="button"
              disabled={Boolean(busy)}
              onClick={async () => {
                if (!window.confirm("Factory reset the app by deleting sources, indexed assets, previews, scan history, and audit logs?")) {
                  return;
                }
                setBusy("reset-all");
                setError(null);
                setMessage(null);
                try {
                  const result = await resetApplicationData("all");
                  setMessage(`Factory reset complete. Deleted ${result.deleted_sources} sources and ${result.deleted_assets} assets.`);
                  await load();
                } catch (nextError) {
                  setError(nextError instanceof Error ? nextError.message : "Unable to factory reset the app.");
                } finally {
                  setBusy(null);
                }
              }}
            >
              Factory Reset
            </button>
          </div>
        </section>

        <section className="panel stack">
          <div>
            <p className="eyebrow">Recent Audit Activity</p>
            <h2>Latest actions</h2>
          </div>
          <div className="list-stack compact-list-stack">
            {auditLogs.map((entry) => (
              <article key={entry.id} className="metadata-row">
                <strong>{entry.action}</strong>
                <p className="subdued">{entry.actor} · {formatDate(entry.created_at)}</p>
                <p className="subdued">{entry.resource_type}</p>
              </article>
            ))}
          </div>
        </section>
      </section>
    </AppShell>
  );
}
