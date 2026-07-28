"""
ImpactChain AI — Phase 1 Step 1.2: spaCy Entity Extraction

Loads spaCy en_core_web_lg model ONCE at module level and provides
extract_entities_spacy() for per-article entity extraction.
"""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level model holder — loaded once, reused for all articles
# ---------------------------------------------------------------------------
nlp = None


def load_spacy_model():
    """
    Load the spaCy en_core_web_lg model into the module-level `nlp` variable.
    Call this once before processing articles. Subsequent calls are no-ops.
    """
    global nlp
    if nlp is not None:
        return

    try:
        import spacy
        from config import SPACY_MODEL

        logger.info(f"Loading spaCy model '{SPACY_MODEL}'...")
        nlp = spacy.load(SPACY_MODEL)
        logger.info(f"spaCy model '{SPACY_MODEL}' loaded successfully")
    except OSError as e:
        logger.error(
            f"spaCy model not found. Run: python -m spacy download en_core_web_lg\n"
            f"Error: {e}"
        )
        raise
    except Exception as e:
        logger.error(f"Failed to load spaCy model: {e}", exc_info=True)
        raise


# ---------------------------------------------------------------------------
# Entity type → scaffold key mapping
# ---------------------------------------------------------------------------
_TYPE_MAP = {
    "ORG":      "organizations",
    "GPE":      "locations",
    "LOC":      "locations",
    "PRODUCT":  "products_mentioned",
    "EVENT":    "events_mentioned",
    "NORP":     "norp_mentioned",
    "MONEY":    "money_signals",
    "PERCENT":  "percent_signals",
    "QUANTITY": "quantity_signals",
}

# Entity types where we keep original formatting (not lowercased)
_KEEP_ORIGINAL = {"MONEY", "PERCENT", "QUANTITY"}


def _empty_scaffold(article_id: str) -> dict:
    """Return an empty entity scaffold with all required keys."""
    return {
        "article_id": article_id,
        "raw_entities": {
            "organizations": [],
            "locations": [],
            "products_mentioned": [],
            "events_mentioned": [],
            "norp_mentioned": [],
            "money_signals": [],
            "percent_signals": [],
            "quantity_signals": [],
        },
    }


def extract_entities_spacy(article: dict) -> dict:
    """
    Extract named entities from an article using spaCy NER.

    Args:
        article: Article dictionary from Step 1.1 with keys:
                 article_id, title, description, content

    Returns:
        Entity scaffold dictionary with article_id and raw_entities.
        Returns empty scaffold on error or empty text.
    """
    article_id = article.get("article_id", "unknown")

    # Ensure model is loaded
    if nlp is None:
        load_spacy_model()

    # Combine text fields
    title = article.get("title") or ""
    description = article.get("description") or ""
    content = article.get("content") or ""
    combined_text = f"{title}. {description}. {content}".strip()

    # Handle empty text
    if not combined_text or combined_text == "..":
        logger.warning(f"Article {article_id}: empty text, returning empty scaffold")
        return _empty_scaffold(article_id)

    try:
        # Run spaCy pipeline
        doc = nlp(combined_text)

        # Build scaffold
        scaffold = _empty_scaffold(article_id)
        seen = {}  # Track seen entities per category for dedup

        for ent in doc.ents:
            label = ent.label_
            if label not in _TYPE_MAP:
                continue  # Discard unwanted entity types

            scaffold_key = _TYPE_MAP[label]

            # Determine entity text: lowercase for most, keep original for signals
            if label in _KEEP_ORIGINAL:
                entity_text = ent.text.strip()
            else:
                entity_text = ent.text.strip().lower()

            if not entity_text:
                continue

            # Deduplicate within each category
            dedup_key = (scaffold_key, entity_text.lower())
            if dedup_key in seen:
                continue
            seen[dedup_key] = True

            scaffold["raw_entities"][scaffold_key].append(entity_text)

        entity_count = sum(len(v) for v in scaffold["raw_entities"].values())
        logger.info(f"Article {article_id}: extracted {entity_count} entities via spaCy")
        return scaffold

    except Exception as e:
        logger.error(
            f"spaCy processing error for article {article_id}: {e}",
            exc_info=True,
        )
        return _empty_scaffold(article_id)
