"""
ImpactChain AI — Phase 2 Orchestrator (2A + 2B)

Phase 2A (Steps 2.1–2.3):
  fetch_unembedded_articles() — read from master.db, skip already-in-ChromaDB
  generate_embedding()        — compound string + sentence-transformers vector
  VectorStore.batch_add_articles() — persist to ChromaDB

Phase 2B (Step 2.4):
  fetch_articles_for_graph()  — read from master.db, skip already-in-graph
  MasterGraph.update_from_articles() — incremental graph update
  MasterGraph._save()         — persist to data/master_graph.json

Entry points:
  run_phase2a() — called from main.py startup after run_phase_1()
  run_phase2b() — called from main.py startup after run_phase2a()
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


# ============================================================================
# Step 2.4 — Fetch articles for graph update
# ============================================================================

def fetch_articles_for_graph(
    last_processed_timestamp: Optional[str] = None,
) -> list[dict]:
    """
    Query master.db for relevant articles that have not yet been processed
    into the master graph.

    If last_processed_timestamp is provided, only articles with
    ingested_at > that timestamp are returned.
    If None (fresh graph), ALL relevant articles are returned.

    Args:
        last_processed_timestamp: ISO timestamp string from graph_metadata table,
                                  or None for a fresh graph.

    Returns:
        List of normalized article dicts, ordered by ingested_at ascending.
    """
    db_path = _DATABASE_PATH

    if not Path(db_path).exists():
        logger.warning(f"master.db not found at {db_path} — no articles for graph.")
        return []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if last_processed_timestamp:
            cursor.execute(
                """
                SELECT full_json
                FROM articles
                WHERE is_relevant = 1
                  AND confidence >= 0.40
                  AND ingested_at > ?
                ORDER BY ingested_at ASC
                """,
                (last_processed_timestamp,),
            )
        else:
            cursor.execute(
                """
                SELECT full_json
                FROM articles
                WHERE is_relevant = 1
                  AND confidence >= 0.40
                ORDER BY ingested_at ASC
                """
            )

        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        logger.error(
            f"Failed to query master.db for graph articles: {e}", exc_info=True
        )
        return []

    articles: list[dict] = []
    for row in rows:
        try:
            article = json.loads(row["full_json"])
            articles.append(article)
        except json.JSONDecodeError as e:
            logger.warning(f"Skipping article with invalid full_json: {e}")

    logger.info(
        f"Found {len(articles)} articles for graph update "
        f"(since={last_processed_timestamp or 'beginning'})."
    )
    return articles


# ============================================================================
# Phase 2B main entry point
# ============================================================================

def run_phase2b():
    """
    Phase 2B orchestrator — Master Graph Construction.

    Execution order:
      1. Instantiate MasterGraph (loads from disk or creates empty).
      2. Fetch articles from master.db newer than last_processed_at.
      3. If none found, return the existing (already up-to-date) graph.
      4. Feed new articles into graph (nodes + edges with weight accumulation).
      5. Save graph to data/master_graph.json (atomic write).
      6. Update graph_metadata.last_processed_at in master.db.

    Returns the MasterGraph instance so main.py can store it in app_state
    for the lifetime of the server (Phase 4 reads from this object).

    This function is synchronous — no async needed because it does purely
    CPU + disk work with no external API calls.
    """
    from master_graph import MasterGraph

    logger.info("=" * 60)
    logger.info("Phase 2B starting: Master Graph Construction")
    logger.info("=" * 60)

    try:
        master_graph = MasterGraph()
    except Exception as e:
        logger.error(f"Phase 2B aborted: MasterGraph initialisation failed: {e}")
        return None

    # Fetch only articles not yet reflected in the graph
    articles = fetch_articles_for_graph(master_graph._last_processed_timestamp)

    if not articles:
        logger.info("Master graph is already up to date. No new articles to process.")
        stats = master_graph.get_graph_stats()
        logger.info(f"Current graph stats: {stats}")
        logger.info("=" * 60)
        return master_graph

    # Incremental update
    master_graph.update_from_articles(articles)

    stats = master_graph.get_graph_stats()
    logger.info(f"Phase 2B complete. Graph stats: {stats}")
    logger.info("=" * 60)

    return master_graph
