"use client";

import Link from "next/link";

export function CompareSelectionTray({
  selectionMode,
  selectedCount,
  compareHref,
  onToggleSelectionMode,
  onClearSelection,
  hint,
  canAddToCollection = false,
  onAddToCollection,
}: {
  selectionMode: boolean;
  selectedCount: number;
  compareHref: string | null;
  onToggleSelectionMode: () => void;
  onClearSelection: () => void;
  hint: string;
  canAddToCollection?: boolean;
  onAddToCollection?: () => void;
}) {
  return (
    <section className="compare-tray panel">
      <div>
        <p className="eyebrow">Compare Tray</p>
        <h2>{selectedCount} selected</h2>
        <p className="subdued">{hint}</p>
      </div>
      <div className="card-actions">
        <button className={`button small-button ${selectionMode ? "" : "ghost-button"}`} type="button" onClick={onToggleSelectionMode}>
          {selectionMode ? "Exit Selection Mode" : "Select for Compare"}
        </button>
        <button className="button ghost-button small-button" type="button" onClick={onClearSelection} disabled={!selectedCount}>
          Clear Selection
        </button>
        {canAddToCollection && onAddToCollection ? (
          <button className="button subtle-button small-button" type="button" onClick={onAddToCollection} disabled={!selectedCount}>
            Add Selected to Collection
          </button>
        ) : null}
        {compareHref ? (
          <Link href={compareHref} className="button small-button">
            Compare Selected
          </Link>
        ) : null}
      </div>
    </section>
  );
}
