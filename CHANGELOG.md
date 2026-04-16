# Changelog

All notable changes to MKLanLocal are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [1.6.0] — 2026-04-14

### Fixed

- **Image clicks blocked by overlay** — `gallery-status-badge` had no `pointer-events: none`, making it intercept taps in the top-left corner of every tile on mobile. The badge is purely cosmetic; it now passes all pointer events through to the image button beneath it.
- **Search page shows no results on first open** — Default sort was `relevance`, which returns 0 results when there is no query string. Default is now `modified_at` so the page always populates with images on load. The `SearchPageContent` component also auto-corrects any `?sort=relevance` URL param to `modified_at` when the query is empty.
- **Mobile filter panel unscrollable** — On viewports ≤ 900 px the filter sidebar now renders as a `BottomSheet` (the same component used by gallery long-press menus), giving it native-scroll, drag-to-dismiss, and a proper safe-area-inset footer. The old fixed slide-panel remains on desktop.
- **Filter inputs too small on mobile** — Added `min-height: 44px; font-size: 1rem` to `.field input` and `.field select` inside the `@media (max-width: 1024px)` block to hit Apple/Google tap-target guidelines and prevent iOS auto-zoom on focus.

### Added

- **File Explorer page** (`/sources/:id/explorer`) — A Windows-Explorer-style two-pane page: a collapsible folder tree on the left (lazy-loads children via the existing `/sources/:id/tree` API), and a folder contents panel on the right showing subfolder tiles and an image summary. From any folder you can:
  - Navigate the full directory hierarchy without leaving the page.
  - Click **📌 Index This Folder as Source** to immediately create a scoped source from the selected subfolder (requires `can_manage_sources`).
  - Open the **Gallery View** for that exact path in the existing live-browse page.
- **Explorer entry points** — A `📁 File Explorer` button now appears in the source list cards (Sources page) and in the header actions of the source gallery page, so the new page is always one tap away.

## [1.0.0] — 2026-04-13 — First public release

Initial open-source release. Covers all features developed through internal versions v1–v3.

### Core Features

- **Source management** — Mount any number of local folders as named sources.
- **Recursive metadata indexing** — ExifTool + ffprobe extract camera make/model, GPS, resolution, duration, and 100+ other fields per file.
- **Full-text + faceted search** — PostgreSQL `tsvector` search with filters for media type, camera, year, dimensions, duration, tags, rating, and review status.
- **Near-duplicate detection** — Perceptual hash (pHash / OpenCV) with configurable Hamming distance threshold.
- **Semantic image similarity** — CLIP embeddings stored in pgvector; configurable cosine similarity threshold and neighbour limit.
- **Side-by-side comparison** — Pixel-locked pan/zoom sync, overlay diff mode, metadata diff table.
- **Collections** — Named groups of assets; bulk add/remove from gallery or search results.

### Curation

- **Asset annotations** — Per-user rating (1–5 ★), review status (unreviewed / approved / rejected / favorite), curator note, and flagged toggle.
- **Bulk curation UI** — Multi-select in Browse and Search; right-click / long-press context menu with Approve, Reject, Favorite, Flag, Rate, and Add-to-Collection actions.
- **Search by example** — "Find visually similar" on any asset uses existing CLIP embeddings.

### Administration

- **User management** — Three built-in roles (admin, curator, guest); password reset, lock with duration, ban with reason.
- **User groups** — Flexible capability overrides per group, including source-scoped access.
- **Backup & restore** — Streams a ZIP with pg_dump + SHA256 manifest; dry-run validation before applying.
- **Live settings** — Thumbnail size, CLIP thresholds, cache limits adjustable at runtime.
- **Rate limiting** — Sliding-window limiter on login and destructive admin actions.
- **Startup security check** — Server refuses to start with default `SESSION_SECRET` outside development mode.

### UI & Performance

- **Virtualized gallery** — Handles 10 000+ images without jank.
- **BlurHash previews** — Instant placeholder while thumbnails load.
- **Deep Zoom viewer** — Tile-based viewer for gigapixel images.
- **Touch support** — Swipe navigation in the image explorer.
- **Structured JSON logging** — All services emit newline-delimited JSON including full `extra` context fields.

### Infrastructure

- Docker Compose stack: PostgreSQL 16 + pgvector, FastAPI, Next.js (standalone), async scan worker.
- HuggingFace model cache persisted across restarts via named Docker volume.
- Idempotent Alembic migrations safe to re-run.

### Security fixes applied before public release

- Removed hardcoded real credentials from `config.py` defaults.
- Removed personal host paths from `docker-compose.yml`.
- Removed `backup/` folder (contained `.env` snapshot with live passwords).
- `JsonFormatter` now surfaces structured `extra` fields — errors no longer silently swallowed.
- CLIP load failure flagged once and skipped cleanly for the rest of the scan session.
- `get_image_features()` output unpacked correctly for current transformers versions.
