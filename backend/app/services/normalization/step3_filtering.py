"""
Step 3A — Supply-Chain Relevance Filter

Evaluates each extracted_entities row against 5 conditions.
If ANY condition is TRUE → is_sc_relevant = TRUE.
Otherwise → is_sc_relevant = FALSE.

Conditions:
  1. commodities_found is NOT empty
  2. orgs contains a company in COMPANY_WATCHLIST
  3. geo_locations or gpe_locations contains a known LOGISTICS_LOCATION
  4. sc_signals_found NOT empty AND quantitative_score > 0
  5. (money_mentions OR percent_mentions NOT empty) AND
     (commodities NOT empty OR org in watchlist)
"""

import json
from loguru import logger

from app.services.normalization.database import get_connection
from app.services.normalization.keywords import COMPANY_WATCHLIST, LOGISTICS_LOCATIONS


# Pre-compute lowercase sets for O(1) lookups
_WATCHLIST_LOWER = {c.lower() for c in COMPANY_WATCHLIST}
_LOGISTICS_LOWER = {loc.lower() for loc in LOGISTICS_LOCATIONS}


def _has_watchlist_company(orgs: list[str]) -> bool:
    """Check if any extracted org matches the company watchlist (case-insensitive)."""
    for org in orgs:
        if org.lower() in _WATCHLIST_LOWER:
            return True
    return False


def _has_logistics_location(geo_locations: list[str], gpe_locations: list[str]) -> bool:
    """Check if any extracted location matches known logistics locations."""
    for loc in geo_locations:
        if loc.lower() in _LOGISTICS_LOWER:
            return True
    for loc in gpe_locations:
        if loc.lower() in _LOGISTICS_LOWER:
            return True
    return False


def _evaluate_relevance(row: dict) -> tuple[bool, str]:
    """
    Evaluate supply-chain relevance for a single extracted_entities row.

    Returns:
        (is_relevant: bool, reason: str)
    """
    commodities = json.loads(row["commodities_found"] or "[]")
    orgs = json.loads(row["orgs"] or "[]")
    geo_locations = json.loads(row["geo_locations"] or "[]")
    gpe_locations = json.loads(row["gpe_locations"] or "[]")
    sc_signals = json.loads(row["sc_signals_found"] or "[]")
    money = json.loads(row["money_mentions"] or "[]")
    percent = json.loads(row["percent_mentions"] or "[]")
    q_score = row["quantitative_score"] or 0

    # Condition 1: commodities found
    if commodities:
        return True, f"COND1: commodities_found={commodities}"

    # Condition 2: org in company watchlist
    if _has_watchlist_company(orgs):
        matched = [o for o in orgs if o.lower() in _WATCHLIST_LOWER]
        return True, f"COND2: watchlist_company={matched}"

    # Condition 3: logistics location
    if _has_logistics_location(geo_locations, gpe_locations):
        all_locs = geo_locations + gpe_locations
        matched = [l for l in all_locs if l.lower() in _LOGISTICS_LOWER]
        return True, f"COND3: logistics_location={matched}"

    # Condition 4: SC signals + quantitative score > 0
    if sc_signals and q_score > 0:
        return True, f"COND4: sc_signals={sc_signals}, q_score={q_score:.1f}"

    # Condition 5: price/percent signals + (commodity or watchlist company)
    has_price_signals = bool(money or percent)
    has_commodity_or_watchlist = bool(commodities) or _has_watchlist_company(orgs)
    if has_price_signals and has_commodity_or_watchlist:
        return True, f"COND5: price_signals=True, commodity_or_watchlist=True"

    return False, "No conditions met"


def filter_relevant_articles() -> tuple[int, int]:
    """
    Run supply-chain relevance filter on all extracted_entities.

    Updates is_sc_relevant = TRUE/FALSE for each row.

    Returns:
        (relevant_count, irrelevant_count)
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Fetch all extracted entities that haven't been evaluated yet
        cursor.execute("""
            SELECT ee.id, ee.article_id, ee.orgs, ee.gpe_locations, ee.geo_locations,
                   ee.commodities_found, ee.sc_signals_found, ee.money_mentions,
                   ee.percent_mentions, ee.quantitative_score,
                   ra.headline
            FROM extracted_entities ee
            JOIN raw_articles ra ON ra.id = ee.article_id
            ORDER BY ee.id
        """)
        rows = cursor.fetchall()

    if not rows:
        logger.info("Step 3A: No entities to filter")
        return 0, 0

    logger.info(f"Step 3A: Evaluating {len(rows)} articles for SC relevance")

    relevant_count = 0
    irrelevant_count = 0

    with get_connection() as conn:
        cursor = conn.cursor()

        for row in rows:
            is_relevant, reason = _evaluate_relevance(row)

            cursor.execute(
                "UPDATE extracted_entities SET is_sc_relevant = ? WHERE id = ?",
                (1 if is_relevant else 0, row["id"])
            )

            if is_relevant:
                relevant_count += 1
                logger.debug(
                    f"  ✓ RELEVANT article {row['article_id']} "
                    f"('{(row['headline'] or '')[:50]}'): {reason}"
                )
            else:
                irrelevant_count += 1
                logger.debug(
                    f"  ✗ IRRELEVANT article {row['article_id']} "
                    f"('{(row['headline'] or '')[:50]}'): {reason}"
                )

        conn.commit()

    logger.info(
        f"Step 3A complete: {relevant_count} relevant, "
        f"{irrelevant_count} irrelevant out of {len(rows)} total"
    )
    return relevant_count, irrelevant_count
