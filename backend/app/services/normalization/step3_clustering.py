"""
Step 3B + 3C — Same-Event Detection & Primary Source Selection

Groups SC-relevant articles into event clusters using 2-pass Jaccard similarity:
  Pass 1: Jaccard(commodities) ≥ 0.70 AND within 24h → SAME CLUSTER
  Pass 2: Jaccard ≥ 0.40 AND (matching ORG OR 2+ matching SC signals) AND within 36-48h
  Unmatched → NEW cluster

Selects primary source per cluster:
  - Highest quantitative_score wins
  - Tiebreaker: SOURCE_CREDIBILITY_RANK

Stores results in consolidated_articles table.
"""

import json
import datetime
from collections import defaultdict
from loguru import logger

try:
    from dateutil import parser as dateutil_parser
except ImportError:
    dateutil_parser = None

from app.services.normalization.database import get_connection
from app.services.normalization.keywords import get_source_rank


# =============================================================================
# Jaccard similarity
# =============================================================================

def _jaccard(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def _parse_timestamp(ts_str: str) -> datetime.datetime:
    """Parse ISO timestamp string to datetime object (UTC)."""
    if not ts_str:
        return datetime.datetime.now(datetime.timezone.utc)

    try:
        if dateutil_parser:
            dt = dateutil_parser.parse(ts_str)
        else:
            dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc)


def _hours_between(dt1: datetime.datetime, dt2: datetime.datetime) -> float:
    """Absolute hours between two datetimes."""
    return abs((dt1 - dt2).total_seconds()) / 3600.0


def _get_primary_commodity(commodities: list[str]) -> str:
    """
    Determine primary commodity — the most mentioned.
    If tie, pick alphabetically first for determinism.
    If empty, return 'unknown'.
    """
    if not commodities:
        return "unknown"

    # Count occurrences (in case of duplicates in source data)
    from collections import Counter
    counts = Counter(c.lower() for c in commodities)
    max_count = max(counts.values())
    top = sorted(c for c, n in counts.items() if n == max_count)
    return top[0]


# =============================================================================
# Clustering algorithm
# =============================================================================

def _build_article_data(rows) -> list[dict]:
    """Convert DB rows into dicts with parsed fields for clustering."""
    articles = []
    for row in rows:
        commodities = set(json.loads(row["commodities_found"] or "[]"))
        orgs = set(json.loads(row["orgs"] or "[]"))
        sc_signals = set(json.loads(row["sc_signals_found"] or "[]"))
        published_at = _parse_timestamp(row["published_at"])

        articles.append({
            "article_id": row["article_id"],
            "entity_id": row["entity_id"],
            "headline": row["headline"] or "",
            "source_name": row["source_name"] or "",
            "published_at": published_at,
            "commodities": commodities,
            "commodities_lower": {c.lower() for c in commodities},
            "orgs": orgs,
            "orgs_lower": {o.lower() for o in orgs},
            "sc_signals": sc_signals,
            "quantitative_score": row["quantitative_score"] or 0.0,
            "primary_commodity": _get_primary_commodity(list(commodities)),
        })

    return articles


def _cluster_articles(articles: list[dict]) -> list[list[dict]]:
    """
    Run 2-pass clustering on articles.

    Phase 1: Group by primary_commodity, cluster within each group.
    Phase 2: Cross-group merge — try to merge clusters whose articles
             have overlapping commodities (handles 'brent' vs 'crude oil' groups).

    Returns list of clusters. Each cluster is a list of article dicts.
    """
    if not articles:
        return []

    # Sort all articles by published_at for deterministic ordering
    articles.sort(key=lambda a: a["published_at"])

    # --- Phase 1: Within-group clustering ---
    commodity_groups = defaultdict(list)
    for art in articles:
        commodity_groups[art["primary_commodity"]].append(art)

    all_clusters = []
    clustered_ids = set()

    for commodity, group in commodity_groups.items():
        logger.debug(
            f"  Clustering commodity group '{commodity}': {len(group)} articles"
        )

        local_clusters = []

        for art in group:
            if art["article_id"] in clustered_ids:
                continue

            merged = False

            for cluster in local_clusters:
                for existing in cluster:
                    matched, pass_name = _try_match(art, existing)
                    if matched:
                        cluster.append(art)
                        clustered_ids.add(art["article_id"])
                        logger.debug(
                            f"    {pass_name}: Article {art['article_id']} "
                            f"merged into cluster with article {existing['article_id']}"
                        )
                        merged = True
                        break
                if merged:
                    break

            if not merged:
                local_clusters.append([art])
                clustered_ids.add(art["article_id"])
                logger.debug(
                    f"    NEW CLUSTER: Article {art['article_id']} "
                    f"('{art['headline'][:50]}')"
                )

        all_clusters.extend(local_clusters)

    logger.debug(
        f"  After within-group clustering: {len(all_clusters)} clusters"
    )

    # --- Phase 2: Cross-group merge ---
    # Try to merge clusters from different commodity groups that overlap.
    # This catches cases like 'brent' and 'crude oil' being separate groups
    # but clearly related events.
    merged_clusters = _cross_group_merge(all_clusters)

    logger.info(
        f"  Clustering result: {len(articles)} articles -> {len(merged_clusters)} clusters"
    )
    return merged_clusters


def _cross_group_merge(clusters: list[list[dict]]) -> list[list[dict]]:
    """
    Merge clusters across commodity groups if their articles match
    via Pass 1 or Pass 2 rules.
    """
    if len(clusters) <= 1:
        return clusters

    # Use union-find approach: keep merging until stable
    merged = True
    while merged:
        merged = False
        new_clusters = []
        used = set()

        for i in range(len(clusters)):
            if i in used:
                continue

            current = list(clusters[i])

            for j in range(i + 1, len(clusters)):
                if j in used:
                    continue

                # Check if any article in cluster_i matches any in cluster_j
                should_merge = False
                for art_a in clusters[i]:
                    for art_b in clusters[j]:
                        matched, pass_name = _try_match(art_a, art_b)
                        if matched:
                            should_merge = True
                            logger.debug(
                                f"    CROSS-GROUP MERGE: "
                                f"article {art_a['article_id']} <-> "
                                f"article {art_b['article_id']} ({pass_name})"
                            )
                            break
                    if should_merge:
                        break

                if should_merge:
                    current.extend(clusters[j])
                    used.add(j)
                    merged = True

            new_clusters.append(current)
            used.add(i)

        clusters = new_clusters

    return clusters


def _try_match(art_a: dict, art_b: dict) -> tuple[bool, str]:
    """
    Try to match two articles using Pass 1 then Pass 2 rules.

    Returns (matched: bool, pass_name: str)
    """
    jaccard_score = _jaccard(art_a["commodities_lower"], art_b["commodities_lower"])
    hours_gap = _hours_between(art_a["published_at"], art_b["published_at"])

    # Pass 1: Jaccard ≥ 0.70 AND within 24h
    if jaccard_score >= 0.70 and hours_gap <= 24.0:
        return True, f"PASS1 (jaccard={jaccard_score:.2f}, gap={hours_gap:.1f}h)"

    # Pass 2: Jaccard ≥ 0.40 AND (matching ORG AND within 48h)
    if jaccard_score >= 0.40 and hours_gap <= 48.0:
        matching_orgs = art_a["orgs_lower"] & art_b["orgs_lower"]
        if matching_orgs:
            return True, (
                f"PASS2-ORG (jaccard={jaccard_score:.2f}, "
                f"gap={hours_gap:.1f}h, orgs={matching_orgs})"
            )

    # Pass 2 Alt: Jaccard ≥ 0.40 AND 2+ matching SC signals AND within 36h
    if jaccard_score >= 0.40 and hours_gap <= 36.0:
        matching_signals = art_a["sc_signals"] & art_b["sc_signals"]
        if len(matching_signals) >= 2:
            return True, (
                f"PASS2-SIGNAL (jaccard={jaccard_score:.2f}, "
                f"gap={hours_gap:.1f}h, signals={matching_signals})"
            )

    return False, ""


# =============================================================================
# Primary source selection
# =============================================================================

def _select_primary(cluster: list[dict]) -> dict:
    """
    Select primary source from a cluster.
    Highest quantitative_score wins. Tiebreaker: source credibility rank.
    """
    if len(cluster) == 1:
        return cluster[0]

    # Sort by quantitative_score DESC, then credibility rank ASC
    sorted_cluster = sorted(
        cluster,
        key=lambda a: (-a["quantitative_score"], get_source_rank(a["source_name"]))
    )

    primary = sorted_cluster[0]

    logger.debug(
        f"    PRIMARY selected: article {primary['article_id']} "
        f"(score={primary['quantitative_score']:.1f}, "
        f"source={primary['source_name']})"
    )

    return primary


# =============================================================================
# Main clustering entry point
# =============================================================================

def cluster_and_select_primary() -> list[dict]:
    """
    Run same-event detection + primary source selection.

    1. Load all is_sc_relevant = TRUE entities joined with raw_articles
    2. Group by primary_commodity
    3. Run 2-pass clustering
    4. Select primary per cluster
    5. Store in consolidated_articles table

    Returns:
        List of cluster dicts with metadata for consolidation step.
    """
    # Fetch relevant articles with their entities
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                ee.id as entity_id,
                ee.article_id,
                ee.orgs,
                ee.gpe_locations,
                ee.geo_locations,
                ee.commodities_found,
                ee.sc_signals_found,
                ee.money_mentions,
                ee.percent_mentions,
                ee.quantitative_score,
                ra.headline,
                ra.summary,
                ra.source_name,
                ra.published_at
            FROM extracted_entities ee
            JOIN raw_articles ra ON ra.id = ee.article_id
            WHERE ee.is_sc_relevant = 1
            ORDER BY ra.published_at ASC
        """)
        rows = cursor.fetchall()

    if not rows:
        logger.info("Step 3B: No SC-relevant articles to cluster")
        return []

    logger.info(f"Step 3B: Clustering {len(rows)} SC-relevant articles")

    # Build structured article data
    articles = _build_article_data(rows)

    # Run clustering
    clusters = _cluster_articles(articles)

    # Select primary for each cluster and build output
    cluster_results = []
    cluster_index_map = defaultdict(int)  # per-commodity cluster counter

    with get_connection() as conn:
        cursor = conn.cursor()

        for cluster in clusters:
            primary = _select_primary(cluster)

            # Recompute primary_commodity from ALL articles in cluster
            # (important after cross-group merging)
            all_commodities = []
            for art in cluster:
                all_commodities.extend(art.get("commodities", set()))
            primary_commodity = _get_primary_commodity(all_commodities)

            # Generate cluster ID
            cluster_index_map[primary_commodity] += 1
            idx = cluster_index_map[primary_commodity]
            date_str = primary["published_at"].strftime("%Y%m%d")
            cluster_id = f"cluster_{primary_commodity.replace(' ', '_')}_{date_str}_{idx:03d}"

            # Store in consolidated_articles
            for art in cluster:
                is_primary = (art["article_id"] == primary["article_id"])
                cursor.execute("""
                    INSERT INTO consolidated_articles
                        (event_cluster_id, article_id, is_primary)
                    VALUES (?, ?, ?)
                """, (cluster_id, art["article_id"], 1 if is_primary else 0))

            # Build cluster result dict for consolidation step
            cluster_results.append({
                "cluster_id": cluster_id,
                "primary_commodity": primary_commodity,
                "primary_article": primary,
                "articles": cluster,
                "article_count": len(cluster),
            })

            logger.debug(
                f"  Cluster '{cluster_id}': {len(cluster)} articles, "
                f"primary=article {primary['article_id']}"
            )

        conn.commit()

    logger.info(
        f"Step 3B/3C complete: {len(rows)} articles -> "
        f"{len(cluster_results)} event clusters"
    )
    return cluster_results

