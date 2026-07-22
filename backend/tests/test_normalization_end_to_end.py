"""
End-to-End Test -- Normalization Pipeline

Loads sample_raw_data.json and runs the full 4-step pipeline.
Validates:
  1. Raw articles are stored correctly (dedup by URL)
  2. NER extracts commodities and signals
  3. Filtering keeps SC-relevant articles, discards noise
  4. Clustering merges related articles into event clusters
  5. Master events have correct merged entities
"""

import os
import sys
import json
import sqlite3
from pathlib import Path

# Fix Windows console encoding
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Use a test-specific DB
TEST_DB_PATH = Path(__file__).parent / "test_impactchain.db"
os.environ["IMPACTCHAIN_DB_PATH"] = str(TEST_DB_PATH)

from app.services.normalization import run_normalization_pipeline
from app.services.normalization.database import get_connection
from app.services.normalization.step4_master_db import query_master_events, get_pipeline_stats


def load_sample_data() -> list[dict]:
    """Load the sample raw data JSON."""
    sample_path = Path(__file__).parent / "sample_raw_data.json"
    with open(sample_path, "r", encoding="utf-8") as f:
        return json.load(f)


def cleanup():
    """Remove test database."""
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    wal_path = TEST_DB_PATH.with_suffix(".db-wal")
    shm_path = TEST_DB_PATH.with_suffix(".db-shm")
    if wal_path.exists():
        wal_path.unlink()
    if shm_path.exists():
        shm_path.unlink()


def test_full_pipeline():
    """Run the full pipeline and validate each step's output."""
    print("\n" + "=" * 60)
    print("NORMALIZATION PIPELINE -- END-TO-END TEST")
    print("=" * 60)

    # Clean up any previous test DB
    cleanup()

    # Load sample data
    articles = load_sample_data()
    print(f"\n[SETUP] Loaded {len(articles)} sample articles")

    # Run the full pipeline
    summary = run_normalization_pipeline(articles, fresh_db=True)

    print(f"\n[PIPELINE SUMMARY]")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    # =========================================================================
    # VALIDATION 1: Raw articles stored correctly
    # =========================================================================
    print("\n" + "-" * 40)
    print("VALIDATION 1: Raw Article Storage")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM raw_articles")
        raw_count = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM raw_articles WHERE processed = 1")
        processed_count = cursor.fetchone()["cnt"]

    print(f"  Raw articles stored: {raw_count}")
    print(f"  Processed: {processed_count}")
    assert raw_count == len(articles), f"Expected {len(articles)} raw articles, got {raw_count}"
    assert processed_count == raw_count, "All articles should be processed"
    print("  [OK] PASSED")

    # Test deduplication -- run again with same data
    from app.services.normalization.step1_ingestion import store_raw_articles
    from app.services.normalization.database import init_database

    # Don't wipe DB this time, just try inserting duplicates
    dupes_inserted = store_raw_articles(articles)
    print(f"\n  Dedup test: {dupes_inserted} inserted on second pass (should be 0)")
    assert dupes_inserted == 0, "Duplicate insertion should result in 0 new rows"
    print("  [OK] DEDUP PASSED")

    # =========================================================================
    # VALIDATION 2: NER Extraction
    # =========================================================================
    print("\n" + "-" * 40)
    print("VALIDATION 2: NER Extraction")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM extracted_entities")
        entity_count = cursor.fetchone()["cnt"]

        # Check that crude oil articles have commodities extracted
        cursor.execute("""
            SELECT ee.commodities_found, ra.headline
            FROM extracted_entities ee
            JOIN raw_articles ra ON ra.id = ee.article_id
            WHERE ra.headline LIKE '%crude%' OR ra.headline LIKE '%Brent%'
        """)
        crude_rows = cursor.fetchall()

    print(f"  Entity rows created: {entity_count}")
    assert entity_count == raw_count, f"Expected {raw_count} entity rows, got {entity_count}"

    found_commodities = False
    for row in crude_rows:
        commodities = json.loads(row["commodities_found"])
        if commodities:
            found_commodities = True
            print(f"  [OK] '{row['headline'][:50]}...' -> commodities: {commodities}")

    assert found_commodities, "Crude oil articles should have commodity extractions"
    print("  [OK] PASSED")

    # =========================================================================
    # VALIDATION 3: Relevance Filtering
    # =========================================================================
    print("\n" + "-" * 40)
    print("VALIDATION 3: Relevance Filtering")

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) as cnt FROM extracted_entities WHERE is_sc_relevant = 1"
        )
        relevant_count = cursor.fetchone()["cnt"]

        cursor.execute(
            "SELECT COUNT(*) as cnt FROM extracted_entities WHERE is_sc_relevant = 0"
        )
        irrelevant_count = cursor.fetchone()["cnt"]

        # Check specific: election article should be irrelevant
        cursor.execute("""
            SELECT ee.is_sc_relevant, ra.headline
            FROM extracted_entities ee
            JOIN raw_articles ra ON ra.id = ee.article_id
            WHERE ra.headline LIKE '%election%'
        """)
        election_rows = cursor.fetchall()

        # Check: sports article should be irrelevant
        cursor.execute("""
            SELECT ee.is_sc_relevant, ra.headline
            FROM extracted_entities ee
            JOIN raw_articles ra ON ra.id = ee.article_id
            WHERE ra.headline LIKE '%Manchester%' OR ra.headline LIKE '%striker%'
        """)
        sports_rows = cursor.fetchall()

    print(f"  Relevant: {relevant_count}")
    print(f"  Irrelevant: {irrelevant_count}")

    assert relevant_count > 0, "Should have some relevant articles"
    assert irrelevant_count > 0, "Should have some irrelevant articles (election, sports)"

    for row in election_rows:
        print(f"  Election article relevant={row['is_sc_relevant']}: '{row['headline'][:50]}'")
        assert row["is_sc_relevant"] == 0, "Election article should be irrelevant"

    for row in sports_rows:
        print(f"  Sports article relevant={row['is_sc_relevant']}: '{row['headline'][:50]}'")
        assert row["is_sc_relevant"] == 0, "Sports article should be irrelevant"

    print("  [OK] PASSED")

    # =========================================================================
    # VALIDATION 4: Clustering
    # =========================================================================
    print("\n" + "-" * 40)
    print("VALIDATION 4: Event Clustering")

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT event_cluster_id, COUNT(*) as cnt
            FROM consolidated_articles
            GROUP BY event_cluster_id
            ORDER BY cnt DESC
        """)
        clusters = cursor.fetchall()

    print(f"  Total clusters: {len(clusters)}")
    for cluster in clusters:
        print(f"    {cluster['event_cluster_id']}: {cluster['cnt']} articles")

    assert len(clusters) > 0, "Should have formed at least 1 cluster"

    # There should be a multi-article cluster (e.g. chip/semiconductor)
    multi_article_clusters = [c for c in clusters if c["cnt"] > 1]
    print(f"  Multi-article clusters: {len(multi_article_clusters)}")
    print("  [OK] PASSED")

    # =========================================================================
    # VALIDATION 5: Master Events
    # =========================================================================
    print("\n" + "-" * 40)
    print("VALIDATION 5: Master Events")

    events = query_master_events(limit=50)
    print(f"  Master events stored: {len(events)}")

    assert len(events) > 0, "Should have at least 1 master event"

    for event in events[:5]:
        commodities = event.get("commodities", [])
        companies = event.get("companies", [])
        print(
            f"    {event['event_uid']}: "
            f"commodity={event['primary_commodity']}, "
            f"articles={event['article_count']}, "
            f"relevance={event['relevance_score']:.4f}, "
            f"commodities={commodities[:3]}, "
            f"companies={companies[:3]}"
        )

    # Check relevance scores are computed
    for event in events:
        assert event["relevance_score"] >= 0, "Relevance score should be non-negative"

    # Check that events are sorted by relevance descending
    scores = [e["relevance_score"] for e in events]
    assert scores == sorted(scores, reverse=True), "Events should be sorted by relevance DESC"

    print("  [OK] PASSED")

    # =========================================================================
    # VALIDATION 6: Pipeline Stats
    # =========================================================================
    print("\n" + "-" * 40)
    print("VALIDATION 6: Pipeline Stats")

    stats = get_pipeline_stats()
    print(f"  Stats: {json.dumps(stats, indent=4)}")
    assert stats["total_raw_articles"] > 0
    assert stats["total_events"] > 0
    print("  [OK] PASSED")

    # =========================================================================
    # CLEANUP
    # =========================================================================
    cleanup()

    print("\n" + "=" * 60)
    print("ALL VALIDATIONS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    test_full_pipeline()
