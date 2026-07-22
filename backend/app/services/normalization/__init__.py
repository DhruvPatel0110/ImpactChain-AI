"""
ImpactChain AI — Normalization Pipeline Package

Exports the main pipeline orchestration function.
Import and call run_normalization_pipeline() after ingestion completes.
"""

from app.services.normalization.database import init_database
from app.services.normalization.step1_ingestion import store_raw_articles
from app.services.normalization.step2_ner_extraction import extract_entities_batch
from app.services.normalization.step3_filtering import filter_relevant_articles
from app.services.normalization.step3_clustering import cluster_and_select_primary
from app.services.normalization.step3_consolidation import consolidate_clusters
from app.services.normalization.step4_master_db import (
    store_master_events,
    query_master_events,
    query_event_by_uid,
    get_pipeline_stats,
)

from loguru import logger


def run_normalization_pipeline(
    articles: list[dict],
    fresh_db: bool = True,
) -> dict:
    """
    Run the complete 4-step normalization pipeline.

    Args:
        articles: List of article dicts from NewsAPI + RSS ingestion.
                  Expected keys: title, description, content, url, source,
                  published_at, author, keyword_queried.
        fresh_db: If True, wipe DB before starting (clean slate each run).

    Returns:
        Dict with pipeline summary stats.
    """
    logger.info("=" * 60)
    logger.info("NORMALIZATION PIPELINE START")
    logger.info("=" * 60)

    # 0. Initialize database
    init_database(fresh=fresh_db)

    # 1. Raw ingestion
    logger.info("-" * 40)
    logger.info("STEP 1: Raw Ingestion")
    inserted = store_raw_articles(articles)

    # 2. NER extraction
    logger.info("-" * 40)
    logger.info("STEP 2: NER Extraction")
    extracted = extract_entities_batch()

    # 3A. Relevance filtering
    logger.info("-" * 40)
    logger.info("STEP 3A: Relevance Filtering")
    relevant, irrelevant = filter_relevant_articles()

    # 3B/3C. Clustering + primary selection
    logger.info("-" * 40)
    logger.info("STEP 3B/3C: Clustering + Primary Selection")
    clusters = cluster_and_select_primary()

    # 3D. Consolidation
    logger.info("-" * 40)
    logger.info("STEP 3D: Entity Merging / Consolidation")
    consolidated = consolidate_clusters(clusters)

    # 4. Master DB storage
    logger.info("-" * 40)
    logger.info("STEP 4: Master DB Storage")
    stored = store_master_events(consolidated)

    # Summary
    summary = {
        "articles_received": len(articles),
        "articles_inserted": inserted,
        "articles_extracted": extracted,
        "articles_relevant": relevant,
        "articles_irrelevant": irrelevant,
        "clusters_formed": len(clusters),
        "events_stored": stored,
    }

    logger.info("=" * 60)
    logger.info("NORMALIZATION PIPELINE COMPLETE")
    for k, v in summary.items():
        logger.info(f"  {k}: {v}")
    logger.info("=" * 60)

    return summary


__all__ = [
    "run_normalization_pipeline",
    "init_database",
    "store_raw_articles",
    "extract_entities_batch",
    "filter_relevant_articles",
    "cluster_and_select_primary",
    "consolidate_clusters",
    "store_master_events",
    "query_master_events",
    "query_event_by_uid",
    "get_pipeline_stats",
]
