"use client";

import { CSSProperties, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { BlurhashPlaceholder } from "@/components/blurhash-placeholder";
import { TagFilterChip } from "@/components/tag-filter-chip";

export interface GalleryTileAction {
  label: string;
  onSelect: () => void;
  variant?: "primary" | "subtle" | "ghost" | "danger";
  disabled?: boolean;
}

export function GalleryTile({
  imageSrc,
  blurHash,
  alt,
  title,
  subtitle,
  promptExcerpt,
  promptTags,
  statusBadge,
  selected,
  selectionMode,
  onOpen,
  onInspect,
  onToggleSelect,
  menuActions,
  className = "",
  tileStyle,
  imageButtonStyle,
  onImageLoad,
}: {
  imageSrc: string | null;
  blurHash?: string | null;
  alt: string;
  title: string;
  subtitle?: string | null;
  promptExcerpt?: string | null;
  promptTags: string[];
  statusBadge?: string | null;
  selected?: boolean;
  selectionMode?: boolean;
  onOpen: () => void;
  onInspect?: () => void;
  onToggleSelect?: () => void;
  menuActions: GalleryTileAction[];
  className?: string;
  tileStyle?: CSSProperties;
  imageButtonStyle?: CSSProperties;
  onImageLoad?: (size: { width: number; height: number }) => void;
}) {
  const [menuPos, setMenuPos] = useState<{ x: number; y: number } | null>(null);
  const menuOpen = menuPos !== null;
  const [loaded, setLoaded] = useState(false);
  const longPressTimer = useRef<number | null>(null);
  const longPressTriggered = useRef(false);
  const tileRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setLoaded(false);
  }, [imageSrc]);

  useEffect(() => {
    if (!menuOpen) {
      return;
    }
    const handlePointerDown = (event: PointerEvent) => {
      if (tileRef.current?.contains(event.target as Node)) {
        return;
      }
      setMenuPos(null);
    };
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [menuOpen]);

  const triggerInspect = () => {
    onInspect?.();
  };

  const triggerMenuAction = (action: GalleryTileAction) => {
    if (action.disabled) {
      return;
    }
    setMenuPos(null);
    action.onSelect();
  };

  return (
    <article
      ref={tileRef}
      className={`gallery-tile ${selected ? "gallery-tile-selected" : ""} ${className}`.trim()}
      style={tileStyle}
      onMouseEnter={triggerInspect}
      onContextMenu={(event) => {
        event.preventDefault();
        triggerInspect();
        setMenuPos({ x: event.clientX, y: event.clientY });
      }}
    >
      {statusBadge ? <span className="gallery-status-badge">{statusBadge}</span> : null}
      {onToggleSelect ? (
        <button
          type="button"
          className={`gallery-select-badge ${selected ? "gallery-select-badge-selected" : ""} ${selectionMode ? "gallery-select-badge-visible" : ""}`}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onToggleSelect();
          }}
        >
          {selected ? "Selected" : "Select"}
        </button>
      ) : null}
      <div className="gallery-image-shell">
        <button
          type="button"
          className="gallery-image-button"
          style={imageButtonStyle}
          onClick={(event) => {
            if (longPressTriggered.current) {
              longPressTriggered.current = false;
              event.preventDefault();
              return;
            }
            if (selectionMode && onToggleSelect) {
              event.preventDefault();
              onToggleSelect();
              return;
            }
            onOpen();
          }}
          onTouchStart={(event) => {
            triggerInspect();
            longPressTriggered.current = false;
            if (longPressTimer.current) {
              window.clearTimeout(longPressTimer.current);
            }
            const touch = event.touches[0];
            longPressTimer.current = window.setTimeout(() => {
              longPressTriggered.current = true;
              setMenuPos({ x: touch.clientX, y: touch.clientY });
            }, 420);
          }}
          onTouchEnd={() => {
            if (longPressTimer.current) {
              window.clearTimeout(longPressTimer.current);
              longPressTimer.current = null;
            }
          }}
          onTouchCancel={() => {
            if (longPressTimer.current) {
              window.clearTimeout(longPressTimer.current);
              longPressTimer.current = null;
            }
          }}
        >
          {imageSrc ? (
            <>
              {!loaded && blurHash ? <BlurhashPlaceholder hash={blurHash} className="gallery-blurhash" /> : null}
              <img
                src={imageSrc}
                alt={alt}
                loading="lazy"
                style={{ opacity: loaded ? 1 : 0 }}
                onLoad={(event) => {
                  setLoaded(true);
                  onImageLoad?.({
                    width: event.currentTarget.naturalWidth,
                    height: event.currentTarget.naturalHeight,
                  });
                }}
              />
            </>
          ) : (
            <div className="asset-placeholder">image</div>
          )}
        </button>
        <div className={`gallery-overlay ${menuOpen ? "gallery-overlay-visible" : ""}`}>
          <div className="gallery-overlay-top">
            <strong>{title}</strong>
            {subtitle ? <span>{subtitle}</span> : null}
          </div>
          <div className="gallery-overlay-body">
            {promptExcerpt ? <p>{promptExcerpt}</p> : null}
            {promptTags.length ? (
              <div className="chip-row gallery-overlay-tags">
                {promptTags.slice(0, 6).map((tag) => (
                  <TagFilterChip key={tag} tag={tag} prompt className="chip chip-prompt buttonless" />
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>
      {menuOpen && menuPos && typeof document !== "undefined"
        ? createPortal(
            <div
              className="gallery-context-menu gallery-context-menu-open"
              style={{
                position: "fixed",
                left: Math.min(menuPos.x, window.innerWidth - 240),
                top: Math.min(menuPos.y, window.innerHeight - 300),
                zIndex: 9999,
              }}
            >
              <div className="stack">
                <div>
                  <strong>{title}</strong>
                  {subtitle ? <p className="subdued">{subtitle}</p> : null}
                </div>
                {promptExcerpt ? <p className="subdued">{promptExcerpt}</p> : null}
              </div>
              <div className="stack">
                {menuActions.map((action) => (
                  <button
                    key={action.label}
                    type="button"
                    className={`button small-button ${
                      action.variant === "subtle"
                        ? "subtle-button"
                        : action.variant === "ghost"
                          ? "ghost-button"
                          : action.variant === "danger"
                            ? "danger-button"
                            : ""
                    }`.trim()}
                    disabled={action.disabled}
                    onClick={() => triggerMenuAction(action)}
                  >
                    {action.label}
                  </button>
                ))}
              </div>
            </div>,
            document.body
          )
        : null}
    </article>
  );
}
