"""
Unit and Integration Tests for Dynamic Relevance Scoring
Tests RelevanceScorer, RelevanceMonitor, MasterDB filtering, and Normalizer integration.
"""

import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure backend dir is on path
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from relevance_scorer import RelevanceScorer
from monitoring.relevance_monitor import RelevanceMonitor
from database import MasterDB
from normalizer import merge_and_normalize


# ---------------------------------------------------------------------------
# Test RelevanceScorer Unit & Mock Tests
# ---------------------------------------------------------------------------

def test_relevance_scorer_cache():
    scorer = RelevanceScorer(groq_api_key="mock_key")
    headline = "Test Headline"
    summary = "Test summary description"
    entities = ["oil", "tanker"]

    # Pre-populate cache
    cache_key = scorer._build_cache_key(headline, entities)
    cached_val = {
        "relevant": True,
        "score": 0.95,
        "reason": "Cached disruption",
        "disruption_type": "logistics",
        "affected_domains": ["oil"],
    }
    scorer.cache[cache_key] = cached_val

    result = scorer.score_article(headline, summary, entities)
    assert result == cached_val
    assert result["relevant"] is True
    assert result["disruption_type"] == "logistics"

    # Test clear_cache
    scorer.clear_cache()
    assert len(scorer.cache) == 0


@patch("groq.Groq")
def test_relevance_scorer_true_positive(mock_groq_class):
    # Setup mock Groq response for true positive
    mock_client = MagicMock()
    mock_groq_class.return_value = mock_client

    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = """
    {
        "relevant": true,
        "score": 0.92,
        "reason": "Iran restricts oil tanker navigation through Strait of Hormuz",
        "disruption_type": "geopolitical",
        "affected_domains": ["crude oil", "shipping"]
    }
    """
    mock_completion.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_completion

    scorer = RelevanceScorer(groq_api_key="mock_key")
    result = scorer.score_article(
        headline="Iran blocks Strait of Hormuz shipping lane amid tensions",
        summary="Middle East geopolitical tensions escalate as Iran restricts crude oil shipping routes.",
        entities=["iran", "crude oil", "shipping lanes"],
    )

    assert result["relevant"] is True
    assert result["score"] >= 0.9
    assert result["disruption_type"] == "geopolitical"
    assert "crude oil" in result["affected_domains"]


@patch("groq.Groq")
def test_relevance_scorer_false_positive(mock_groq_class):
    # Setup mock Groq response for false positive (Ed Sheeran concert with semiconductor tech)
    mock_client = MagicMock()
    mock_groq_class.return_value = mock_client

    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = """
    {
        "relevant": false,
        "score": 0.05,
        "reason": "Entertainment news featuring hologram technology; no physical supply chain disruption.",
        "disruption_type": "none",
        "affected_domains": []
    }
    """
    mock_completion.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_completion

    scorer = RelevanceScorer(groq_api_key="mock_key")
    result = scorer.score_article(
        headline="Ed Sheeran's new concert uses hologram semiconductor technology",
        summary="The singer showcases cutting-edge semiconductor visual tech during his global tour.",
        entities=["semiconductor", "technology", "ed sheeran"],
    )

    assert result["relevant"] is False
    assert result["score"] < 0.5
    assert result["disruption_type"] == "none"
    assert result["affected_domains"] == []


# ---------------------------------------------------------------------------
# Test RelevanceMonitor
# ---------------------------------------------------------------------------

def test_relevance_monitor():
    monitor = RelevanceMonitor()

    # Record 3 articles: 2 relevant (geopolitical, logistics), 1 irrelevant
    monitor.record(
        {"title": "Iran blocks Strait"},
        is_relevant=True,
        score=0.9,
        disruption_type="geopolitical",
    )
    monitor.record(
        {"title": "Port strike in Rotterdam"},
        is_relevant=True,
        score=0.85,
        disruption_type="logistics",
    )
    monitor.record(
        {"title": "Ed Sheeran Concert"},
        is_relevant=False,
        score=0.1,
        disruption_type="none",
    )

    stats = monitor.get_stats()
    assert stats["total_ingested"] == 3
    assert stats["total_relevant"] == 2
    assert stats["total_filtered"] == 1
    assert stats["by_disruption_type"]["geopolitical"] == 1
    assert stats["by_disruption_type"]["logistics"] == 1
    assert abs(stats["filtering_ratio"] - (1 / 3)) < 0.01

    report = monitor.report()
    assert "33.3%" in report["filtering_ratio"]


# ---------------------------------------------------------------------------
# Test Normalizer with Dynamic Relevance Data
# ---------------------------------------------------------------------------

def test_normalizer_with_relevance_data():
    article = {
        "article_id": "test_art_123",
        "title": "Red Sea Shipping Halted",
        "description": "Attacks force shipping reroutes around Cape of Good Hope.",
        "url": "https://example.com/news/1",
        "published_at": "2026-01-01T12:00:00Z",
    }
    spacy_scaffold = {
        "raw_entities": {
            "organizations": ["maersk"],
            "locations": ["red sea", "cape of good hope"],
        }
    }
    groq_response = {
        "is_supply_chain_relevant": True,
        "confidence": 0.85,
        "primary_commodities": ["container freight"],
        "entity_roles": {"maersk": "logistics_node"},
        "relationships": [["maersk", "reroutes_around", "cape of good hope"]],
        "economic_impact_chain": ["Attacks occur", "Ships reroute", "Freight rates spike"],
        "event_category": "geopolitical",
    }
    relevance_data = {
        "relevant": True,
        "score": 0.94,
        "reason": "Confirmed shipping route closure and rerouting",
        "disruption_type": "logistics",
        "affected_domains": ["shipping", "freight"],
    }

    normalized = merge_and_normalize(article, spacy_scaffold, groq_response, relevance_data)
    assert normalized is not None
    assert normalized["is_relevant"] is True
    assert normalized["relevance_score"] == 0.94
    assert normalized["disruption_type"] == "logistics"
    assert "shipping" in normalized["primary_commodities"]
    assert normalized["relevance_reason"] == "Confirmed shipping route closure and rerouting"


def test_normalizer_rejects_irrelevant():
    article = {
        "article_id": "test_art_456",
        "title": "Ed Sheeran Concert",
        "description": "Fun concert with lights.",
        "url": "https://example.com/news/2",
    }
    spacy_scaffold = {"raw_entities": {"organizations": ["sony"]}}
    groq_response = {"is_supply_chain_relevant": True, "confidence": 0.3}
    relevance_data = {
        "relevant": False,
        "score": 0.05,
        "reason": "Entertainment news",
        "disruption_type": "none",
        "affected_domains": [],
    }

    normalized = merge_and_normalize(article, spacy_scaffold, groq_response, relevance_data)
    assert normalized is None


# ---------------------------------------------------------------------------
# Test MasterDB Filter Queries
# ---------------------------------------------------------------------------

def test_database_fetch_with_filter():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_master.db")
        db = MasterDB(db_path=db_path)

        # Insert 1 high-relevance geopolitical article
        art1 = {
            "article_id": "id_1",
            "title": "Oil Pipeline Explosion",
            "source_name": "Reuters",
            "source_type": "rss",
            "published_at": "2026-02-01T00:00:00Z",
            "is_relevant": True,
            "confidence": 0.95,
            "relevance_score": 0.95,
            "disruption_type": "industrial_failure",
            "url": "https://example.com/1",
            "all_entities": {"entity_roles": {"pipeline_corp": "supplier"}},
            "relationships": [],
            "economic_impact_chain": ["Explosion halts oil flow"],
            "primary_commodities": ["crude oil"],
        }
        db.insert_article(art1)

        # Insert 1 low-relevance article (is_relevant=False)
        art2 = {
            "article_id": "id_2",
            "title": "Celebrity Tech Gadget",
            "source_name": "TechBlog",
            "source_type": "rss",
            "published_at": "2026-02-02T00:00:00Z",
            "is_relevant": False,
            "confidence": 0.2,
            "relevance_score": 0.2,
            "disruption_type": "none",
            "url": "https://example.com/2",
            "all_entities": {},
            "relationships": [],
            "economic_impact_chain": [],
            "primary_commodities": [],
        }
        db.insert_article(art2)

        # Query relevant only (min_score=0.5)
        results = db.fetch_articles_with_filter(relevant_only=True, min_score=0.5)
        assert len(results) == 1
        assert results[0]["article_id"] == "id_1"

        # Query by disruption_type
        ind_results = db.fetch_articles_with_filter(disruption_type="industrial_failure")
        assert len(ind_results) == 1
        assert ind_results[0]["title"] == "Oil Pipeline Explosion"

        geo_results = db.fetch_articles_with_filter(disruption_type="geopolitical")
        assert len(geo_results) == 0

        # Query including non-relevant
        all_results = db.fetch_articles_with_filter(relevant_only=False, min_score=0.0)
        assert len(all_results) == 2

        db.close()


def test_api_articles_and_monitoring():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.get("/api/monitoring/relevance")
    assert response.status_code == 200
    data = response.json()
    assert "total_ingested" in data
    assert "filtering_ratio" in data

    response = client.get("/api/articles?relevant_only=true&min_score=0.5")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


if __name__ == "__main__":
    print("Running test_relevance_scorer_cache...")
    test_relevance_scorer_cache()
    print("[PASS] test_relevance_scorer_cache passed")

    print("Running test_relevance_scorer_true_positive...")
    test_relevance_scorer_true_positive()
    print("[PASS] test_relevance_scorer_true_positive passed")

    print("Running test_relevance_scorer_false_positive...")
    test_relevance_scorer_false_positive()
    print("[PASS] test_relevance_scorer_false_positive passed")

    print("Running test_relevance_monitor...")
    test_relevance_monitor()
    print("[PASS] test_relevance_monitor passed")

    print("Running test_normalizer_with_relevance_data...")
    test_normalizer_with_relevance_data()
    print("[PASS] test_normalizer_with_relevance_data passed")

    print("Running test_normalizer_rejects_irrelevant...")
    test_normalizer_rejects_irrelevant()
    print("[PASS] test_normalizer_rejects_irrelevant passed")

    print("Running test_database_fetch_with_filter...")
    test_database_fetch_with_filter()
    print("[PASS] test_database_fetch_with_filter passed")

    print("Running test_api_articles_and_monitoring...")
    test_api_articles_and_monitoring()
    print("[PASS] test_api_articles_and_monitoring passed")

    print("\nALL DYNAMIC FILTERING TESTS PASSED SUCCESSFULLY! [PASS]")

