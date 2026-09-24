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
    relevance_data: dict | None = None,
) -> dict | None:
    """
    Merge article, spaCy scaffold, Groq response, and dynamic relevance judgment
    into a canonical record.

    Decision logic:
    - groq_response is None → return None (article rejected / extraction failed)
    - relevance_data is provided and relevant is False → return None
    - is_supply_chain_relevant is False → return None (article not relevant)
    - score / confidence < 0.50 → return record with is_relevant=False (→ low_confidence_queue)
    - Otherwise → return fully normalized record
    """
    article_id = article.get("article_id", "unknown")

    # ------------------------------------------------------------------
    # Rejection: Groq failed entirely
    # ------------------------------------------------------------------
    if groq_response is None:
        logger.info(f"Article {article_id}: rejected — Groq extraction returned None")
        return None

    # ------------------------------------------------------------------
    # Rejection: dynamic relevance scorer marked irrelevant
    # ------------------------------------------------------------------
    if relevance_data is not None and not relevance_data.get("relevant", True):
        logger.info(
            f"Article {article_id}: rejected by dynamic relevance scorer — "
            f"reason: {relevance_data.get('reason')}"
        )
        return None

    # ------------------------------------------------------------------
    # Rejection: not supply-chain relevant (from Groq scaffold)
    # ------------------------------------------------------------------
    is_relevant = groq_response.get("is_supply_chain_relevant", True)
    if not is_relevant and relevance_data is None:
        logger.info(
            f"Article {article_id}: rejected — not supply-chain relevant "
            f"(confidence={groq_response.get('confidence', 0)})"
        )
        return None

    # ------------------------------------------------------------------
    # Extract confidence and relevance score
    # ------------------------------------------------------------------
    confidence = float(groq_response.get("confidence", 0.0))
    if relevance_data is not None:
        relevance_score = float(relevance_data.get("score", confidence))
        disruption_type = str(relevance_data.get("disruption_type") or groq_response.get("event_category", "other")).lower()
        affected_domains = relevance_data.get("affected_domains") or []
        relevance_reason = str(relevance_data.get("reason", ""))
    else:
        relevance_score = confidence
        disruption_type = str(groq_response.get("event_category", "other")).lower()
        affected_domains = []
        relevance_reason = ""

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

    # Merge any affected domains into primary commodities if not already present
    for domain in affected_domains:
        d_clean = str(domain).strip().lower()
        if d_clean and d_clean not in primary_commodities:
            primary_commodities.append(d_clean)

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
    is_record_relevant = relevance_score >= 0.50 if relevance_data is not None else confidence >= 0.40

    normalized = {
        "article_id": article.get("article_id", ""),
        "source_name": article.get("source_name", ""),
        "source_type": article.get("source_type", ""),
        "title": article.get("title", ""),
        "content_snippet": content_snippet,
        "url": article.get("url", ""),
        "published_at": article.get("published_at", ""),
        "ingested_at": now,
        "is_relevant": is_record_relevant,
        "confidence": confidence,
        "relevance_score": relevance_score,
        "disruption_type": disruption_type,
        "affected_domains": affected_domains,
        "relevance_reason": relevance_reason,
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
    if not is_record_relevant:
        normalized["is_relevant"] = False
        logger.info(
            f"Article {article_id}: low relevance score ({relevance_score:.2f}) "
            f"→ will be stored in low_confidence_queue"
        )
    else:
        logger.info(
            f"Article {article_id}: normalized successfully — "
            f"relevant=True, score={relevance_score:.2f}, "
            f"disruption_type={disruption_type}, "
            f"commodities={primary_commodities}, "
            f"relationships={len(relationships)}"
        )

    return normalized
