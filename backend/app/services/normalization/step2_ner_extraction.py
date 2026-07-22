"""
Step 2 — spaCy NER Extraction

Runs all unprocessed raw_articles through spaCy NER + PhraseMatcher.
- Extracts: ORG, GPE, LOC, EVENT, PRODUCT, MONEY, PERCENT, DATE, NORP
- PhraseMatcher catches: COMMODITY_TERMS + SUPPLY_CHAIN_SIGNALS
- Computes quantitative_score per article
- Batch processes with nlp.pipe() for efficiency
- Stores results in extracted_entities table
- Marks raw_articles.processed = TRUE
"""

import json
from loguru import logger

import spacy
from spacy.matcher import PhraseMatcher

from app.services.normalization.database import get_connection
from app.services.normalization.keywords import COMMODITY_TERMS, SUPPLY_CHAIN_SIGNALS


# =============================================================================
# spaCy model + PhraseMatcher initialization (loaded once at module import)
# =============================================================================

_nlp = None
_matcher = None


def _get_nlp():
    """Lazy-load spaCy model and PhraseMatcher. Loaded once, reused."""
    global _nlp, _matcher

    if _nlp is not None:
        return _nlp, _matcher

    logger.info("Loading spaCy model: en_core_web_sm")
    _nlp = spacy.load("en_core_web_sm")

    # Build PhraseMatcher for commodity terms
    _matcher = PhraseMatcher(_nlp.vocab, attr="LOWER")

    commodity_patterns = [_nlp.make_doc(term) for term in COMMODITY_TERMS]
    _matcher.add("COMMODITY", commodity_patterns)

    sc_signal_patterns = [_nlp.make_doc(term) for term in SUPPLY_CHAIN_SIGNALS]
    _matcher.add("SC_SIGNAL", sc_signal_patterns)

    logger.info(
        f"PhraseMatcher loaded: {len(COMMODITY_TERMS)} commodity terms, "
        f"{len(SUPPLY_CHAIN_SIGNALS)} SC signal terms"
    )
    return _nlp, _matcher


# =============================================================================
# Entity extraction from a single spaCy Doc
# =============================================================================

# spaCy entity labels we care about
_ENTITY_LABELS = {"ORG", "GPE", "LOC", "EVENT", "PRODUCT", "MONEY", "PERCENT", "DATE", "NORP"}


def _extract_from_doc(doc, matcher) -> dict:
    """
    Extract named entities + PhraseMatcher matches from a processed spaCy Doc.

    Returns dict with all entity arrays + quantitative_score.
    """
    orgs = set()
    gpe_locations = set()
    geo_locations = set()
    events_named = set()
    money_mentions = set()
    percent_mentions = set()

    # Standard NER extraction
    for ent in doc.ents:
        text = ent.text.strip()
        if not text:
            continue

        if ent.label_ == "ORG":
            orgs.add(text)
        elif ent.label_ == "GPE":
            gpe_locations.add(text)
        elif ent.label_ == "LOC":
            geo_locations.add(text)
        elif ent.label_ == "EVENT":
            events_named.add(text)
        elif ent.label_ == "MONEY":
            money_mentions.add(text)
        elif ent.label_ == "PERCENT":
            percent_mentions.add(text)
        # DATE, PRODUCT, NORP — extracted but not stored separately (used in scoring)

    # PhraseMatcher extraction
    commodities_found = set()
    sc_signals_found = set()

    matches = matcher(doc)
    for match_id, start, end in matches:
        rule_id = doc.vocab.strings[match_id]
        matched_text = doc[start:end].text.strip()

        if rule_id == "COMMODITY":
            commodities_found.add(matched_text.lower())
        elif rule_id == "SC_SIGNAL":
            sc_signals_found.add(matched_text.lower())

    # Compute quantitative score
    quantitative_score = (
        (len(money_mentions) * 2.0)
        + (len(percent_mentions) * 2.0)
        + (len(orgs) * 1.0)
        + (len(commodities_found) * 1.5)
        + (len(sc_signals_found) * 1.0)
    )

    return {
        "orgs": sorted(orgs),
        "gpe_locations": sorted(gpe_locations),
        "geo_locations": sorted(geo_locations),
        "events_named": sorted(events_named),
        "commodities_found": sorted(commodities_found),
        "sc_signals_found": sorted(sc_signals_found),
        "money_mentions": sorted(money_mentions),
        "percent_mentions": sorted(percent_mentions),
        "quantitative_score": quantitative_score,
    }


# =============================================================================
# Batch extraction pipeline
# =============================================================================

def extract_entities_batch(batch_size: int = 50) -> int:
    """
    Process all unprocessed raw_articles through spaCy NER.

    1. Fetch raw_articles WHERE processed = FALSE
    2. Combine headline + summary + full_text into input text
    3. Batch through nlp.pipe()
    4. Extract entities + PhraseMatcher matches
    5. Store in extracted_entities
    6. Mark raw_articles.processed = TRUE

    Args:
        batch_size: Number of docs to process per nlp.pipe() batch.

    Returns:
        Number of articles processed.
    """
    nlp, matcher = _get_nlp()

    # Fetch unprocessed articles
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, headline, summary, full_text
            FROM raw_articles
            WHERE processed = 0
            ORDER BY id
        """)
        rows = cursor.fetchall()

    if not rows:
        logger.info("Step 2: No unprocessed articles found")
        return 0

    logger.info(f"Step 2: Processing {len(rows)} articles through spaCy NER")

    # Prepare texts for batch processing
    article_ids = []
    texts = []
    for row in rows:
        article_ids.append(row["id"])
        # Combine all text fields — headline carries most weight so put it first
        parts = []
        if row["headline"]:
            parts.append(row["headline"])
        if row["summary"]:
            parts.append(row["summary"])
        if row["full_text"]:
            parts.append(row["full_text"])
        combined = " . ".join(parts) if parts else ""
        texts.append(combined)

    # Batch process through spaCy
    insert_sql = """
        INSERT INTO extracted_entities
            (article_id, orgs, gpe_locations, geo_locations, events_named,
             commodities_found, sc_signals_found, money_mentions, percent_mentions,
             quantitative_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    update_sql = "UPDATE raw_articles SET processed = 1 WHERE id = ?"

    processed_count = 0

    with get_connection() as conn:
        cursor = conn.cursor()

        for i, doc in enumerate(nlp.pipe(texts, batch_size=batch_size)):
            article_id = article_ids[i]

            try:
                entities = _extract_from_doc(doc, matcher)

                cursor.execute(insert_sql, (
                    article_id,
                    json.dumps(entities["orgs"]),
                    json.dumps(entities["gpe_locations"]),
                    json.dumps(entities["geo_locations"]),
                    json.dumps(entities["events_named"]),
                    json.dumps(entities["commodities_found"]),
                    json.dumps(entities["sc_signals_found"]),
                    json.dumps(entities["money_mentions"]),
                    json.dumps(entities["percent_mentions"]),
                    entities["quantitative_score"],
                ))

                cursor.execute(update_sql, (article_id,))
                processed_count += 1

                # Log extraction summary for debugging
                commodity_count = len(entities["commodities_found"])
                signal_count = len(entities["sc_signals_found"])
                org_count = len(entities["orgs"])
                score = entities["quantitative_score"]

                logger.debug(
                    f"  Article {article_id}: "
                    f"commodities={commodity_count}, signals={signal_count}, "
                    f"orgs={org_count}, score={score:.1f}"
                )

            except Exception as e:
                logger.error(f"Failed NER extraction for article {article_id}: {e}")
                # Still mark as processed to avoid infinite retry loop
                cursor.execute(update_sql, (article_id,))

        conn.commit()

    logger.info(
        f"Step 2 complete: {processed_count}/{len(rows)} articles "
        f"extracted successfully"
    )
    return processed_count
