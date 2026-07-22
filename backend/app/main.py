"""
ImpactChain AI — FastAPI Backend

Endpoints:
  GET  /                    → Health check
  GET  /api/articles        → Raw RSS articles (legacy)
  POST /api/pipeline/run    → Trigger full ingest + normalize pipeline
  GET  /api/events          → Query master events (sorted by relevance)
  GET  /api/events/{uid}    → Single event with source articles
  GET  /api/stats           → Pipeline summary statistics
"""

from fastapi import FastAPI, HTTPException, Query
from loguru import logger

from app.services.rss_feed_service import RSSFeedService
from app.services.ingestion_orchestrator import IngestionOrchestrator
from app.services.normalization import query_master_events, query_event_by_uid, get_pipeline_stats, init_database

app = FastAPI(
    title="ImpactChain AI",
    description="Supply-chain intelligence from real-time news signals",
    version="0.2.0",
)

rss_feed_service = RSSFeedService()
orchestrator = IngestionOrchestrator()


@app.on_event("startup")
def startup_event():
    """Ensure database schema is created on startup without wiping existing data."""
    try:
        init_database(fresh=False)
        logger.info("Database initialized on startup.")
    except Exception as e:
        logger.error(f"Failed to initialize database on startup: {e}")



@app.get("/")
async def home():
    return {
        "message": "ImpactChain AI Backend Running!",
        "version": "0.2.0",
    }


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
    Trigger full pipeline: ingest from all sources → normalize → store events.

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