"""
ImpactChain AI — Phase 1 Orchestrator

Dual-source article ingestion (NewsAPI + RSS) with async concurrency,
followed by sequential per-article processing:
  Step 1.1 → ingest_articles()
  Step 1.2 → spaCy entity extraction
  Step 1.3 → Groq relationship extraction
  Step 1.4 → Merge and normalize
  Step 1.5 → Store in master DB
"""

import hashlib
import asyncio
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import aiohttp
import feedparser

from config import (
    NEWSAPI_KEY,
    NEWSAPI_BASE_URL,
    NEWSAPI_CATEGORIES,
    NEWSAPI_PAGE_SIZE,
    RSS_FEEDS,
)
from database import MasterDB
from spacy_extractor import load_spacy_model, extract_entities_spacy
from groq_extractor import extract_relationships_groq
from normalizer import merge_and_normalize

logger = logging.getLogger(__name__)


# ============================================================================
# Step 1.1 — Dual Source Article Ingestion
# ============================================================================

def _generate_article_id(url: str) -> str:
    """Generate a deterministic SHA-256 article ID from the URL."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _normalize_date(date_str: str | None) -> str:
    """Convert various date formats to ISO-8601."""
    if not date_str:
        return datetime.now(timezone.utc).isoformat()
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        # Try ISO format directly
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.isoformat()
        except Exception:
            return date_str


async def _fetch_newsapi(session: aiohttp.ClientSession) -> list[dict]:
    """
    Fetch articles from NewsAPI top-headlines for business/technology/science.
    Returns list of normalized article dicts.
    """
    if not NEWSAPI_KEY:
        logger.warning("NEWSAPI_KEY not set — skipping NewsAPI source")
        return []

    all_articles = []

    for category in NEWSAPI_CATEGORIES:
        try:
            params = {
                "category": category,
                "apiKey": NEWSAPI_KEY,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": NEWSAPI_PAGE_SIZE,
            }
            logger.info(f"NewsAPI: fetching top-headlines category='{category}'")

            async with session.get(
                NEWSAPI_BASE_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 429:
                    logger.error("NewsAPI: 429 Too Many Requests — rate limited")
                    continue
                if response.status == 401:
                    logger.error("NewsAPI: 401 Unauthorized — check NEWSAPI_KEY")
                    continue
                if response.status != 200:
                    err = await response.text()
                    logger.error(f"NewsAPI: HTTP {response.status} for category '{category}': {err}")
                    continue

                payload = await response.json()
                if payload.get("status") != "ok":
                    logger.error(f"NewsAPI: bad status — {payload.get('message', 'unknown error')}")
                    continue

                articles = payload.get("articles", [])
                for item in articles:
                    url = item.get("url")
                    if not url:
                        continue

                    all_articles.append({
                        "article_id": _generate_article_id(url),
                        "title": item.get("title") or "",
                        "description": item.get("description") or "",
                        "content": item.get("content") or "",
                        "source_name": item.get("source", {}).get("name", "NewsAPI"),
                        "source_type": "newsapi",
                        "published_at": _normalize_date(item.get("publishedAt")),
                        "url": url,
                    })

                logger.info(
                    f"NewsAPI: fetched {len(articles)} articles for category '{category}'"
                )

        except asyncio.TimeoutError:
            logger.error(f"NewsAPI: timeout for category '{category}'")
        except aiohttp.ClientError as e:
            logger.error(f"NewsAPI: connection error for category '{category}': {e}")
        except Exception as e:
            logger.error(f"NewsAPI: unexpected error for category '{category}': {e}", exc_info=True)

    logger.info(f"NewsAPI: total {len(all_articles)} articles fetched")
    return all_articles


async def _fetch_rss_feed(
    session: aiohttp.ClientSession, feed: dict
) -> list[dict]:
    """Fetch and parse a single RSS feed. Returns list of article dicts."""
    name = feed.get("name", "Unknown")
    url = feed.get("url", "")

    try:
        logger.debug(f"RSS: fetching feed '{name}' from {url}")
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=15)
        ) as response:
            if response.status != 200:
                logger.error(f"RSS: feed '{name}' returned HTTP {response.status}")
                return []

            xml_data = await response.text()
            parsed = feedparser.parse(xml_data)

            if parsed.bozo:
                logger.warning(
                    f"RSS: feedparser warning for '{name}': {parsed.bozo_exception}"
                )

            articles = []
            for entry in parsed.entries:
                link = entry.get("link")
                if not link:
                    continue

                # Extract description/content
                description = entry.get("summary") or entry.get("description") or ""
                content_list = entry.get("content")
                content = ""
                if content_list and isinstance(content_list, list):
                    content = content_list[0].get("value", "")
                if not content:
                    content = description

                # Extract date
                raw_date = entry.get("published") or entry.get("updated")
                published_at = _normalize_date(raw_date)

                # Extract source
                source = entry.get("source", {})
                if isinstance(source, dict):
                    source_name = source.get("title") or name
                else:
                    source_name = name

                articles.append({
                    "article_id": _generate_article_id(link),
                    "title": entry.get("title") or "",
                    "description": description,
                    "content": content,
                    "source_name": source_name,
                    "source_type": "rss",
                    "published_at": published_at,
                    "url": link,
                })

            logger.info(f"RSS: fetched {len(articles)} articles from '{name}'")
            return articles

    except asyncio.TimeoutError:
        logger.error(f"RSS: timeout fetching feed '{name}' from {url}")
        return []
    except aiohttp.ClientError as e:
        logger.error(f"RSS: connection error for feed '{name}': {e}")
        return []
    except Exception as e:
        logger.error(f"RSS: unexpected error for feed '{name}': {e}", exc_info=True)
        return []


async def _fetch_all_rss(session: aiohttp.ClientSession) -> list[dict]:
    """Fetch all RSS feeds concurrently."""
    tasks = [_fetch_rss_feed(session, feed) for feed in RSS_FEEDS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_articles = []
    for feed, result in zip(RSS_FEEDS, results):
        if isinstance(result, Exception):
            logger.error(f"RSS: feed '{feed.get('name')}' raised exception: {result}")
        elif result:
            all_articles.extend(result)

    logger.info(f"RSS: total {len(all_articles)} articles fetched from {len(RSS_FEEDS)} feeds")
    return all_articles


async def ingest_articles() -> list[dict]:
    """
    Step 1.1: Fetch articles from NewsAPI + RSS concurrently, deduplicate
    against existing articles in master.db.

    Returns:
        List of deduplicated article dicts ready for processing.
    """
    logger.info("=" * 60)
    logger.info("STEP 1.1: Dual Source Article Ingestion")
    logger.info("=" * 60)

    async with aiohttp.ClientSession() as session:
        # Fetch from both sources concurrently
        newsapi_task = _fetch_newsapi(session)
        rss_task = _fetch_all_rss(session)

        results = await asyncio.gather(newsapi_task, rss_task, return_exceptions=True)

    all_articles = []

    # Process NewsAPI results
    if isinstance(results[0], Exception):
        logger.error(f"NewsAPI fetch raised exception: {results[0]}")
    elif results[0]:
        all_articles.extend(results[0])

    # Process RSS results
    if isinstance(results[1], Exception):
        logger.error(f"RSS fetch raised exception: {results[1]}")
    elif results[1]:
        all_articles.extend(results[1])

    if not all_articles:
        logger.warning("No articles fetched from any source")
        return []

    logger.info(f"Total raw articles fetched: {len(all_articles)}")

    # ------------------------------------------------------------------
    # Deduplication against master.db
    # ------------------------------------------------------------------
    db = MasterDB()
    try:
        # Also deduplicate within the current batch (same URL from multiple sources)
        seen_ids = set()
        deduplicated = []

        for article in all_articles:
            aid = article["article_id"]

            # Skip if already in this batch
            if aid in seen_ids:
                continue
            seen_ids.add(aid)

            # Skip if already in database
            if db.article_exists(aid):
                logger.debug(f"Skipping duplicate article {aid} (already in DB)")
                continue

            deduplicated.append(article)

        skipped = len(all_articles) - len(deduplicated)
        logger.info(
            f"Deduplication: {len(all_articles)} total → {len(deduplicated)} new "
            f"({skipped} skipped as duplicates)"
        )
        return deduplicated

    finally:
        db.close()


# ============================================================================
# Phase 1 Orchestrator
# ============================================================================

async def run_phase_1():
    """
    Main Phase 1 execution flow:
      1.1 → Ingest articles (NewsAPI + RSS)
      1.2 → spaCy entity extraction (per article)
      1.3 → Groq relationship extraction (per article)
      1.4 → Merge and normalize
      1.5 → Store in master database
    """
    logger.info("=" * 60)
    logger.info("PHASE 1: INGESTION PIPELINE — START")
    logger.info("=" * 60)

    # Step 1.1: Ingest
    raw_articles = await ingest_articles()
    if not raw_articles:
        logger.warning("No new articles to process — Phase 1 complete (no-op)")
        return

    logger.info(f"Processing {len(raw_articles)} new articles")

    # Load spaCy model once
    load_spacy_model()

    # Initialize database
    db = MasterDB()

    # Counters for summary
    processed = 0
    stored = 0
    rejected = 0
    low_conf = 0
    failed = 0

    try:
        # Process each article sequentially
        for i, article in enumerate(raw_articles, 1):
            article_id = article["article_id"]
            title = article.get("title", "")[:80]
            logger.info(f"[{i}/{len(raw_articles)}] Processing: {title}...")

            try:
                # Step 1.2: spaCy entity extraction
                spacy_scaffold = extract_entities_spacy(article)

                # Step 1.3: Groq relationship extraction
                groq_response = await extract_relationships_groq(article, spacy_scaffold)

                # Handle Groq failure
                if groq_response is None:
                    db.insert_failed_extraction(
                        article,
                        error_message="Groq extraction returned None",
                        raw_groq_response=None,
                    )
                    failed += 1
                    continue

                # Step 1.4: Merge and normalize
                normalized = merge_and_normalize(article, spacy_scaffold, groq_response)

                if normalized is None:
                    # Article was rejected (not relevant)
                    rejected += 1
                    continue

                # Step 1.5: Store in database
                success = db.insert_article(normalized)
                if success:
                    if normalized.get("is_relevant"):
                        stored += 1
                    else:
                        low_conf += 1

                processed += 1

            except Exception as e:
                logger.error(
                    f"Error processing article {article_id}: {e}",
                    exc_info=True,
                )
                try:
                    db.insert_failed_extraction(
                        article,
                        error_message=str(e),
                    )
                except Exception:
                    pass
                failed += 1
                continue

    finally:
        db.close()

    # Summary
    logger.info("=" * 60)
    logger.info("PHASE 1: INGESTION PIPELINE — COMPLETE")
    logger.info(f"  Articles fetched:       {len(raw_articles)}")
    logger.info(f"  Articles processed:     {processed}")
    logger.info(f"  Articles stored:        {stored}")
    logger.info(f"  Low confidence (queue):  {low_conf}")
    logger.info(f"  Rejected (not relevant): {rejected}")
    logger.info(f"  Failed extractions:      {failed}")
    logger.info("=" * 60)
