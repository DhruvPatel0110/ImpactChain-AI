"""
RSS Feed Service

Responsibility:
- Read configured RSS feeds
- Fetch RSS XML feeds asynchronously
- Parse XML responses using feedparser
- Return parsed article list
"""

import aiohttp
import asyncio
import feedparser
from loguru import logger
from email.utils import parsedate_to_datetime
import datetime
from app.config.settings import RSS_FEEDS


class RSSFeedService:

    def __init__(self):
        # Filter only enabled feeds
        self.feeds = [feed for feed in RSS_FEEDS if feed.get("enabled", True)]

    async def fetch_articles(self):
        """
        Fetch articles from all configured RSS feeds concurrently.

        Returns:
            List of normalized article dictionaries.
        """
        if not self.feeds:
            logger.warning("No RSS feeds are configured or enabled.")
            return []

        logger.info(f"Initiating RSS fetch for {len(self.feeds)} feeds.")

        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_single_feed(session, feed) for feed in self.feeds]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles = []
        for feed, res in zip(self.feeds, results):
            if isinstance(res, Exception):
                logger.error(f"Failed to fetch RSS feed '{feed.get('name')}': {res}")
            elif res:
                all_articles.extend(res)

        logger.info(f"Successfully fetched {len(all_articles)} total articles from RSS feeds.")
        return all_articles

    async def _fetch_single_feed(self, session: aiohttp.ClientSession, feed: dict):
        """
        Fetch and parse a single RSS feed.
        """
        name = feed.get("name")
        url = feed.get("url")

        try:
            logger.debug(f"Fetching RSS feed '{name}' from {url}")
            async with session.get(url, timeout=15) as response:
                if response.status != 200:
                    logger.error(f"RSS feed '{name}' returned status {response.status}")
                    return []
                
                # Read the response text (XML)
                xml_data = await response.text()
                
                # Parse XML using feedparser
                parsed = feedparser.parse(xml_data)
                
                if parsed.bozo:
                    logger.warning(f"Feedparser flagged non-fatal parsing warning (bozo) for '{name}': {parsed.bozo_exception}")

                articles = []
                for entry in parsed.entries:
                    # Extract date
                    raw_date = entry.get("published") or entry.get("updated")
                    published_at = self._normalize_date(raw_date)

                    # Extract source or default to feed name
                    source = entry.get("source", {}).get("title") or name

                    # Extract summary/description and content
                    description = entry.get("summary") or entry.get("description") or ""
                    
                    content_list = entry.get("content")
                    content = ""
                    if content_list and isinstance(content_list, list):
                        content = content_list[0].get("value", "")
                    if not content:
                        content = description

                    # Normalize into unified schema
                    articles.append({
                        "title": entry.get("title"),
                        "description": description,
                        "content": content,
                        "url": entry.get("link"),
                        "source": source,
                        "published_at": published_at,
                        "author": entry.get("author") or entry.get("creator"),
                        "keyword_queried": None  # RSS is broad, not keyword-specific
                    })

                logger.info(f"Fetched {len(articles)} articles from RSS feed '{name}'.")
                return articles

        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching RSS feed '{name}' from {url}")
            return []
        except aiohttp.ClientError as e:
            logger.error(f"Connection error fetching RSS feed '{name}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching RSS feed '{name}': {e}")
            return []

    def _normalize_date(self, date_str: str) -> str:
        """
        Normalize raw date string from RSS feed to ISO-8601 format.
        """
        if not date_str:
            return datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            dt = parsedate_to_datetime(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.isoformat()
        except Exception:
            # Fall back to raw string if parsing fails
            return date_str