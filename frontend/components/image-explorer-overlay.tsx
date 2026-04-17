"use client";

import Link from "next/link";
import { ReactNode, useCallback, useEffect, useRef, useState } from "react";

import { TagFilterChip } from "@/components/tag-filter-chip";
import { MediaDeepZoomStage, MediaDeepZoomViewerHandle } from "@/components/media-deep-zoom-viewer";
import { copyImageToClipboard } from "@/lib/clipboard";
import { copyTextToClipboard } from "@/lib/clipboard";
import { downloadWorkflow } from "@/lib/api";

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
  previewSrc: string | null | undefined;
  contentSrc: string | null | undefined;
  deepzoomUrl?: string | null | undefined;
  detailHref?: string | null;
  similarHref?: string | null;
  sourceContext?: string | null;
  metadataSummary?: ExplorerMetadataEntry[];
  workflowAvailable?: boolean;
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
  const viewerRef = useRef<MediaDeepZoomViewerHandle | null>(null);
  const viewerContainerRef = useRef<HTMLDivElement | null>(null);
  const filmstripRef = useRef<HTMLDivElement | null>(null);
  const currentItem = items[activeIndex] ?? null;
  const touchRef = useRef<{ x: number; y: number } | null>(null);
  const [metaPanelOpen, setMetaPanelOpen] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [rotation, setRotation] = useState(0);
  const [scalePercent, setScalePercent] = useState(100);
  const [navigatorVisible, setNavigatorVisible] = useState(true);
  const [copied, setCopied] = useState(false);
  const [toolbarVisible, setToolbarVisible] = useState(true);

  // Reset rotation when item changes
  useEffect(() => {
    setRotation(0);
  }, [activeIndex]);

  useEffect(() => {
    if (!open) return;
    setMetaPanelOpen(false);
    setShowHelp(false);
    setCopied(false);
  }, [open, activeIndex]);

  // Scroll active filmstrip item into view
  useEffect(() => {
    if (!open) return;
    const strip = filmstripRef.current;
    if (!strip) return;
    const active = strip.querySelector('.explorer-filmstrip-item-active') as HTMLElement | null;
    if (active) {
      active.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
    }
  }, [open, activeIndex]);

  // Horizontal wheel scroll on filmstrip
  useEffect(() => {
    const strip = filmstripRef.current;
    if (!strip) return;
    const handleWheel = (e: WheelEvent) => {
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        e.preventDefault();
        strip.scrollLeft += e.deltaY;
      }
    };
    strip.addEventListener('wheel', handleWheel, { passive: false });
    return () => strip.removeEventListener('wheel', handleWheel);
  }, [open]);

  const handleCopyImage = useCallback(async () => {
    if (!currentItem?.contentSrc) return;
    const ok = await copyImageToClipboard(currentItem.contentSrc);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    }
  }, [currentItem?.contentSrc]);

  const handleOpenOriginal = useCallback(() => {
    if (currentItem?.contentSrc) {
      window.open(currentItem.contentSrc, '_blank', 'noopener,noreferrer');
    }
  }, [currentItem?.contentSrc]);

  const handleFullscreen = useCallback(() => {
    const el = viewerContainerRef.current ?? document.documentElement;
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      el.requestFullscreen?.();
    }
  }, []);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      // Don't intercept when user is typing in an input
      if (
        document.activeElement instanceof HTMLInputElement ||
        document.activeElement instanceof HTMLTextAreaElement
      ) {
        return;
      }

      switch (event.key) {
        case "Escape":
          event.preventDefault();
          if (showHelp) { setShowHelp(false); return; }
          onClose();
          return;
        case "ArrowLeft":
        case "ArrowUp":
          event.preventDefault();
          onActiveIndexChange(Math.max(0, activeIndex - 1));
          return;
        case "ArrowRight":
        case "ArrowDown":
          event.preventDefault();
          onActiveIndexChange(Math.min(items.length - 1, activeIndex + 1));
          return;
        case "PageDown":
          event.preventDefault();
          onActiveIndexChange(Math.min(items.length - 1, activeIndex + 10));
          return;
        case "PageUp":
          event.preventDefault();
          onActiveIndexChange(Math.max(0, activeIndex - 10));
          return;
        case "0":
          event.preventDefault();
          viewerRef.current?.fit();
          return;
        case "1":
          event.preventDefault();
          viewerRef.current?.actualSize();
          return;
        case "c":
        case "C":
          event.preventDefault();
          if (currentItem?.promptTags.length) {
            void copyTextToClipboard(currentItem.promptTags.join(", "));
          }
          return;
        case "w":
        case "W":
        case "d":
        case "D":
          event.preventDefault();
          if (currentItem?.workflowAvailable && currentItem.key) {
            void downloadWorkflow(currentItem.key, currentItem.title);
          }
          return;
        case "?":
          event.preventDefault();
          setShowHelp((v) => !v);
          return;
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeIndex, items.length, onActiveIndexChange, onClose, open, currentItem, showHelp]);

  if (!open || !currentItem) {
    return null;
  }

  return (
    <>
      <button type="button" className="explorer-scrim" aria-label="Close explorer" onClick={onClose} />
      <section className="explorer-overlay">
        <div className="explorer-header">
          <div className="stack explorer-header-title">
            <p className="eyebrow">Explorer</p>
            <h2>{currentItem.title}</h2>
            {currentItem.subtitle ? <p className="subdued">{currentItem.subtitle}</p> : null}
          </div>
          <div className="explorer-header-actions">
            <button type="button" className="button ghost-button small-button" onClick={() => onActiveIndexChange(Math.max(0, activeIndex - 1))} disabled={activeIndex === 0} title="Previous">
              <span className="explorer-btn-icon" aria-hidden="true">◀</span>
              <span className="explorer-btn-label">Previous</span>
            </button>
            <button
              type="button"
              className="button ghost-button small-button"
              onClick={() => onActiveIndexChange(Math.min(items.length - 1, activeIndex + 1))}
              disabled={activeIndex >= items.length - 1}
              title="Next"
            >
              <span className="explorer-btn-icon" aria-hidden="true">▶</span>
              <span className="explorer-btn-label">Next</span>
            </button>
            <button type="button" className="button ghost-button small-button" onClick={() => setShowHelp((v) => !v)} title="Keyboard shortcuts">
              ?
            </button>
            <button type="button" className="button ghost-button small-button explorer-meta-toggle" onClick={() => setMetaPanelOpen((v) => !v)} title="Toggle info panel">
              <span className="explorer-btn-icon" aria-hidden="true">ℹ</span>
              <span className="explorer-btn-label">{metaPanelOpen ? "Hide" : "Info"}</span>
            </button>
            <button type="button" className="button small-button" onClick={onClose} title="Close">
              <span className="explorer-btn-icon" aria-hidden="true">✕</span>
              <span className="explorer-btn-label">Close</span>
            </button>
          </div>
        </div>

        {/* Keyboard help panel */}
        {showHelp ? (
          <div className="panel" style={{ padding: "0.75rem 1rem", marginBottom: "0.5rem" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.84rem" }}>
              <tbody>
                {[
                  ["← / →  or  ↑ / ↓", "Previous / Next image"],
                  ["Page Up / Page Down", "Jump ±10 images"],
                  ["C", "Copy Danbooru tags"],
                  ["D / W", "Download workflow (if available)"],
                  ["0", "Fit image to viewer"],
                  ["1", "Actual size"],
                  ["?", "Toggle this help panel"],
                  ["Esc", "Close explorer"],
                ].map(([key, desc]) => (
                  <tr key={key} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "0.3rem 0.6rem 0.3rem 0", fontFamily: "var(--font-mono)", color: "var(--accent)" }}>{key}</td>
                    <td style={{ padding: "0.3rem 0", color: "var(--muted)" }}>{desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

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
          <div className="panel explorer-viewer-panel" ref={viewerContainerRef}>
            {currentItem.contentSrc ? (
              <div style={{ transform: `rotate(${rotation}deg)`, transition: "transform 0.22s ease", height: "100%", width: "100%", position: "relative" }}>
                <MediaDeepZoomStage
                  ref={viewerRef}
                  source={{
                    previewSrc: currentItem.previewSrc ?? currentItem.contentSrc ?? null,
                    fullSrc: currentItem.contentSrc ?? currentItem.previewSrc ?? null,
                    deepzoomUrl: currentItem.deepzoomUrl ?? null,
                  }}
                  alt={currentItem.title}
                  defaultMode="fit"
                  navigatorVisible={navigatorVisible}
                  onScalePercentChange={setScalePercent}
                />
              </div>
            ) : (
              <div className="explorer-viewer-empty">No image available.</div>
            )}
            {/* Floating compact toolbar */}
            <div
              className={`explorer-floating-toolbar ${toolbarVisible ? '' : 'explorer-floating-toolbar-hidden'}`}
              onMouseEnter={() => setToolbarVisible(true)}
            >
              <button type="button" className="image-toolbar-btn" title="Fit" onClick={() => viewerRef.current?.fit()}>⊞</button>
              <button type="button" className="image-toolbar-btn" title="Zoom out" onClick={() => viewerRef.current?.zoomOut()}>−</button>
              <span className="explorer-toolbar-scale">{scalePercent}%</span>
              <button type="button" className="image-toolbar-btn" title="Zoom in" onClick={() => viewerRef.current?.zoomIn()}>+</button>
              <span className="explorer-toolbar-sep" />
              <button type="button" className="image-toolbar-btn" title={copied ? 'Copied!' : 'Copy image'} onClick={handleCopyImage} disabled={!currentItem.contentSrc}>{copied ? '✓' : '⧉'}</button>
              <button type="button" className="image-toolbar-btn" title="Open original" onClick={handleOpenOriginal} disabled={!currentItem.contentSrc}>↗</button>
              <button type="button" className="image-toolbar-btn" title="Fullscreen" onClick={handleFullscreen}>⤢</button>
              <button type="button" className="image-toolbar-btn" title={`Rotate (${rotation}°)`} onClick={() => setRotation((r) => (r + 90) % 360)}>↻</button>
              <button
                type="button"
                className={`image-toolbar-btn ${navigatorVisible ? 'image-toolbar-btn-active' : ''}`}
                title="Toggle navigator"
                onClick={() => {
                  const next = !navigatorVisible;
                  setNavigatorVisible(next);
                  viewerRef.current?.toggleNavigator(next);
                }}
              >🗺</button>
            </div>
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
        <div className="explorer-filmstrip" ref={filmstripRef}>
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
