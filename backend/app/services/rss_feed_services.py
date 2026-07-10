"""
RSS Feed Service

Responsibility:
- Read configured RSS feeds
- Fetch RSS XML feeds
- Parse XML responses
- Return parsed article list

Implementation will be added later.
"""

from app.config.settings import RSS_FEEDS


class RSSFeedService:

    def __init__(self):
        self.feeds = RSS_FEEDS

    async def fetch_articles(self):
        """
        Fetch articles from all configured RSS feeds.

        Returns:
            List of normalized article dictionaries.
        """

        pass