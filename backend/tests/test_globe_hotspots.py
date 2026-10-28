"""
ImpactChain AI - Globe Hotspots Integration Test Suite
Validates Link_Backend_Globe.md implementation across MasterGraph, API endpoints,
schema conformance, and dynamic updates.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure backend root is on sys.path
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from master_graph import MasterGraph
from app.main import app
from fastapi.testclient import TestClient

def test_master_graph_hotspots_direct():
    print("\n" + "=" * 60)
    print("TEST 1: Direct MasterGraph.get_hotspots_for_globe()")
    print("=" * 60)

    mg = MasterGraph()
    res = mg.get_hotspots_for_globe()

    assert "hotspots" in res, "Missing 'hotspots' key"
    assert "max_intensity" in res, "Missing 'max_intensity' key"
    assert "timestamp" in res, "Missing 'timestamp' key"
    assert "total_disruptions" in res, "Missing 'total_disruptions' key"
    assert len(res["hotspots"]) > 0, "Hotspots list is empty"
    assert res["total_disruptions"] == len(res["hotspots"]), "total_disruptions mismatch"

    print(f"[PASS] Retrieved {len(res['hotspots'])} hotspots, max_intensity: {res['max_intensity']}")

    # Validate each hotspot schema
    required_fields = {
        "id": str,
        "latitude": (int, float),
        "longitude": (int, float),
        "intensity": (int, float),
        "article_count": int,
        "disruption_type": str,
        "color": str,
        "pulse_strength": (int, float),
        "label": str,
    }

    for idx, h in enumerate(res["hotspots"]):
        for field, expected_type in required_fields.items():
            assert field in h, f"Hotspot {idx} ({h.get('id')}) missing field '{field}'"
            assert isinstance(h[field], expected_type), (
                f"Hotspot {idx} field '{field}' has type {type(h[field])}, expected {expected_type}"
            )

        # Validate color scale
        intensity = h["intensity"]
        color = h["color"]
        if intensity >= 0.7:
            assert color == "red", f"Expected red for intensity {intensity}, got {color}"
            assert h["pulse_strength"] == 1.0, f"Expected pulse 1.0, got {h['pulse_strength']}"
        elif intensity >= 0.4:
            assert color == "orange", f"Expected orange for intensity {intensity}, got {color}"
        elif intensity >= 0.2:
            assert color == "yellow", f"Expected yellow for intensity {intensity}, got {color}"
        else:
            assert color == "green", f"Expected green for intensity {intensity}, got {color}"

    print(f"[PASS] All {len(res['hotspots'])} hotspots strictly adhere to response schema and color scale")

def test_api_endpoints():
    print("\n" + "=" * 60)
    print("TEST 2: FastAPI HTTP Endpoints (/api/master_graph/hotspots & /api/graph/hotspots)")
    print("=" * 60)

    client = TestClient(app)

    # 1. /api/master_graph/hotspots
    resp1 = client.get("/api/master_graph/hotspots")
    assert resp1.status_code == 200, f"Expected 200, got {resp1.status_code}: {resp1.text}"
    data1 = resp1.json()
    assert "hotspots" in data1 and len(data1["hotspots"]) > 0
    print(f"[PASS] GET /api/master_graph/hotspots returned 200 OK with {len(data1['hotspots'])} hotspots")

    # 2. /api/graph/hotspots (alias)
    resp2 = client.get("/api/graph/hotspots")
    assert resp2.status_code == 200, f"Expected 200, got {resp2.status_code}: {resp2.text}"
    data2 = resp2.json()
    assert "hotspots" in data2 and len(data2["hotspots"]) == len(data1["hotspots"])
    print(f"[PASS] GET /api/graph/hotspots returned 200 OK (alias matches primary endpoint)")

def test_dynamic_graph_update():
    print("\n" + "=" * 60)
    print("TEST 3: Dynamic Ingestion Updates Hotspots in Graph")
    print("=" * 60)

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        temp_graph_path = tf.name

    try:
        mg = MasterGraph(graph_path=temp_graph_path)

        # Verify initial baseline has all 4 tiers
        init_res = mg.get_hotspots_for_globe()
        colors = {h["color"] for h in init_res["hotspots"]}
        assert "red" in colors, "Initial hotspots missing red tier"
        assert "orange" in colors, "Initial hotspots missing orange tier"
        assert "yellow" in colors, "Initial hotspots missing yellow tier"
        assert "green" in colors, "Initial hotspots missing green tier"
        print(f"[PASS] Initial baseline contains all 4 tiers: {colors}")

        # Simulate an article processed with Panama Canal logistics disruption
        test_article = {
            "article_id": "test_hotspot_article_001",
            "title": "Severe drought restricts Panama Canal vessel transits",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "disruption_type": "logistics",
            "all_entities": {
                "locations": ["panama", "panama canal"],
                "entity_roles": {"panama": "logistics_node"},
                "events_mentioned": ["drought", "transit restriction"],
            },
            "primary_commodities": ["containerized freight"],
            "relationships": [
                ["drought", "causes", "transit restriction"],
                ["transit restriction", "affects", "panama"]
            ]
        }

        # Ingest multiple articles for the region to elevate intensity to Red
        articles = [test_article] * 8
        mg.update_from_articles(articles)

        res = mg.get_hotspots_for_globe()
        panama_hotspot = next((h for h in res["hotspots"] if h["id"] in ("panama", "panama canal")), None)

        assert panama_hotspot is not None, "Panama hotspot not found after ingestion"
        assert panama_hotspot["article_count"] >= 8, f"Expected >= 8 articles, got {panama_hotspot['article_count']}"
        assert panama_hotspot["intensity"] >= 0.7, f"Expected intensity >= 0.7, got {panama_hotspot['intensity']}"
        assert panama_hotspot["color"] == "red", f"Expected color 'red', got '{panama_hotspot['color']}'"

        print(f"[PASS] Dynamic update verified: Panama intensified to {panama_hotspot['intensity']} ({panama_hotspot['color']}) with {panama_hotspot['article_count']} articles")
        print(f"  Hotspot label: {panama_hotspot['label']}")
    finally:
        temp_p = Path(temp_graph_path)
        if temp_p.exists():
            temp_p.unlink()

if __name__ == "__main__":
    test_master_graph_hotspots_direct()
    test_api_endpoints()
    test_dynamic_graph_update()
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY (100%)")
    print("=" * 60)
