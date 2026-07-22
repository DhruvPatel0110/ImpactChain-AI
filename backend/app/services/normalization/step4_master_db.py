"""
Step 4 — Master DB Storage

Takes consolidated events and stores them in the final master tables:
  - master_events: one row per supply-chain event
  - master_event_sources: junction table linking events to source articles

Generates deterministic event_uid and computes relevance_score.
Leaves embedding_id, significance_tier, significance_score as NULL for Month 2.
"""

import json
from loguru import logger

from app.services.normalization.database import get_connection


def _compute_relevance_score(
    source_count: int,
    article_count: int,
    price_count: int,
    signal_count: int,
    commodity_count: int,
    max_values: dict,
) -> float:
    """
    Compute relevance_score with normalized 0-1 factors.

    Formula:
      relevance_score = (source_count × 0.25) + (article_count × 0.15)
                      + (price_signals × 0.30) + (sc_signals × 0.20)
                      + (commodity_count × 0.10)

    Each factor normalized to 0-1 by dividing by max observed value.
    """
    def _norm(val, max_val):
        if max_val <= 0:
            return 0.0
        return min(val / max_val, 1.0)

    score = (
        _norm(source_count, max_values.get("source_count", 1)) * 0.25
        + _norm(article_count, max_values.get("article_count", 1)) * 0.15
        + _norm(price_count, max_values.get("price_count", 1)) * 0.30
        + _norm(signal_count, max_values.get("signal_count", 1)) * 0.20
        + _norm(commodity_count, max_values.get("commodity_count", 1)) * 0.10
    )

    return round(score, 4)


def _generate_event_uid(primary_commodity: str, date_str: str, cluster_index: int) -> str:
    """
    Generate deterministic event UID.
    Format: {primary_commodity}_{date_str}_{cluster_index}
    Example: crude_oil_20240712_001
    """
    sanitized = primary_commodity.lower().replace(" ", "_").replace("-", "_")
    return f"{sanitized}_{date_str}_{cluster_index:03d}"


def store_master_events(events: list[dict]) -> int:
    """
    Store consolidated events into master_events + master_event_sources.

    Args:
        events: Output from consolidate_clusters()

    Returns:
        Number of events stored.
    """
    if not events:
        logger.info("Step 4: No events to store")
        return 0

    logger.info(f"Step 4: Storing {len(events)} events in master DB")

    # Pre-compute max values for relevance score normalization
    max_values = {
        "source_count": max((e["source_count"] for e in events), default=1),
        "article_count": max((e["article_count"] for e in events), default=1),
        "price_count": max(
            (len(e["price_mentions"]) + len(e["rate_changes"]) for e in events),
            default=1,
        ),
        "signal_count": max((len(e["sc_signals"]) for e in events), default=1),
        "commodity_count": max((len(e["commodities"]) for e in events), default=1),
    }

    logger.debug(f"  Max values for normalization: {max_values}")

    insert_event_sql = """
        INSERT OR IGNORE INTO master_events
            (event_uid, primary_commodity, primary_entity_type,
             headline, summary,
             commodities, companies, regions, locations, sc_signals,
             price_mentions, rate_changes,
             source_count, article_count, unique_sources,
             primary_article_id, event_start, event_last_seen,
             relevance_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    insert_source_sql = """
        INSERT OR IGNORE INTO master_event_sources
            (event_id, article_id, is_primary, source_name)
        VALUES (?, ?, ?, ?)
    """

    stored_count = 0
    cluster_index_map = {}  # per-commodity counter for UID generation

    with get_connection() as conn:
        cursor = conn.cursor()

        for event in events:
            commodity = event["primary_commodity"]

            # Track cluster index per commodity
            if commodity not in cluster_index_map:
                cluster_index_map[commodity] = 0
            cluster_index_map[commodity] += 1
            idx = cluster_index_map[commodity]

            # Extract date from event_start for UID
            date_str = ""
            if event.get("event_start"):
                date_str = event["event_start"][:10].replace("-", "")
            else:
                import datetime
                date_str = datetime.datetime.now(
                    datetime.timezone.utc
                ).strftime("%Y%m%d")

            event_uid = _generate_event_uid(commodity, date_str, idx)

            # Compute relevance score
            price_count = len(event["price_mentions"]) + len(event["rate_changes"])
            signal_count = len(event["sc_signals"])
            commodity_count = len(event["commodities"])

            relevance_score = _compute_relevance_score(
                event["source_count"],
                event["article_count"],
                price_count,
                signal_count,
                commodity_count,
                max_values,
            )

            try:
                cursor.execute(insert_event_sql, (
                    event_uid,
                    commodity,
                    event.get("primary_entity_type", "commodity"),
                    event["headline"],
                    event.get("summary", ""),
                    json.dumps(event["commodities"]),
                    json.dumps(event["companies"]),
                    json.dumps(event["regions"]),
                    json.dumps(event["locations"]),
                    json.dumps(event["sc_signals"]),
                    json.dumps(event["price_mentions"]),
                    json.dumps(event["rate_changes"]),
                    event["source_count"],
                    event["article_count"],
                    json.dumps(event["unique_sources"]),
                    event["primary_article_id"],
                    event.get("event_start"),
                    event.get("event_last_seen"),
                    relevance_score,
                ))

                event_db_id = cursor.lastrowid

                # Insert source junction records
                articles = event.get("articles", [])
                primary_id = event["primary_article_id"]

                for art in articles:
                    cursor.execute(insert_source_sql, (
                        event_db_id,
                        art["article_id"],
                        1 if art["article_id"] == primary_id else 0,
                        art.get("source_name", "unknown"),
                    ))

                stored_count += 1

                logger.debug(
                    f"  Stored event '{event_uid}': "
                    f"relevance={relevance_score:.4f}, "
                    f"articles={event['article_count']}, "
                    f"sources={event['source_count']}"
                )

            except Exception as e:
                logger.error(f"Failed to store event '{event_uid}': {e}")

        conn.commit()

    logger.info(f"Step 4 complete: {stored_count}/{len(events)} events stored")
    return stored_count


# =============================================================================
# Query helpers (for API endpoints)
# =============================================================================

def query_master_events(
    limit: int = 50,
    commodity_filter: str = None,
) -> list[dict]:
    """
    Query master_events for API consumption.

    Args:
        limit: Max events to return.
        commodity_filter: Optional commodity name to filter by.

    Returns:
        List of event dicts.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        if commodity_filter:
            cursor.execute("""
                SELECT * FROM master_events
                WHERE commodities LIKE ?
                ORDER BY relevance_score DESC
                LIMIT ?
            """, (f"%{commodity_filter}%", limit))
        else:
            cursor.execute("""
                SELECT * FROM master_events
                ORDER BY relevance_score DESC
                LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()

    events = []
    for row in rows:
        event = dict(row)
        # Parse JSON arrays for API response
        for field in [
            "commodities", "companies", "regions", "locations",
            "sc_signals", "price_mentions", "rate_changes", "unique_sources"
        ]:
            if event.get(field):
                try:
                    event[field] = json.loads(event[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        events.append(event)

    return events


def query_event_by_uid(event_uid: str) -> dict | None:
    """Fetch a single event by its UID, including source articles."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Fetch event
        cursor.execute(
            "SELECT * FROM master_events WHERE event_uid = ?",
            (event_uid,)
        )
        event_row = cursor.fetchone()

        if not event_row:
            return None

        event = dict(event_row)

        # Parse JSON arrays
        for field in [
            "commodities", "companies", "regions", "locations",
            "sc_signals", "price_mentions", "rate_changes", "unique_sources"
        ]:
            if event.get(field):
                try:
                    event[field] = json.loads(event[field])
                except (json.JSONDecodeError, TypeError):
                    pass

        # Fetch source articles
        cursor.execute("""
            SELECT ra.id, ra.headline, ra.url, ra.source_name, ra.published_at,
                   mes.is_primary, mes.source_name as junction_source
            FROM master_event_sources mes
            JOIN raw_articles ra ON ra.id = mes.article_id
            WHERE mes.event_id = ?
            ORDER BY mes.is_primary DESC
        """, (event["id"],))

        event["source_articles"] = [dict(r) for r in cursor.fetchall()]

    return event


def get_pipeline_stats() -> dict:
    """Get summary statistics for the current pipeline state."""
    with get_connection() as conn:
        cursor = conn.cursor()

        stats = {}

        cursor.execute("SELECT COUNT(*) as cnt FROM raw_articles")
        stats["total_raw_articles"] = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM raw_articles WHERE processed = 1")
        stats["processed_articles"] = cursor.fetchone()["cnt"]

        cursor.execute(
            "SELECT COUNT(*) as cnt FROM extracted_entities WHERE is_sc_relevant = 1"
        )
        stats["relevant_articles"] = cursor.fetchone()["cnt"]

        cursor.execute(
            "SELECT COUNT(*) as cnt FROM extracted_entities WHERE is_sc_relevant = 0"
        )
        stats["irrelevant_articles"] = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM master_events")
        stats["total_events"] = cursor.fetchone()["cnt"]

        cursor.execute(
            "SELECT COUNT(DISTINCT event_cluster_id) as cnt FROM consolidated_articles"
        )
        stats["total_clusters"] = cursor.fetchone()["cnt"]

        cursor.execute("""
            SELECT primary_commodity, COUNT(*) as cnt
            FROM master_events
            GROUP BY primary_commodity
            ORDER BY cnt DESC
        """)
        stats["events_by_commodity"] = {
            row["primary_commodity"]: row["cnt"]
            for row in cursor.fetchall()
        }

    return stats
