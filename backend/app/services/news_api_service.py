"""
NewsAPI Service

Responsibility:
- Communicate with NewsAPI
- Fetch articles
- Return parsed article list

Implementation will be added later.
"""

from app.config.settings import NEWS_API_KEY


class NewsAPIService:

    def __init__(self):
        self.api_key = NEWS_API_KEY

    async def fetch_articles(self):
        """
        Fetch articles from NewsAPI.

        Returns:
            List of normalized article dictionaries.
        """

        pass