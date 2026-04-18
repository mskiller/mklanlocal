"use client";

import { useState } from "react";

import { clearDoneScanJobs } from "@/lib/api";

export function ScanJobsControls({
  onCleared,
  terminalCount = 0,
}: {
  onCleared?: (deletedCount: number) => void | Promise<void>;
  terminalCount?: number;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleClearDone = async () => {
    if (!window.confirm("Remove all completed, failed, and cancelled jobs from the list?")) return;
    setBusy(true);
    setError(null);
    setSuccess(false);
    try {
      const payload = await clearDoneScanJobs();
      setSuccess(true);
      setTimeout(() => setSuccess(false), 2500);
      await Promise.resolve(onCleared?.(payload.deleted_count));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to clear jobs.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
      <button
        type="button"
        className="button ghost-button small-button"
        onClick={handleClearDone}
        disabled={busy || terminalCount === 0}
      >
        {busy ? "Clearing…" : `Clear Finished Jobs${terminalCount ? ` (${terminalCount})` : ""}`}
      </button>
      {success && <span className="subdued" style={{ fontSize: "0.85rem" }}>Cleared.</span>}
      {error && <span style={{ fontSize: "0.85rem", color: "var(--error, #e05)" }}>{error}</span>}
    </div>
  );
}
