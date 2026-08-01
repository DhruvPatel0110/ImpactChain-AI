"""
ImpactChain AI — Phase 1 Step 1.4: Merge and Normalize

Combines the original article, spaCy scaffold, and Groq response into
a single canonical normalized record for database storage.
"""

import logging
from datetime import datetime, timezone

from entity_filter import (
    filter_entity_roles,
    filter_commodities,
    filter_entities_from_scaffold,
    filter_relationships,
)

logger = logging.getLogger(__name__)


def merge_and_normalize(
    article: dict,
    spacy_scaffold: dict,
    groq_response: dict | None,
) -> dict | None:
    """
    Merge article, spaCy scaffold, and Groq response into a canonical record.

    Decision logic:
    - groq_response is None → return None (article rejected / extraction failed)
    - is_supply_chain_relevant is False → return None (article not relevant)
    - confidence < 0.40 → return record with is_relevant=False (→ low_confidence_queue)
    - Otherwise → return fully normalized record

    Args:
        article: Raw article dict from Step 1.1
        spacy_scaffold: Entity scaffold from Step 1.2
        groq_response: Parsed Groq response from Step 1.3, or None

    Returns:
        Normalized record dict, or None if article is rejected.
    """
    article_id = article.get("article_id", "unknown")

    # ------------------------------------------------------------------
    # Rejection: Groq failed entirely
    # ------------------------------------------------------------------
    if groq_response is None:
        logger.info(f"Article {article_id}: rejected — Groq extraction returned None")
        return None

    # ------------------------------------------------------------------
    # Rejection: not supply-chain relevant
    # ------------------------------------------------------------------
    is_relevant = groq_response.get("is_supply_chain_relevant", False)
    if not is_relevant:
        logger.info(
            f"Article {article_id}: rejected — not supply-chain relevant "
            f"(confidence={groq_response.get('confidence', 0)})"
        )
        return None

    # ------------------------------------------------------------------
    # Extract confidence
    # ------------------------------------------------------------------
    confidence = float(groq_response.get("confidence", 0.0))

    # ------------------------------------------------------------------
    # Build the normalized record
    # ------------------------------------------------------------------
    now = datetime.now(timezone.utc).isoformat()

    # Content snippet: first 1000 characters
    content = article.get("content") or article.get("description") or ""
    content_snippet = content[:1000]

    # Primary commodities from Groq (ensure lowercase)
    primary_commodities = groq_response.get("primary_commodities") or []
    if isinstance(primary_commodities, list):
        primary_commodities = [
            c.lower() if isinstance(c, str) else str(c).lower()
            for c in primary_commodities
        ]
    else:
        primary_commodities = []

    # Filter irrelevant commodities
    primary_commodities = filter_commodities(primary_commodities)

    # Entity roles from Groq (ensure all keys and values lowercase)
    entity_roles = groq_response.get("entity_roles") or {}
    if isinstance(entity_roles, dict):
        entity_roles = {
            k.lower(): v.lower() if isinstance(v, str) else v
            for k, v in entity_roles.items()
        }
    else:
        entity_roles = {}

    # Filter irrelevant entities and validate roles
    entity_roles = filter_entity_roles(entity_roles)

    # Relationships from Groq (ensure all entity names lowercase)
    relationships = groq_response.get("relationships") or []
    normalized_rels = []
    for triple in relationships:
        if isinstance(triple, (list, tuple)) and len(triple) == 3:
            normalized_rels.append([
                str(triple[0]).lower(),
                str(triple[1]).lower(),
                str(triple[2]).lower(),
            ])
        else:
            logger.warning(f"Article {article_id}: skipping malformed triple: {triple}")
    relationships = normalized_rels

    # Filter relationships with irrelevant entities
    relationships = filter_relationships(relationships)

    # Economic impact chain from Groq (keep exact text)
    economic_impact_chain = groq_response.get("economic_impact_chain") or []

    # Event category from Groq
    event_category = str(groq_response.get("event_category", "other")).lower()

    # spaCy entities (already lowercased in Step 1.2)
    raw_entities = spacy_scaffold.get("raw_entities", {})

    # Filter irrelevant entities from spaCy scaffold
    raw_entities = filter_entities_from_scaffold(raw_entities)

    # ------------------------------------------------------------------
    # Assemble canonical normalized record
    # ------------------------------------------------------------------
    normalized = {
        "article_id": article.get("article_id", ""),
        "source_name": article.get("source_name", ""),
        "source_type": article.get("source_type", ""),
        "title": article.get("title", ""),
        "content_snippet": content_snippet,
        "url": article.get("url", ""),
        "published_at": article.get("published_at", ""),
        "ingested_at": now,
        "is_relevant": confidence >= 0.40,  # True only if above threshold
        "confidence": confidence,
        "event_category": event_category,
        "primary_commodities": primary_commodities,
        "all_entities": {
            "organizations": raw_entities.get("organizations", []),
            "locations": raw_entities.get("locations", []),
            "products_mentioned": raw_entities.get("products_mentioned", []),
            "events_mentioned": raw_entities.get("events_mentioned", []),
            "norp_mentioned": raw_entities.get("norp_mentioned", []),
            "money_signals": raw_entities.get("money_signals", []),
            "percent_signals": raw_entities.get("percent_signals", []),
            "quantity_signals": raw_entities.get("quantity_signals", []),
            "entity_roles": entity_roles,
        },
        "relationships": relationships,
        "economic_impact_chain": economic_impact_chain,
    }

    # ------------------------------------------------------------------
    # Route based on confidence
    # ------------------------------------------------------------------
    if confidence < 0.40:
        normalized["is_relevant"] = False
        logger.info(
            f"Article {article_id}: low confidence ({confidence:.2f}) "
            f"→ will be stored in low_confidence_queue"
        )
    else:
        logger.info(
            f"Article {article_id}: normalized successfully — "
            f"relevant=True, confidence={confidence:.2f}, "
            f"category={event_category}, "
            f"commodities={primary_commodities}, "
            f"relationships={len(relationships)}"
        )

    return normalized
