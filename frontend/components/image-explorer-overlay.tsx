"use client";

import Link from "next/link";
import { ReactNode, useEffect, useRef, useState } from "react";

import { TagFilterChip } from "@/components/tag-filter-chip";
import { ZoomableImageViewer, ZoomableImageViewerHandle } from "@/components/zoomable-image-viewer";

export interface ExplorerMetadataEntry {
  label: string;
  value: string;
}

export interface ExplorerItem {
  key: string;
  title: string;
  subtitle?: string | null;
  promptExcerpt?: string | null;
  promptTags: string[];
  statusBadge?: string | null;
  previewSrc: string | null;
  contentSrc: string | null;
  deepzoomUrl?: string | null;
  detailHref?: string | null;
  similarHref?: string | null;
  sourceContext?: string | null;
  metadataSummary?: ExplorerMetadataEntry[];
}

export function ImageExplorerOverlay({
  open,
  items,
  activeIndex,
  onClose,
  onActiveIndexChange,
  renderActions,
}: {
  open: boolean;
  items: ExplorerItem[];
  activeIndex: number;
  onClose: () => void;
  onActiveIndexChange: (next: number) => void;
  renderActions?: (item: ExplorerItem) => ReactNode;
}) {
  const viewerRef = useRef<ZoomableImageViewerHandle | null>(null);
  const currentItem = items[activeIndex] ?? null;
  const touchRef = useRef<{ x: number; y: number } | null>(null);
  const [metaPanelOpen, setMetaPanelOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    setMetaPanelOpen(false);
  }, [open, activeIndex]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        onActiveIndexChange(Math.max(0, activeIndex - 1));
        return;
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        onActiveIndexChange(Math.min(items.length - 1, activeIndex + 1));
        return;
      }
      if (event.key === "0") {
        event.preventDefault();
        viewerRef.current?.fit();
        return;
      }
      if (event.key === "1") {
        event.preventDefault();
        viewerRef.current?.actualSize();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeIndex, items.length, onActiveIndexChange, onClose, open]);

  if (!open || !currentItem) {
    return null;
  }

  return (
    <>
      <button type="button" className="explorer-scrim" aria-label="Close explorer" onClick={onClose} />
      <section className="explorer-overlay">
        <div className="explorer-header">
          <div className="stack">
            <p className="eyebrow">Explorer</p>
            <h2>{currentItem.title}</h2>
            {currentItem.subtitle ? <p className="subdued">{currentItem.subtitle}</p> : null}
          </div>
          <div className="card-actions explorer-header-actions">
            <button type="button" className="button ghost-button small-button" onClick={() => onActiveIndexChange(Math.max(0, activeIndex - 1))} disabled={activeIndex === 0}>
              Previous
            </button>
            <button
              type="button"
              className="button ghost-button small-button"
              onClick={() => onActiveIndexChange(Math.min(items.length - 1, activeIndex + 1))}
              disabled={activeIndex >= items.length - 1}
            >
              Next
            </button>
            <button type="button" className="button ghost-button small-button" onClick={() => document.documentElement.requestFullscreen?.()}>
              Fullscreen
            </button>
            <button type="button" className="button ghost-button small-button explorer-meta-toggle" onClick={() => setMetaPanelOpen((v) => !v)}>
              {metaPanelOpen ? "Hide Info" : "Info"}
            </button>
            <button type="button" className="button small-button" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
        <div
          className="explorer-body"
          onTouchStart={(e) => {
            touchRef.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
          }}
          onTouchEnd={(e) => {
            if (!touchRef.current) return;
            const dx = e.changedTouches[0].clientX - touchRef.current.x;
            const dy = e.changedTouches[0].clientY - touchRef.current.y;
            touchRef.current = null;
            if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 50) {
              if (dx < 0) {
                onActiveIndexChange(Math.min(items.length - 1, activeIndex + 1));
              } else {
                onActiveIndexChange(Math.max(0, activeIndex - 1));
              }
            } else if (dy < -60 && Math.abs(dy) > Math.abs(dx)) {
              setMetaPanelOpen(true);
            } else if (dy > 60 && Math.abs(dy) > Math.abs(dx)) {
              setMetaPanelOpen(false);
            }
          }}
          onDoubleClick={(e) => {
            (viewerRef.current as any)?.zoomToPoint?.(e.clientX, e.clientY, 2.5);
          }}
        >
          <div className="panel explorer-viewer-panel">
            {currentItem.contentSrc ? (
              <ZoomableImageViewer
                ref={viewerRef}
                previewSrc={currentItem.previewSrc}
                contentSrc={currentItem.contentSrc}
                deepzoomUrl={currentItem.deepzoomUrl}
                alt={currentItem.title}
                defaultMode="auto"
              />
            ) : (
              <div className="explorer-viewer-empty">No image available.</div>
            )}
          </div>
          <aside className={`panel stack explorer-inspector ${metaPanelOpen ? "explorer-inspector-open" : ""}`}>
            <div className="row-between">
              <div>
                <p className="eyebrow">Inspector</p>
                <h3>{currentItem.title}</h3>
              </div>
              {currentItem.statusBadge ? <span className="pill">{currentItem.statusBadge}</span> : null}
            </div>
            {currentItem.sourceContext ? <p className="subdued">{currentItem.sourceContext}</p> : null}
            {currentItem.promptExcerpt ? (
              <div className="stack">
                <strong>Prompt</strong>
                <p className="subdued">{currentItem.promptExcerpt}</p>
              </div>
            ) : null}
            {currentItem.promptTags.length ? (
              <div className="stack">
                <strong>Tags</strong>
                <div className="chip-row">
                  {currentItem.promptTags.map((tag) => (
                    <TagFilterChip key={`${currentItem.key}-${tag}`} tag={tag} prompt className="chip chip-prompt buttonless" />
                  ))}
                </div>
              </div>
            ) : null}
            {currentItem.metadataSummary?.length ? (
              <div className="metadata-grid explorer-metadata-grid">
                {currentItem.metadataSummary.map((entry) => (
                  <div key={`${currentItem.key}-${entry.label}`} className="metadata-row">
                    <strong>{entry.label}</strong>
                    <div className="subdued">{entry.value}</div>
                  </div>
                ))}
              </div>
            ) : null}
            {renderActions ? <div className="stack">{renderActions(currentItem)}</div> : null}
            <div className="card-actions">
              {currentItem.detailHref ? (
                <Link href={currentItem.detailHref} className="button subtle-button small-button">
                  Open Detail
                </Link>
              ) : null}
              {currentItem.similarHref ? (
                <Link href={currentItem.similarHref} className="button ghost-button small-button">
                  Open Similar
                </Link>
              ) : null}
            </div>
          </aside>
        </div>
        <div className="explorer-filmstrip">
          {items.map((item, index) => (
            <button
              key={item.key}
              type="button"
              className={`explorer-filmstrip-item ${index === activeIndex ? "explorer-filmstrip-item-active" : ""}`}
              onClick={() => onActiveIndexChange(index)}
            >
              {item.previewSrc ? <img src={item.previewSrc} alt={item.title} loading="lazy" /> : <span>{item.title}</span>}
            </button>
          ))}
        </div>
      </section>
    </>
  );
}
