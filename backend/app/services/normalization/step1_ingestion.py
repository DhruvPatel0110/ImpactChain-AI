"""
Step 1 — Raw Ingestion

Stores fetched articles from NewsAPI + RSS into raw_articles table.
- Maps incoming article dicts to schema columns
- Normalizes timestamps to UTC ISO 8601
- Stores full original dict as raw_payload JSON
- Deduplicates by URL (INSERT OR IGNORE)
- Marks all articles as processed = FALSE for NER pipeline
"""

import json
import datetime
from loguru import logger

try:
    from dateutil import parser as dateutil_parser
except ImportError:
    dateutil_parser = None

from app.services.normalization.database import get_connection


# Known API source names (lowered) → treated as "api" type
_API_SOURCES = {"newsapi", "gnews", "news api"}


def _determine_source_type(article: dict) -> str:
    """Determine if article came from API or RSS based on source name."""
    source = (article.get("source") or "").lower().strip()
    keyword = article.get("keyword_queried")

    # If it has keyword_queried set, it came from keyword-based API search
    if keyword is not None:
        return "api"
    if source in _API_SOURCES:
        return "api"
    return "rss"


def _determine_source_name(article: dict) -> str:
    """
    Normalize source name for storage.
    API articles: 'newsapi' or actual source name from API response.
    RSS articles: feed name (e.g., 'BBC World', 'Economic Times').
    """
    source = article.get("source") or "unknown"
    return source.strip()


def _normalize_timestamp(raw_ts: str) -> str:
    """
    Normalize any timestamp format to UTC ISO 8601 string.
    Falls back to current UTC time if parsing fails or value is missing.
    """
    if not raw_ts:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    try:
        if dateutil_parser:
            dt = dateutil_parser.parse(raw_ts)
        else:
            # Fallback: try ISO format directly
            dt = datetime.datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))

        # Ensure UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            dt = dt.astimezone(datetime.timezone.utc)

        return dt.isoformat()
    except Exception as e:
        logger.warning(f"Could not parse timestamp '{raw_ts}': {e}. Using current UTC time.")
        return datetime.datetime.now(datetime.timezone.utc).isoformat()


def store_raw_articles(articles: list[dict]) -> int:
    """
    Store a list of fetched article dicts into raw_articles table.

    Expected article dict keys (from NewsAPIService / RSSFeedService):
        title, description, content, url, source, published_at, author, keyword_queried

    Returns:
        Number of newly inserted articles (excludes URL duplicates).
    """
    if not articles:
        logger.warning("Step 1: No articles provided for ingestion")
        return 0

    logger.info(f"Step 1: Ingesting {len(articles)} articles into raw_articles")

    insert_sql = """
        INSERT OR IGNORE INTO raw_articles
            (source_name, source_type, headline, url, full_text, summary,
             author, published_at, language, raw_payload, processed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
    """

    inserted = 0
    skipped = 0

    with get_connection() as conn:
        cursor = conn.cursor()

        for article in articles:
            url = (article.get("url") or "").strip()
            if not url:
                logger.debug("Skipping article with no URL")
                skipped += 1
                continue

            source_name = _determine_source_name(article)
            source_type = _determine_source_type(article)
            headline = article.get("title") or ""
            full_text = article.get("content") or ""
            summary = article.get("description") or ""
            author = article.get("author") or ""
            published_at = _normalize_timestamp(article.get("published_at"))
            raw_payload = json.dumps(article, ensure_ascii=False, default=str)

            try:
                cursor.execute(insert_sql, (
                    source_name,
                    source_type,
                    headline,
                    url,
                    full_text,
                    summary,
                    author,
                    published_at,
                    "en",
                    raw_payload,
                ))

                if cursor.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1

            except Exception as e:
                logger.error(f"Failed to insert article '{headline[:60]}': {e}")
                skipped += 1

        conn.commit()

    logger.info(
        f"Step 1 complete: {inserted} inserted, {skipped} skipped "
        f"(duplicates or invalid), {len(articles)} total received"
    )
    return inserted
