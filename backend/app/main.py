"""
ImpactChain AI — FastAPI Backend

Phase 1 endpoints:
  GET  /                        → Health check
  POST /api/phase1/run          → Manually trigger Phase 1 ingestion pipeline
  GET  /api/articles            → Raw RSS articles (legacy)
  POST /api/pipeline/run        → Legacy pipeline trigger
  GET  /api/events              → Query master events (legacy)
  GET  /api/events/{uid}        → Single event (legacy)
  GET  /api/stats               → Pipeline stats (legacy)

Phase 1 also runs automatically on server startup.
"""

import sys
import os
from pathlib import Path

# Ensure the backend directory is on sys.path so Phase 1 modules can be imported
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from fastapi import FastAPI, HTTPException, Query
from loguru import logger

# Legacy imports (old pipeline)
from app.services.rss_feed_service import RSSFeedService
from app.services.ingestion_orchestrator import IngestionOrchestrator
from app.services.normalization import (
    query_master_events,
    query_event_by_uid,
    get_pipeline_stats,
    init_database,
)

# Phase 1 imports
from ingestion import run_phase_1

app = FastAPI(
    title="ImpactChain AI",
    description="Supply-chain intelligence from real-time news signals",
    version="0.3.0",
)

rss_feed_service = RSSFeedService()
orchestrator = IngestionOrchestrator()


# ============================================================================
# Startup
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    On server startup:
    1. Initialize legacy database schema (non-destructive)
    2. Run Phase 1 ingestion pipeline
    """
    # Legacy DB init
    try:
        init_database(fresh=False)
        logger.info("Legacy database initialized on startup.")
    except Exception as e:
        logger.error(f"Failed to initialize legacy database on startup: {e}")

    # Phase 1 ingestion
    logger.info("Starting Phase 1 ingestion pipeline...")
    try:
        await run_phase_1()
        logger.info("Phase 1 ingestion pipeline complete.")
    except Exception as e:
        logger.error(f"Phase 1 ingestion pipeline failed: {e}")


# ============================================================================
# Phase 1 Endpoints
# ============================================================================

@app.post("/api/phase1/run")
async def trigger_phase1():
    """Manually trigger the Phase 1 ingestion pipeline."""
    try:
        await run_phase_1()
        return {"status": "success", "message": "Phase 1 ingestion pipeline completed"}
    except Exception as e:
        logger.error(f"Phase 1 manual trigger failed: {e}")
        raise HTTPException(status_code=500, detail=f"Phase 1 failed: {str(e)}")


# ============================================================================
# Health Check
# ============================================================================

@app.get("/")
async def home():
    return {
        "message": "ImpactChain AI Backend Running!",
        "version": "0.3.0",
        "phase_1": "active",
    }


# ============================================================================
# Legacy Endpoints (preserved for backward compatibility)
# ============================================================================

@app.get("/api/articles")
async def get_articles():
    """Legacy endpoint — raw RSS articles."""
    articles = await rss_feed_service.fetch_articles()
    return articles


@app.post("/api/pipeline/run")
async def run_pipeline(
    keywords: list[str] | None = None,
):
    """
    Trigger full legacy pipeline: ingest from all sources → normalize → store events.

    Optional body: list of keywords for NewsAPI search.
    If not provided, uses default supply chain keywords.
    """
    try:
        summary = await orchestrator.run_full_pipeline(keywords=keywords)
        return {
            "status": "success",
            "pipeline_summary": summary,
        }
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")


@app.get("/api/events")
async def get_events(
    limit: int = Query(default=50, ge=1, le=500),
    commodity: str = Query(default=None, description="Filter by commodity name"),
):
    """
    Query master events sorted by relevance score.

    Query params:
      - limit: max events to return (default 50)
      - commodity: optional commodity filter (e.g., 'crude oil')
    """
    try:
        events = query_master_events(limit=limit, commodity_filter=commodity)
        return {
            "count": len(events),
            "events": events,
        }
    except Exception as e:
        logger.error(f"Failed to query events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/events/{event_uid}")
async def get_event_detail(event_uid: str):
    """Get a single event by its UID, including all source articles."""
    try:
        event = query_event_by_uid(event_uid)
        if not event:
            raise HTTPException(status_code=404, detail=f"Event '{event_uid}' not found")
        return event
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to query event '{event_uid}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats():
    """Get pipeline summary statistics."""
    try:
        stats = get_pipeline_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))