"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { useModuleRegistry } from "@/components/module-registry-provider";
import { fetchAdminModule, fetchCharacterCards, updateAdminModule } from "@/lib/api";
import { PlatformModule } from "@/lib/types";

export default function AdminCharactersModulePage() {
  const { user } = useAuth();
  const { refresh: refreshRegistry } = useModuleRegistry();
  const [moduleItem, setModuleItem] = useState<PlatformModule | null>(null);
  const [busy, setBusy] = useState(false);
  const [cardCount, setCardCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = async () => {
    try {
      const nextModule = await fetchAdminModule("characters");
      setModuleItem(nextModule);
      if (nextModule.enabled && nextModule.status === "active") {
        const nextCards = await fetchCharacterCards({ page: 1, page_size: 1 });
        setCardCount(nextCards.total);
      } else {
        setCardCount(null);
      }
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load characters module.");
    }
  };

  useEffect(() => {
    if (user?.capabilities.can_view_admin) {
      void load();
    }
  }, [user?.capabilities.can_view_admin]);

  if (user && !user.capabilities.can_view_admin) {
    return (
      <AppShell title="Characters Module" description="Module health and registry overview.">
        <section className="panel empty-state">
          <h2>Admin only</h2>
          <p className="subdued">This page is only available to admin users.</p>
        </section>
      </AppShell>
    );
  }

  return (
    <AppShell
      title={moduleItem?.name ?? "Characters Module"}
      description="Built-in SillyTavern PNG card extraction, browsing, and write-back."
      actions={
        <div className="page-actions">
          <Link href="/admin/modules" className="button subtle-button small-button">All Modules</Link>
          {moduleItem?.enabled && moduleItem.status === "active" ? (
            <Link href="/characters" className="button ghost-button small-button">Open Characters</Link>
          ) : null}
        </div>
      }
    >
      {error ? <section className="panel empty-state">{error}</section> : null}
      {message ? <section className="panel empty-state">{message}</section> : null}

      {moduleItem ? (
        <>
          <section className="stats-grid">
            <article className="panel">
              <p className="eyebrow">Status</p>
              <p className="stat-card-value">{moduleItem.status}</p>
              <p className="subdued">{moduleItem.enabled ? "Enabled in registry" : "Disabled in registry"}</p>
            </article>
            <article className="panel">
              <p className="eyebrow">Cards Indexed</p>
              <p className="stat-card-value">{cardCount ?? "—"}</p>
              <p className="subdued">Detected PNG character cards visible through current scope</p>
            </article>
            <article className="panel">
              <p className="eyebrow">Module Kind</p>
              <p className="stat-card-value">{moduleItem.kind}</p>
              <p className="subdued">Loaded through the platform registry</p>
            </article>
          </section>

          <section className="two-column">
            <article className="panel stack">
              <div>
                <p className="eyebrow">Overview</p>
                <h2>Supported format</h2>
              </div>
              <p className="subdued">This built-in module extracts and edits PNG-embedded SillyTavern character cards using explicit <code>ccv3</code> and compatibility <code>chara</code> text chunks.</p>
              <div className="chip-row">
                <span className="chip">PNG only</span>
                <span className="chip">SillyTavern ccv3</span>
                <span className="chip">Legacy chara write-back</span>
              </div>
              {moduleItem.error ? <p className="subdued">{moduleItem.error}</p> : null}
            </article>

            <article className="panel stack">
              <div>
                <p className="eyebrow">Controls</p>
                <h2>Module availability</h2>
              </div>
              <p className="subdued">Disable the module to hide the library and API surface without removing the indexed character-card records from the database.</p>
              <button
                type="button"
                className="button small-button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  setMessage(null);
                  try {
                    const updated = await updateAdminModule("characters", { enabled: !moduleItem.enabled });
                    setModuleItem(updated);
                    await refreshRegistry();
                    setMessage(`Characters ${moduleItem.enabled ? "disabled" : "enabled"}.`);
                    if (updated.enabled && updated.status === "active") {
                      const nextCards = await fetchCharacterCards({ page: 1, page_size: 1 });
                      setCardCount(nextCards.total);
                    } else {
                      setCardCount(null);
                    }
                  } catch (nextError) {
                    setError(nextError instanceof Error ? nextError.message : "Unable to update module.");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {busy ? "Saving..." : moduleItem.enabled ? "Disable Module" : "Enable Module"}
              </button>
            </article>
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
