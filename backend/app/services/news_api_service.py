"""
NewsAPI Service

Responsibility:
- Communicate with NewsAPI
- Fetch articles for multiple keywords concurrently
- Keep track of monthly API call count to enforce 5,000 monthly rate limit
- Format and normalize response payload
"""

import os
import json
import datetime
import asyncio
from pathlib import Path
import aiohttp
from loguru import logger
from app.config.settings import NEWS_API_KEY

# File path to persist rate limiting status across runs
TRACKER_FILE = Path(__file__).parent.parent / "config" / ".news_api_tracker.json"
MAX_MONTHLY_CALLS = 4950  # Safety buffer (50 calls) below NewsAPI's 5,000 limit


def _check_and_increment_rate_limit(calls_to_make: int = 1) -> bool:
    """
    Check monthly API call tracker.
    Resets counter if calendar month has changed.
    Increments and saves if under budget.
    """
    now = datetime.datetime.now()
    current_month_str = now.strftime("%Y-%m")
    
    data = {"month": current_month_str, "calls": 0}
    
    if TRACKER_FILE.exists():
        try:
            with open(TRACKER_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if loaded.get("month") == current_month_str:
                    data = loaded
        except Exception as e:
            logger.warning(f"Could not read NewsAPI rate tracker file; resetting tracker: {e}")

    # Enforce budget limit
    if data["calls"] + calls_to_make > MAX_MONTHLY_CALLS:
        logger.warning(
            f"NewsAPI Rate Limit Reached! Cannot make {calls_to_make} calls. "
            f"Usage this month: {data['calls']}/{MAX_MONTHLY_CALLS}."
        )
        return False
        
    data["calls"] += calls_to_make
    try:
        TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Could not write to rate tracker file: {e}")
        
    return True


class NewsAPIService:

    def __init__(self):
        self.api_key = NEWS_API_KEY

    async def fetch_articles(self, keywords=None):
        """
        Fetch articles from NewsAPI for multiple keywords concurrently.

        Parameters:
            keywords (list): Search queries to fetch articles for.

        Returns:
            list: Normalized list of article dictionaries.
        """
        if not self.api_key:
            logger.error("NewsAPI key is missing in config settings.")
            return []

        if not keywords:
            # Default supply chain keywords to gather impactful events
            keywords = [
                "supply chain disruption",
                "port congestion",
                "semiconductor shortage",
                "factory closure",
                "shipping delay"
            ]

        # 1. Enforce Rate Limiting
        num_requests = len(keywords)
        if not _check_and_increment_rate_limit(num_requests):
            logger.error("Aborting requests to NewsAPI to respect rate limit quota.")
            return []

        logger.info(f"Initiating concurrent NewsAPI calls for keywords: {keywords}")

        # 2. Concurrent HTTP Requests
        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_keyword_articles(session, keyword) for keyword in keywords]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles = []
        for keyword, res in zip(keywords, results):
            if isinstance(res, Exception):
                logger.error(f"Error fetching NewsAPI articles for keyword '{keyword}': {res}")
            elif res:
                all_articles.extend(res)

        logger.info(f"Successfully fetched {len(all_articles)} total articles from NewsAPI.")
        return all_articles

    async def _fetch_keyword_articles(self, session: aiohttp.ClientSession, keyword: str):
        """
        Fetch articles for a single keyword with timeout and error handling.
        """
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": keyword,
            "apiKey": self.api_key,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 20  # Limit to 20 articles per keyword
        }

        try:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 429:
                    logger.error("NewsAPI error: 429 Too Many Requests (Rate limit hit).")
                    return []
                elif response.status != 200:
                    err_txt = await response.text()
                    logger.error(f"NewsAPI error (Status {response.status}): {err_txt}")
                    return []

                payload = await response.json()
                if payload.get("status") != "ok":
                    logger.error(f"NewsAPI returned bad status: {payload.get('message')}")
                    return []

                articles = payload.get("articles", [])
                normalized_articles = []

                for item in articles:
                    # Clean and map to our internal unified structure
                    normalized_articles.append({
                        "title": item.get("title"),
                        "description": item.get("description"),
                        "content": item.get("content"),
                        "url": item.get("url"),
                        "source": item.get("source", {}).get("name", "NewsAPI"),
                        "published_at": item.get("publishedAt"),
                        "author": item.get("author"),
                        "keyword_queried": keyword
                    })

                return normalized_articles

        except asyncio.TimeoutError:
            logger.error(f"Network timeout fetching news for '{keyword}'")
            return []
        except aiohttp.ClientError as e:
            logger.error(f"Aiohttp connection error for '{keyword}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected exception for '{keyword}': {e}")
            return []