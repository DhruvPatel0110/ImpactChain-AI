"""
Ingestion Orchestrator

Responsibility:
- Coordinate all news ingestion services.
- Collect articles from NewsAPI.
- Collect articles from RSS feeds.
- Merge both article lists.
- Normalize article format.
- Remove duplicate articles.

Week 1:
Structure only.
Implementation will be added in later weeks.
"""

from app.services.news_api_service import NewsAPIService
from app.services.rss_feed_service import RSSFeedService


class IngestionOrchestrator:

    def __init__(self):
        """
        Constructor

        Initializes all ingestion services.
        """

        self.news_api_service = NewsAPIService()
        self.rss_feed_service = RSSFeedService()

    async def ingest_articles(self):
        """
        Main ingestion pipeline.

        Steps:
        1. Fetch NewsAPI articles
        2. Fetch RSS articles
        3. Merge both sources
        4. Normalize article schema
        5. Remove duplicate articles
        6. Return clean article list

        Returns:
            List of normalized article dictionaries.
        """

        # Week 2 Implementation

        # news_articles = await self.news_api_service.fetch_articles()
        # rss_articles = await self.rss_feed_service.fetch_articles()

        # merged_articles = ...
        # normalized_articles = ...
        # deduplicated_articles = ...

        pass