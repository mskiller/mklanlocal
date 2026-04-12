# Changelog

All notable changes to MKLanLocal are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

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
