from __future__ import annotations

from fastapi import APIRouter

from media_indexer_backend.api.routes import admin, assets, auth, collections, compare, health, scan_jobs, search, shares, sources, tags, timeline


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(sources.router)
api_router.include_router(scan_jobs.router)
api_router.include_router(assets.router)
api_router.include_router(collections.router)
api_router.include_router(search.router)
api_router.include_router(tags.router)
api_router.include_router(compare.router)
api_router.include_router(timeline.router)
api_router.include_router(shares.router)
