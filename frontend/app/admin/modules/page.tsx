"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { useModuleRegistry } from "@/components/module-registry-provider";
import { fetchAdminModules, rescanAdminModules, updateAdminModule } from "@/lib/api";
import { PlatformModule } from "@/lib/types";

function sortModules(left: PlatformModule, right: PlatformModule) {
  const leftOrder = left.admin_nav_label ? left.admin_nav_order : left.nav_order;
  const rightOrder = right.admin_nav_label ? right.admin_nav_order : right.nav_order;
  return leftOrder - rightOrder || left.name.localeCompare(right.name);
}

function ModuleCard({
  moduleItem,
  busy,
  onToggle,
}: {
  moduleItem: PlatformModule;
  busy: string | null;
  onToggle: (moduleItem: PlatformModule) => Promise<void>;
}) {
  return (
    <article key={moduleItem.module_id} className="panel stack">
      <div className="row-between">
        <div>
          <h3>{moduleItem.name}</h3>
          <p className="subdued">{moduleItem.module_id} · {moduleItem.kind} · v{moduleItem.version}</p>
        </div>
        <div className="chip-row">
          <span className="chip">{moduleItem.status}</span>
          <span className="chip">{moduleItem.enabled ? "enabled" : "disabled"}</span>
        </div>
      </div>
      {moduleItem.description ? <p className="subdued">{moduleItem.description}</p> : null}
      {moduleItem.error ? <p className="subdued">{moduleItem.error}</p> : null}
      <div className="chip-row">
        {moduleItem.dependencies.map((dependency) => (
          <span key={`${moduleItem.module_id}-dep-${dependency}`} className="chip">depends on {dependency}</span>
        ))}
        {moduleItem.permissions.map((permission) => (
          <span key={`${moduleItem.module_id}-perm-${permission}`} className="chip">{permission}</span>
        ))}
      </div>
      <div className="card-actions">
        <Link href={`/admin/modules/${moduleItem.module_id}`} className="button small-button">
          Configure
        </Link>
        {moduleItem.user_mount ? (
          <Link href={moduleItem.user_mount} className="button ghost-button small-button">
            Open User Surface
          </Link>
        ) : null}
        <button
          type="button"
          className="button ghost-button small-button"
          disabled={busy === moduleItem.module_id}
          onClick={() => void onToggle(moduleItem)}
        >
          {busy === moduleItem.module_id ? "Saving..." : moduleItem.enabled ? "Disable" : "Enable"}
        </button>
      </div>
    </article>
  );
}

function ModuleSection({
  title,
  eyebrow,
  description,
  modules,
  busy,
  onToggle,
  emptyMessage,
}: {
  title: string;
  eyebrow: string;
  description: string;
  modules: PlatformModule[];
  busy: string | null;
  onToggle: (moduleItem: PlatformModule) => Promise<void>;
  emptyMessage: string;
}) {
  return (
    <section className="panel stack">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
        <p className="subdued">{description}</p>
      </div>
      <div className="list-stack">
        {modules.length ? (
          modules.map((moduleItem) => (
            <ModuleCard key={moduleItem.module_id} moduleItem={moduleItem} busy={busy} onToggle={onToggle} />
          ))
        ) : (
          <article className="panel empty-state">
            <p className="subdued">{emptyMessage}</p>
          </article>
        )}
      </div>
    </section>
  );
}

export default function AdminModulesPage() {
  const { user } = useAuth();
  const { refresh: refreshRegistry } = useModuleRegistry();
  const [modules, setModules] = useState<PlatformModule[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = async () => {
    try {
      const nextModules = await fetchAdminModules();
      setModules(nextModules.sort(sortModules));
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load modules.");
    }
  };

  useEffect(() => {
    if (user?.capabilities.can_view_admin) {
      void load();
    }
  }, [user?.capabilities.can_view_admin]);

  if (user && !user.capabilities.can_view_admin) {
    return (
      <AppShell title="Modules" description="Installed platform modules and addon health.">
        <section className="panel empty-state">
          <h2>Admin only</h2>
          <p className="subdued">This page is only available to admin users.</p>
        </section>
      </AppShell>
    );
  }

  const activeCount = modules.filter((item) => item.status === "active").length;
  const disabledCount = modules.filter((item) => item.status === "disabled").length;
  const unhealthyCount = modules.filter((item) => !["active", "disabled"].includes(item.status)).length;
  const builtinModules = modules.filter((item) => item.kind === "builtin").sort(sortModules);
  const addonModules = modules.filter((item) => item.kind !== "builtin").sort(sortModules);

  const toggleModule = async (moduleItem: PlatformModule) => {
    setBusy(moduleItem.module_id);
    setError(null);
    setMessage(null);
    try {
      await updateAdminModule(moduleItem.module_id, { enabled: !moduleItem.enabled });
      await load();
      await refreshRegistry();
      setMessage(`${moduleItem.name} ${moduleItem.enabled ? "disabled" : "enabled"}.`);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to update module.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <AppShell
      title="Platform Modules"
      description="Enable, disable, and inspect built-in modules plus installed addons."
      actions={
        <div className="page-actions">
          <button
            type="button"
            className="button ghost-button small-button"
            disabled={busy === "rescan"}
            onClick={async () => {
              setBusy("rescan");
              setError(null);
              setMessage(null);
              try {
                const nextModules = await rescanAdminModules();
                setModules(nextModules.sort(sortModules));
                await refreshRegistry();
                setMessage("Addon manifest registry refreshed.");
              } catch (nextError) {
                setError(nextError instanceof Error ? nextError.message : "Unable to rescan modules.");
              } finally {
                setBusy(null);
              }
            }}
          >
            {busy === "rescan" ? "Refreshing..." : "Rescan Addons"}
          </button>
          <Link href="/admin" className="button subtle-button small-button">Admin Center</Link>
        </div>
      }
    >
      {error ? <section className="panel empty-state">{error}</section> : null}
      {message ? <section className="panel empty-state">{message}</section> : null}

      <section className="stats-grid">
        <article className="panel">
          <p className="eyebrow">Installed</p>
          <p className="stat-card-value">{modules.length}</p>
          <p className="subdued">Built-ins and discovered addons</p>
        </article>
        <article className="panel">
          <p className="eyebrow">Active</p>
          <p className="stat-card-value">{activeCount}</p>
          <p className="subdued">Available to the app right now</p>
        </article>
        <article className="panel">
          <p className="eyebrow">Disabled</p>
          <p className="stat-card-value">{disabledCount}</p>
          <p className="subdued">Installed but turned off</p>
        </article>
        <article className="panel">
          <p className="eyebrow">Needs Attention</p>
          <p className="stat-card-value">{unhealthyCount}</p>
          <p className="subdued">Blocked, pending, or error states</p>
        </article>
      </section>

      <ModuleSection
        title="Built-in Modules"
        eyebrow="Core Extensions"
        description="First-party modules that now plug into the same registry as addons."
        modules={builtinModules}
        busy={busy}
        onToggle={toggleModule}
        emptyMessage="No built-in modules are currently registered."
      />

      <ModuleSection
        title="Installed Addons"
        eyebrow="Addon Registry"
        description="External or vendored modules discovered from the addon lock file."
        modules={addonModules}
        busy={busy}
        onToggle={toggleModule}
        emptyMessage="No addons are currently installed."
      />
    </AppShell>
  );
}
