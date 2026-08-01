"""
ImpactChain AI — FastAPI Backend

Startup sequence:
  1. Legacy DB init
  2. Phase 1  — ingestion (NewsAPI + RSS → spaCy → Groq → master.db)
  3. Phase 2A — embeddings (master.db → sentence-transformers → ChromaDB)
  4. Phase 2B — master graph construction (master.db → NetworkX → master_graph.json)

Endpoints:
  GET  /                        → Health check
  POST /api/phase1/run          → Manually trigger Phase 1 ingestion pipeline
  POST /api/phase2a/run         → Manually trigger Phase 2A embedding pipeline
  POST /api/phase2b/run         → Manually trigger Phase 2B graph construction
  GET  /api/graph/master        → Full master graph JSON (frontend initial load)
  GET  /api/graph/stats         → Master graph statistics
  GET  /api/articles            → Raw RSS articles (legacy)
  POST /api/pipeline/run        → Legacy pipeline trigger
  GET  /api/events              → Query master events (legacy)
  GET  /api/events/{uid}        → Single event (legacy)
  GET  /api/stats               → Pipeline stats (legacy)
"""

import sys
import os
import asyncio
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

# Phase 1, 2A, 2B imports
from ingestion import run_phase_1
from phase2 import run_phase2a, run_phase2b
from master_graph import MasterGraph

app = FastAPI(
    title="ImpactChain AI",
    description="Supply-chain intelligence from real-time news signals",
    version="0.5.0",
)

# ---------------------------------------------------------------------------
# Application state — holds objects that persist across requests
# ---------------------------------------------------------------------------
app_state: dict = {}

rss_feed_service = RSSFeedService()
orchestrator = IngestionOrchestrator()


async def _run_startup_pipeline():
    """Background task: Run Phase 1 → Phase 2A → Phase 2B sequentially."""
    logger.info("Background pipeline started (Phase 1 → Phase 2A → Phase 2B)...")

    # Phase 1 — ingestion
    try:
        await run_phase_1()
        logger.info("Background Phase 1 complete.")
    except Exception as e:
        logger.error(f"Background Phase 1 failed: {e}")

    # Phase 2A — embeddings + ChromaDB
    try:
        await run_phase2a()
        logger.info("Background Phase 2A complete.")
    except Exception as e:
        logger.error(f"Background Phase 2A failed: {e}")

    # Phase 2B — master graph construction
    try:
        master_graph = run_phase2b()
        if master_graph:
            app_state["master_graph"] = master_graph
        logger.info("Background Phase 2B complete. Master graph updated in app_state.")
    except Exception as e:
        logger.error(f"Background Phase 2B failed: {e}")


# ============================================================================
# Startup
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    On server startup:
    1. Initialize legacy database schema (non-destructive)
    2. Pre-load MasterGraph into app_state so endpoints serve immediately
    3. Trigger Phase 1/2A/2B pipeline in background (non-blocking)
    """
    # Legacy DB init
    try:
        init_database(fresh=False)
        logger.info("Legacy database initialized on startup.")
    except Exception as e:
        logger.error(f"Failed to initialize legacy database on startup: {e}")

    # Pre-load MasterGraph into app_state right away
    try:
        app_state["master_graph"] = MasterGraph()
        logger.info("MasterGraph loaded into app_state.")
    except Exception as e:
        logger.error(f"Failed to load MasterGraph: {e}")

    # Launch pipeline in background so server listens on port 8000 IMMEDIATELY
    asyncio.create_task(_run_startup_pipeline())
    logger.info("Server startup complete. HTTP endpoints live at http://127.0.0.1:8000")


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


@app.post("/api/phase2a/run")
async def trigger_phase2a():
    """Manually trigger the Phase 2A embedding pipeline."""
    try:
        await run_phase2a()
        return {"status": "success", "message": "Phase 2A embedding pipeline completed"}
    except Exception as e:
        logger.error(f"Phase 2A manual trigger failed: {e}")
        raise HTTPException(status_code=500, detail=f"Phase 2A failed: {str(e)}")


@app.post("/api/phase2b/run")
async def trigger_phase2b():
    """Manually trigger the Phase 2B master graph construction pipeline."""
    try:
        master_graph = run_phase2b()
        app_state["master_graph"] = master_graph
        return {"status": "success", "message": "Phase 2B master graph pipeline completed"}
    except Exception as e:
        logger.error(f"Phase 2B manual trigger failed: {e}")
        raise HTTPException(status_code=500, detail=f"Phase 2B failed: {str(e)}")


# ============================================================================
# Health Check
# ============================================================================

@app.get("/")
async def home():
    return {
        "message": "ImpactChain AI Backend Running!",
        "version": "0.5.0",
        "phase_1": "active",
        "phase_2a": "active",
        "phase_2b": "active",
    }


# ============================================================================
# Master Graph Endpoints (Phase 2B)
# ============================================================================

@app.get("/api/graph/master")
def get_master_graph():
    """
    Return the full master graph as node-link JSON.

    Called ONCE by the frontend on initial load. The frontend caches this
    and does not request it again per query. Per-query highlighting data
    is served by Phase 4 endpoints instead.
    """
    master_graph = app_state.get("master_graph")
    if master_graph is None:
        raise HTTPException(status_code=503, detail="Master graph not yet initialized")
    return master_graph.get_full_graph_json()


@app.get("/api/graph/stats")
def get_graph_stats():
    """Return master graph statistics: node/edge counts, top-weighted entities."""
    master_graph = app_state.get("master_graph")
    if master_graph is None:
        raise HTTPException(status_code=503, detail="Master graph not yet initialized")
    return master_graph.get_graph_stats()


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