"""
Step 3D — Consolidation & Entity Merging

Takes clusters from Step 3B/3C and merges entity arrays across all articles.
- Primary article provides headline + summary
- All articles contribute entities (UNION merge)
- Tracks source_count, article_count, unique_sources
- Determines primary_entity_type
- Computes event temporal bounds
"""

import json
from loguru import logger


def _determine_entity_type(
    commodities: list[str],
    companies: list[str],
    locations: list[str],
) -> str:
    """
    Determine primary_entity_type for the event.
    - 'commodity' if commodities are dominant
    - 'company' if company references dominate and few commodities
    - 'logistics_route' if locations dominate
    - 'multi' if mixed
    """
    has_commodities = len(commodities) > 0
    has_companies = len(companies) > 0
    has_locations = len(locations) > 0

    count = sum([has_commodities, has_companies, has_locations])

    if count == 0:
        return "commodity"  # default fallback
    if count >= 2:
        return "multi"
    if has_commodities:
        return "commodity"
    if has_companies:
        return "company"
    if has_locations:
        return "logistics_route"

    return "multi"


def consolidate_clusters(clusters: list[dict]) -> list[dict]:
    """
    Merge entities across all articles in each cluster.

    For each cluster:
      - Primary article → headline, summary
      - UNION merge: commodities, orgs, geo_locations, gpe, sc_signals, money, percent
      - Track: source_count, article_count, unique_sources
      - Determine: primary_entity_type, event_start, event_last_seen

    Args:
        clusters: Output from cluster_and_select_primary()

    Returns:
        List of consolidated event dicts ready for Step 4.
    """
    if not clusters:
        logger.info("Step 3D: No clusters to consolidate")
        return []

    logger.info(f"Step 3D: Consolidating {len(clusters)} event clusters")

    consolidated_events = []

    for cluster in clusters:
        primary = cluster["primary_article"]
        articles = cluster["articles"]

        # Merge all entity arrays via UNION (set operations)
        merged_commodities = set()
        merged_orgs = set()
        merged_geo_locations = set()
        merged_gpe = set()
        merged_sc_signals = set()
        merged_money = set()
        merged_percent = set()

        unique_sources = set()
        timestamps = []

        for art in articles:
            merged_commodities.update(art.get("commodities", set()))
            merged_orgs.update(art.get("orgs", set()))

            # Geo locations need to be loaded from the raw row data
            # (these were sets in the article dict from clustering)
            if isinstance(art.get("sc_signals"), set):
                merged_sc_signals.update(art["sc_signals"])

            unique_sources.add(art.get("source_name", "unknown"))
            if art.get("published_at"):
                timestamps.append(art["published_at"])

        # For geo_locations, gpe, money, percent — need to re-read from DB
        # since clustering step only kept commodities, orgs, sc_signals as sets
        from app.services.normalization.database import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            article_ids = [art["article_id"] for art in articles]
            placeholders = ",".join("?" * len(article_ids))

            cursor.execute(f"""
                SELECT geo_locations, gpe_locations, money_mentions,
                       percent_mentions, sc_signals_found
                FROM extracted_entities
                WHERE article_id IN ({placeholders})
            """, article_ids)

            for row in cursor.fetchall():
                for loc in json.loads(row["geo_locations"] or "[]"):
                    merged_geo_locations.add(loc)
                for loc in json.loads(row["gpe_locations"] or "[]"):
                    merged_gpe.add(loc)
                for m in json.loads(row["money_mentions"] or "[]"):
                    merged_money.add(m)
                for p in json.loads(row["percent_mentions"] or "[]"):
                    merged_percent.add(p)
                for s in json.loads(row["sc_signals_found"] or "[]"):
                    merged_sc_signals.add(s)

        # Also fetch headline and summary for primary article from DB
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT headline, summary FROM raw_articles WHERE id = ?
            """, (primary["article_id"],))
            primary_row = cursor.fetchone()

        headline = primary_row["headline"] if primary_row else primary.get("headline", "")
        summary = primary_row["summary"] if primary_row else ""

        # Compute temporal bounds
        event_start = min(timestamps).isoformat() if timestamps else None
        event_last_seen = max(timestamps).isoformat() if timestamps else None

        # Determine entity type
        entity_type = _determine_entity_type(
            sorted(merged_commodities),
            sorted(merged_orgs),
            sorted(merged_geo_locations),
        )

        event = {
            "cluster_id": cluster["cluster_id"],
            "primary_commodity": cluster["primary_commodity"],
            "primary_entity_type": entity_type,
            "primary_article_id": primary["article_id"],
            "headline": headline,
            "summary": summary,
            "commodities": sorted(merged_commodities),
            "companies": sorted(merged_orgs),
            "regions": sorted(merged_gpe),
            "locations": sorted(merged_geo_locations),
            "sc_signals": sorted(merged_sc_signals),
            "price_mentions": sorted(merged_money),
            "rate_changes": sorted(merged_percent),
            "source_count": len(unique_sources),
            "article_count": len(articles),
            "unique_sources": sorted(unique_sources),
            "event_start": event_start,
            "event_last_seen": event_last_seen,
            "articles": articles,  # pass through for Step 4
        }

        consolidated_events.append(event)

        logger.debug(
            f"  Consolidated '{cluster['cluster_id']}': "
            f"commodities={len(merged_commodities)}, "
            f"companies={len(merged_orgs)}, "
            f"regions={len(merged_gpe)}, "
            f"sources={len(unique_sources)}"
        )

    logger.info(f"Step 3D complete: {len(consolidated_events)} events consolidated")
    return consolidated_events
