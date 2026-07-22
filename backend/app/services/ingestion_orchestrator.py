"""
Ingestion Orchestrator

Responsibility:
- Coordinate all news ingestion services (NewsAPI + RSS)
- Merge both article lists
- Trigger the normalization pipeline after ingestion
- Return pipeline summary
"""

import asyncio
from loguru import logger

from app.services.news_api_service import NewsAPIService
from app.services.rss_feed_service import RSSFeedService
from app.services.normalization import run_normalization_pipeline


class IngestionOrchestrator:

    def __init__(self):
        """Initialize all ingestion services."""
        self.news_api_service = NewsAPIService()
        self.rss_feed_service = RSSFeedService()

    async def ingest_articles(self, keywords: list[str] = None) -> list[dict]:
        """
        Fetch articles from all sources concurrently.

        Steps:
        1. Fetch NewsAPI articles (with keywords)
        2. Fetch RSS articles
        3. Merge both lists

        Args:
            keywords: Optional keyword list for NewsAPI search.

        Returns:
            Merged list of article dicts from all sources.
        """
        logger.info("Starting concurrent article ingestion from all sources")

        # Fetch from both sources concurrently
        news_task = self.news_api_service.fetch_articles(keywords=keywords)
        rss_task = self.rss_feed_service.fetch_articles()

        results = await asyncio.gather(news_task, rss_task, return_exceptions=True)

        all_articles = []

        # Process NewsAPI results
        if isinstance(results[0], Exception):
            logger.error(f"NewsAPI fetch failed: {results[0]}")
        elif results[0]:
            logger.info(f"NewsAPI returned {len(results[0])} articles")
            all_articles.extend(results[0])

        # Process RSS results
        if isinstance(results[1], Exception):
            logger.error(f"RSS fetch failed: {results[1]}")
        elif results[1]:
            logger.info(f"RSS feeds returned {len(results[1])} articles")
            all_articles.extend(results[1])

        logger.info(f"Total articles collected: {len(all_articles)}")
        return all_articles

    async def run_full_pipeline(self, keywords: list[str] = None) -> dict:
        """
        Full pipeline: ingest articles → run normalization.

        1. Fetch from NewsAPI + RSS concurrently
        2. Run 4-step normalization pipeline (sync — SQLite writes)
        3. Return pipeline summary

        Args:
            keywords: Optional keyword list for NewsAPI search.

        Returns:
            Pipeline summary dict with counts.
        """
        logger.info("=" * 60)
        logger.info("FULL PIPELINE: INGEST → NORMALIZE")
        logger.info("=" * 60)

        # Step 1: Ingest
        articles = await self.ingest_articles(keywords=keywords)

        if not articles:
            logger.warning("No articles fetched. Pipeline aborted.")
            return {
                "articles_received": 0,
                "articles_inserted": 0,
                "events_stored": 0,
                "status": "no_articles",
            }

        # Step 2: Normalize (synchronous — SQLite doesn't like concurrent writes)
        # Run in thread pool to not block the event loop
        summary = await asyncio.get_event_loop().run_in_executor(
            None, run_normalization_pipeline, articles, True
        )

        summary["status"] = "complete"
        return summary