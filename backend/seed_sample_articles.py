"""
Seed script to insert canonical supply chain articles into master.db
and run Phase 2A (ChromaDB) and Phase 2B (Master Graph).
"""

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import MasterDB
from phase2 import run_phase2a, run_phase2b

sample_articles = [
    {
        "article_id": "a3f9c2d1e7b5f8a9c4e6d2f1b8a3c5e7",
        "source_name": "Reuters",
        "source_type": "rss",
        "title": "Houthi attacks disrupt Red Sea shipping lanes",
        "content_snippet": "Ongoing attacks by Houthi militants have forced major shipping companies to reroute vessels via Cape of Good Hope, delaying crude oil and LNG shipments.",
        "url": "https://reuters.com/business/red-sea-disruption-2025",
        "published_at": "2025-01-15T10:30:00Z",
        "ingested_at": "2025-01-15T11:00:00Z",
        "is_relevant": True,
        "confidence": 0.91,
        "event_category": "geopolitical",
        "primary_commodities": ["crude oil", "liquefied natural gas"],
        "all_entities": {
            "organizations": ["maersk", "opec"],
            "locations": ["red sea", "suez canal", "yemen", "cape of good hope"],
            "products_mentioned": ["crude oil", "lng"],
            "events_mentioned": ["attacks"],
            "money_signals": ["$90 per barrel"],
            "percent_signals": ["12% increase"],
            "entity_roles": {
                "maersk": "logistics_node",
                "red sea": "logistics_node",
                "opec": "regulatory_body",
                "yemen": "disruption_cause",
                "suez canal": "logistics_node",
                "cape of good hope": "logistics_node"
            }
        },
        "relationships": [
            ["yemen", "disrupts", "red sea"],
            ["red sea", "routes_through", "suez canal"],
            ["suez canal", "disrupts", "crude oil"],
            ["maersk", "depends_on", "red sea"],
            ["maersk", "reroutes_around", "cape of good hope"],
            ["opec", "controls_price_of", "crude oil"]
        ],
        "economic_impact_chain": [
            "Houthi militant attacks on Red Sea shipping vessels",
            "Major shipping companies reroute via Cape of Good Hope",
            "Transit time increases by 10 to 14 days",
            "Crude oil delivery delays to European markets",
            "Crude oil spot price increases",
            "Fuel costs increase globally",
            "Logistics costs increase across all industries"
        ]
    },
    {
        "article_id": "b4e8d3c2f1a5b6c7d8e9f0a1b2c3d4e5",
        "source_name": "Bloomberg",
        "source_type": "rss",
        "title": "Taiwan drought threatens global semiconductor chip supply",
        "content_snippet": "Severe drought in Taiwan restricts water supplies to major semiconductor foundries including TSMC, threatening global chip production.",
        "url": "https://bloomberg.com/news/taiwan-semiconductor-drought-2025",
        "published_at": "2025-01-16T14:20:00Z",
        "ingested_at": "2025-01-16T15:00:00Z",
        "is_relevant": True,
        "confidence": 0.88,
        "event_category": "weather",
        "primary_commodities": ["semiconductors", "silicon wafers"],
        "all_entities": {
            "organizations": ["tsmc", "apple", "nvidia"],
            "locations": ["taiwan", "hsinchu science park"],
            "products_mentioned": ["semiconductors", "chips"],
            "events_mentioned": ["drought", "water rationing"],
            "money_signals": ["$15 billion loss"],
            "percent_signals": ["15% reduction"],
            "entity_roles": {
                "tsmc": "supplier",
                "apple": "consumer",
                "nvidia": "consumer",
                "taiwan": "logistics_node"
            }
        },
        "relationships": [
            ["drought", "disrupts", "taiwan"],
            ["taiwan", "produces", "semiconductors"],
            ["tsmc", "supplies", "semiconductors"],
            ["apple", "depends_on", "semiconductors"],
            ["nvidia", "depends_on", "tsmc"]
        ],
        "economic_impact_chain": [
            "Severe drought in Taiwan reduces reservoir levels",
            "Government imposes water restrictions on Hsinchu Science Park",
            "TSMC slows semiconductor wafer fabrication",
            "Global chip shortage affects consumer electronics and automotive sectors",
            "Lead times for advanced microprocessors double"
        ]
    }
]

def seed():
    print("Seeding sample supply chain articles into master.db...")
    db = MasterDB()
    for art in sample_articles:
        success = db.insert_article(art)
        print(f"  - Article '{art['title']}': inserted={success}")
    db.close()

    print("\nRunning Phase 2A (Embeddings & ChromaDB)...")
    import asyncio
    asyncio.run(run_phase2a())

    print("\nRunning Phase 2B (Master Graph)...")
    mg = run_phase2b()
    if mg:
        stats = mg.get_graph_stats()
        print("\n=== Master Graph Population Complete! ===")
        print(f"Total Nodes: {stats['total_nodes']}")
        print(f"Total Edges: {stats['total_edges']}")
        print(f"Nodes by type: {stats['nodes_by_type']}")
        print(f"Top nodes: {stats['top_nodes_by_weight']}")

if __name__ == "__main__":
    seed()
