"""
ImpactChain AI — Phase 2.2: Embedding Generation

Responsible for:
  - Loading the sentence-transformers model once (all-MiniLM-L6-v2)
  - Constructing a compound semantic string per article that concentrates
    the supply-chain signal (title, commodities, entities, relationships,
    economic impact chain, event type, source)
  - Generating a 384-dimensional float vector for each compound string
  - Returning (compound_string, embedding_vector) per article

NOTE:
  - Raw article text is NOT embedded. Only the compound string is embedded.
  - Groq is NOT used here. Embedding is fully local via sentence-transformers.
  - The same model MUST be used for both ingestion (here) and query embedding
    (Phase 3) so that all vectors live in the same semantic space.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global model — loaded once, reused for all articles and queries
# ---------------------------------------------------------------------------

_model = None


def load_embedding_model():
    """
    Load the sentence-transformers model into memory.

    This must be called once before any embedding generation. The model
    (~80MB) downloads automatically on first use and is cached at
    ~/.cache/huggingface/ afterwards — no repeated downloads.

    Safe to call multiple times: re-uses the already-loaded global instance.
    """
    global _model
    if _model is not None:
        logger.debug("Embedding model already loaded — reusing existing instance.")
        return

    try:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading sentence-transformers model 'all-MiniLM-L6-v2'...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}", exc_info=True)
        raise


def _get_model():
    """Return the loaded model, raising if not yet initialised."""
    if _model is None:
        raise RuntimeError(
            "Embedding model not loaded. Call load_embedding_model() first."
        )
    return _model


# ---------------------------------------------------------------------------
# Compound string construction
# ---------------------------------------------------------------------------

def _build_compound_string(article: dict) -> str:
    """
    Construct a dense supply-chain semantic string from a normalized article.

    The compound string concentrates the signal into a single passage:
      - Title
      - Primary commodities affected
      - Entity names with their supply-chain roles
      - Relationship triples expressed as natural phrases
      - Economic impact chain as a causal narrative
      - Event category
      - Source name

    Raw article text and journalistic prose are intentionally excluded —
    they dilute the supply-chain signal with background context.

    Returns a non-empty string. Falls back to "title. Source: source_name."
    if the article is missing most structured fields.
    """
    title: str = article.get("title") or ""
    source_name: str = article.get("source_name") or "unknown"
    event_category: str = article.get("event_category") or "unknown"

    # --- Commodities ---
    primary_commodities: list = article.get("primary_commodities") or []
    commodities_str = (
        ", ".join(str(c) for c in primary_commodities if c)
        if primary_commodities
        else "unknown"
    )

    # --- Entity roles ---
    all_entities: dict = article.get("all_entities") or {}
    entity_roles: dict = all_entities.get("entity_roles") or {}
    if entity_roles:
        entities_parts = [
            f"{name} ({role.replace('_', ' ')})"
            for name, role in entity_roles.items()
            if name and role
        ]
        entities_str = ", ".join(entities_parts) if entities_parts else "none"
    else:
        entities_str = "none"

    # --- Relationships ---
    relationships: list = article.get("relationships") or []
    if relationships:
        rel_parts = []
        for triple in relationships:
            if isinstance(triple, (list, tuple)) and len(triple) == 3:
                source, rel_type, target = triple
                rel_parts.append(f"{source} {rel_type} {target}")
        relationships_str = ", ".join(rel_parts) if rel_parts else "none"
    else:
        relationships_str = "none"

    # --- Economic impact chain ---
    economic_chain: list = article.get("economic_impact_chain") or []
    if economic_chain:
        # Normalise step casing — lowercase each step to match spec example
        steps = [str(s).strip() for s in economic_chain if s]
        # Join as causal narrative: "A causes B causes C …"
        impact_str = " causes ".join(steps)
    else:
        impact_str = "unknown"

    # --- Assemble compound string ---
    compound = (
        f"{title}.\n"
        f"Commodities affected: {commodities_str}.\n"
        f"Entities: {entities_str}.\n"
        f"Relationships: {relationships_str}.\n"
        f"Economic impact: {impact_str}.\n"
        f"Event type: {event_category}.\n"
        f"Source: {source_name}."
    )

    return compound.strip()


def _minimal_fallback_string(article: dict) -> str:
    """
    Minimal compound string for articles missing most structured fields.

    Always produces a non-empty string so the encoder never receives blank input.
    """
    title = article.get("title") or "unknown article"
    source = article.get("source_name") or "unknown source"
    return f"{title}. Source: {source}."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_embedding(article: dict) -> tuple[str, list[float]]:
    """
    Generate a 384-dimensional embedding for a single normalized article.

    Process:
      1. Build compound semantic string from article fields.
      2. Encode with the loaded SentenceTransformer model.
      3. Convert numpy array → plain Python list (ChromaDB requires lists).

    Args:
        article: Normalized article dictionary (from full_json in master.db).

    Returns:
        Tuple of (compound_string: str, embedding_vector: list[float]).
        The embedding_vector has exactly 384 elements.

    Raises:
        RuntimeError: If the embedding model has not been loaded yet.
    """
    model = _get_model()

    # --- Build compound string ---
    try:
        compound_string = _build_compound_string(article)

        # Sanity check: if compound string is nearly empty, fall back
        # (can happen when almost all fields are None/empty)
        if len(compound_string.strip()) < 20:
            logger.warning(
                f"Article {article.get('article_id', 'unknown')} produced a very short "
                f"compound string — using minimal fallback."
            )
            compound_string = _minimal_fallback_string(article)

    except Exception as e:
        logger.warning(
            f"Compound string construction failed for article "
            f"{article.get('article_id', 'unknown')}: {e}. Using minimal fallback."
        )
        compound_string = _minimal_fallback_string(article)

    # --- Generate embedding ---
    try:
        embedding = model.encode(compound_string)
        # ChromaDB requires plain Python lists, not numpy arrays
        embedding_vector: list[float] = embedding.tolist()
        logger.debug(
            f"Generated embedding for article {article.get('article_id', 'unknown')} "
            f"— vector dim={len(embedding_vector)}"
        )
        return compound_string, embedding_vector

    except Exception as e:
        logger.error(
            f"Embedding generation failed for article "
            f"{article.get('article_id', 'unknown')}: {e}",
            exc_info=True,
        )
        raise
