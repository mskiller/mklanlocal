# UI Fixes — mklanlocal v1.7

## Files changed

### Modified
- `frontend/components/app-shell.tsx`
- `frontend/components/justified-gallery.tsx`
- `frontend/components/asset-card.tsx`
- `frontend/components/interactive-image-stage.tsx`
- `frontend/components/BottomSheet.tsx`

### Added
- `frontend/components/scan-jobs-controls.tsx`
- `frontend/ui-fixes.css`

---

## Fix 1 — Back button everywhere

**File:** `app-shell.tsx`

Added a `<BackButton>` component that calls `router.back()`. It renders:
- In the **desktop page header**, next to the eyebrow/role line
- In the **mobile topbar**, between the Menu button and the page title

It is hidden on the root `/` dashboard (no previous page to go back to).

---

## Fix 2 — Gallery bleeds over Indexed Controls panel

**File:** `justified-gallery.tsx` + `ui-fixes.css`

Root cause: a flex child without `min-width: 0` can overflow its container,
causing the gallery to render on top of the sidebar controls.

Two-part fix:
1. `justified-gallery.tsx` — added `minWidth: 0, overflow: "hidden"` inline to the root div.
2. `ui-fixes.css` — added `.justified-gallery { min-width: 0 !important; overflow: hidden !important; }`
   as a global fallback, plus `.indexed-layout` / `.indexed-gallery-col` utility classes
   you can apply to your browse-indexed page layout wrapper.

In your browse-indexed page, wrap the layout like this:
```tsx
<div className="indexed-layout">
  <aside className="indexed-controls">
    {/* Gallery filters, tags, etc. */}
  </aside>
  <div className="indexed-gallery-col">
    <JustifiedGallery ... />
  </div>
</div>
```

---

## Fix 3 — Clear Done Jobs button on Scan Jobs page

**File:** `scan-jobs-controls.tsx` (new)

Drop `<ScanJobsControls onCleared={refetch} />` into your scan-jobs page.
It renders a "🗑 Clear Done Jobs" button that calls `DELETE /api/scan-jobs/done`.

**You need to add a backend route** (if not already present):
```python
@router.delete("/scan-jobs/done")
async def clear_done_scan_jobs(db: AsyncSession = Depends(get_db)):
    await db.execute(
        delete(ScanJob).where(ScanJob.status.in_(["done", "failed", "completed"]))
    )
    await db.commit()
    return {"deleted": True}
```
Adjust model/status names to match your codebase.

Usage in your page:
```tsx
import { ScanJobsControls } from "@/components/scan-jobs-controls";

// Inside your scan-jobs page, next to the page title or in the actions prop:
<AppShell title="Scan Jobs" actions={<ScanJobsControls onCleared={refetch} />}>
```

---

## Fix 4 — Remove image from collection

**File:** `asset-card.tsx`

Added `onRemoveFromCollection?: (asset: AssetSummary) => void` prop.

When provided, a red "Remove" button appears in the card actions row.

Usage in your collection detail page:
```tsx
<AssetCard
  asset={asset}
  onRemoveFromCollection={async (a) => {
    await fetch(`/api/collections/${collectionId}/assets/${a.id}`, { method: "DELETE" });
    refetch();
  }}
/>
```

---

## Fix 5 — Mobile: image hidden by info panel in explorer

**Files:** `interactive-image-stage.tsx`, `BottomSheet.tsx`, `ui-fixes.css`

**Root cause:** The image stage container collapsed because it was inside a flex
column without `flex: 1; min-height: 0`. The BottomSheet also locked body scroll
unconditionally, preventing touch interaction with the image.

Three-part fix:

1. **`interactive-image-stage.tsx`** — added `flex: 1, minHeight: 0` to both the
   shell wrapper and the stage div so they expand to fill available height.

2. **`BottomSheet.tsx`** — added `peekable` prop. When `peekable={true}`:
   - The sheet shows only the handle + title (≈4.5 rem tall) by default
   - Body scroll is NOT locked in peek state (image remains interactive)
   - Tapping "▴ More" or swiping up expands it to 70dvh
   - Swiping down or tapping "▾ Less" collapses it back to peek state

3. **`ui-fixes.css`** — added flex-column rules for `.mobile-image-viewer`,
   `.interactive-image-stage-shell`, and `.bottom-sheet-peekable`.

In your explorer/asset-detail mobile view, wrap the layout:
```tsx
<div className="mobile-image-viewer">
  <div className="explorer-toolbar">
    {/* Previous / Next / Close buttons */}
  </div>
  <div className="explorer-image-area">
    <InteractiveImageStage ... />
  </div>
  <BottomSheet peekable open={infoOpen} onClose={() => setInfoOpen(false)} title="Info">
    {/* metadata, prompt, etc. */}
  </BottomSheet>
</div>
```
