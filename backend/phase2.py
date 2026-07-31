"""
ImpactChain AI — Phase 2A Orchestrator

Covers Steps 2.1, 2.2, and 2.3:
  2.1  fetch_unembedded_articles() — read from master.db, skip already-in-ChromaDB
  2.2  generate_embedding()        — compound string + sentence-transformers vector
  2.3  VectorStore.batch_add_articles() — persist to ChromaDB

Entry point: run_phase2a()
  Called from main.py startup event after run_phase_1() completes.

Idempotency guarantee:
  On every startup, existing ChromaDB IDs are fetched first. Articles that are
  already embedded are skipped. Only genuinely new articles (added by the latest
  Phase 1 run) are processed and inserted into ChromaDB.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from embeddings import generate_embedding, load_embedding_model
from vector_store import VectorStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database path — same resolution logic as database.py / config.py
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).resolve().parent
_DATABASE_PATH = str(_BACKEND_DIR / "data" / "master.db")


# ============================================================================
# Step 2.1 — Fetch unembedded articles from master.db
# ============================================================================

def fetch_unembedded_articles(
    vector_store: Optional[VectorStore] = None,
) -> list[dict]:
    """
    Read all relevant articles from master.db, then filter out those that are
    already stored in ChromaDB.

    Queries master.db:
        SELECT * FROM articles WHERE is_relevant = 1 AND confidence >= 0.40

    Deserializes full_json → Python dict for each row.
    Calls vector_store.get_existing_ids() to determine which are already embedded.
    Returns only articles whose article_id is NOT in ChromaDB.

    Args:
        vector_store: Optionally pass an already-initialised VectorStore.
                      If None, a new one is created (useful for testing).

    Returns:
        List of normalized article dicts that have not yet been embedded.
    """
    db_path = _DATABASE_PATH

    if not Path(db_path).exists():
        logger.warning(f"master.db not found at {db_path} — no articles to embed.")
        return []

    # --- Fetch all relevant articles from master.db ---
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT article_id, full_json
            FROM articles
            WHERE is_relevant = 1
              AND confidence >= 0.40
            ORDER BY ingested_at ASC
            """
        )
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to query master.db at {db_path}: {e}", exc_info=True)
        return []

    total_in_db = len(rows)
    logger.info(f"master.db has {total_in_db} relevant articles (is_relevant=1, confidence≥0.40).")

    if total_in_db == 0:
        return []

    # --- Deserialize full_json for each row ---
    all_articles: list[dict] = []
    for row in rows:
        article_id: str = row["article_id"]
        raw_json: str = row["full_json"]
        try:
            article = json.loads(raw_json)
            all_articles.append(article)
        except json.JSONDecodeError as e:
            logger.warning(
                f"Failed to deserialize full_json for article {article_id}: {e} — skipping."
            )

    # --- Get IDs already in ChromaDB ---
    vs = vector_store or VectorStore()
    existing_ids: set[str] = vs.get_existing_ids()

    # --- Filter to unembedded articles only ---
    unembedded = [
        article for article in all_articles
        if article.get("article_id") not in existing_ids
    ]

    already_count = total_in_db - len(unembedded)
    logger.info(
        f"Embedding status: {already_count} already in ChromaDB, "
        f"{len(unembedded)} new articles need embedding."
    )

    return unembedded


# ============================================================================
# Metadata builder
# ============================================================================

def build_metadata(article: dict) -> dict:
    """
    Construct a flat ChromaDB metadata dict from a normalized article.

    ChromaDB metadata values MUST be str, int, float, or bool only.
    No nested dicts, no lists. Arrays are embedded in the compound string
    for semantic searchability, but only scalars go in metadata.

    Fields:
        source_name      — string
        source_type      — string (e.g., "rss", "newsapi")
        event_category   — string (e.g., "geopolitical", "weather")
        primary_commodity— first commodity from primary_commodities list
        published_at     — unix timestamp (int) for range-filtering in Phase 3
        confidence       — float relevance confidence from Groq

    Returns:
        Flat dict with exactly the above keys, all scalar values.
    """
    # --- primary_commodity: only first element (metadata must be flat) ---
    primary_commodities = article.get("primary_commodities") or []
    if primary_commodities and isinstance(primary_commodities, list):
        primary_commodity = str(primary_commodities[0]).strip() or "unknown"
    else:
        primary_commodity = "unknown"

    # --- published_at → unix timestamp ---
    published_at_str: str = article.get("published_at") or ""
    try:
        if published_at_str:
            # Handle both "2025-01-15T10:30:00Z" and "2025-01-15T10:30:00+00:00" formats
            published_at_str_clean = published_at_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(published_at_str_clean)
            published_at_ts = int(dt.timestamp())
        else:
            published_at_ts = 0
    except (ValueError, TypeError) as e:
        logger.warning(
            f"Could not parse published_at '{published_at_str}' for article "
            f"{article.get('article_id', 'unknown')}: {e} — defaulting to 0."
        )
        published_at_ts = 0

    return {
        "source_name": str(article.get("source_name") or "unknown"),
        "source_type": str(article.get("source_type") or "unknown"),
        "event_category": str(article.get("event_category") or "unknown"),
        "primary_commodity": primary_commodity,
        "published_at": published_at_ts,
        "confidence": float(article.get("confidence") or 0.0),
    }


# ============================================================================
# Phase 2A main entry point
# ============================================================================

async def run_phase2a():
    """
    Phase 2A orchestrator — Embeddings and ChromaDB.

    Execution order:
      1. Initialise VectorStore (ChromaDB persistent client).
      2. Fetch articles from master.db that are not yet in ChromaDB.
      3. If none found, exit early.
      4. Load sentence-transformers embedding model (once).
      5. Generate compound string + 384-float embedding per article.
      6. Batch-insert all embeddings into ChromaDB (50 per call).

    This function is called from main.py startup event after run_phase_1().
    It is idempotent: restarting the server will not re-embed already-stored
    articles.
    """
    logger.info("=" * 60)
    logger.info("Phase 2A starting: Embeddings and ChromaDB")
    logger.info("=" * 60)

    # Step 2.1 — Initialise VectorStore and fetch unembedded articles
    try:
        vector_store = VectorStore()
    except Exception as e:
        logger.error(f"Phase 2A aborted: ChromaDB initialisation failed: {e}")
        return

    articles = fetch_unembedded_articles(vector_store=vector_store)

    if not articles:
        logger.info("Phase 2A: No new articles to embed. ChromaDB is up to date.")
        return

    logger.info(f"Phase 2A: Embedding {len(articles)} new articles.")

    # Step 2.2 — Load embedding model (no-op if already loaded)
    try:
        load_embedding_model()
    except Exception as e:
        logger.error(f"Phase 2A aborted: Embedding model load failed: {e}")
        return

    # Step 2.2 → 2.3 — Generate embeddings and accumulate batch
    batch: list[tuple[str, str, list[float], dict]] = []
    failed_count = 0

    for article in articles:
        article_id = article.get("article_id", "unknown")
        try:
            compound_string, embedding_vector = generate_embedding(article)
            metadata = build_metadata(article)
            batch.append((article_id, compound_string, embedding_vector, metadata))
        except Exception as e:
            failed_count += 1
            logger.error(
                f"Phase 2A: Skipping article {article_id} — embedding failed: {e}"
            )

    if not batch:
        logger.warning("Phase 2A: All articles failed to embed. ChromaDB not updated.")
        return

    # Step 2.3 — Batch insert into ChromaDB
    added_count = vector_store.batch_add_articles(batch)

    logger.info(
        f"Phase 2A complete. "
        f"{added_count}/{len(articles)} articles embedded and stored in ChromaDB"
        + (f" ({failed_count} failed)." if failed_count else ".")
    )
    logger.info(
        f"ChromaDB collection now contains {vector_store.count()} total documents."
    )
    logger.info("=" * 60)
