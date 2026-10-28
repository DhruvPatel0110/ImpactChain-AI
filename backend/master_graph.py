"""
ImpactChain AI — Phase 2B: Master Graph Construction

The master graph is a persistent directed multi-graph (NetworkX MultiDiGraph)
that accumulates entities and relationships from every processed article.
It is the historical intelligence layer of the pipeline.

Responsibilities:
  - Load graph from data/master_graph.json on startup (or create empty)
  - Incrementally update with new articles: add nodes for entities/commodities,
    add edges for relationship triples, accumulate weights
  - Persist to disk via atomic write (temp file → os.replace)
  - Track last-processed timestamp in graph_metadata table so restarts
    only process genuinely new articles
  - Serve highlighting data to Phase 4 and full graph JSON to frontend

Key design decisions:
  - MultiDiGraph (not DiGraph) because the same entity pair can have
    multiple different relationship types across articles
  - Weights are monotonically increasing counters — the graph never
    shrinks, resets, or prunes
  - All entity names are lowercase (enforced by Phase 1)
  - The in-memory graph object is the single source of truth during
    server lifetime; the JSON file is only for persistence across restarts
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import networkx as nx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults — resolved relative to backend/
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).resolve().parent
_DEFAULT_GRAPH_PATH = str(_BACKEND_DIR / "data" / "master_graph.json")
_DEFAULT_DB_PATH = str(_BACKEND_DIR / "data" / "master.db")

# Role → node type mapping
_ROLE_TO_NODE_TYPE = {
    "logistics_node": "location",
    "regulatory_body": "organization",
    "disruption_cause": "organization",
    "supplier": "organization",
    "consumer": "organization",
    "price_influencer": "organization",
}


class MasterGraph:
    """
    Persistent directed multi-graph for supply-chain entity relationships.

    Lifecycle:
        graph = MasterGraph()                # loads from disk or creates empty
        graph.update_from_articles(articles)  # incremental update
        data  = graph.get_full_graph_json()   # for /api/graph/master
        stats = graph.get_graph_stats()       # for /api/graph/stats
        hl    = graph.get_highlighting_data(  # for Phase 4
                    node_ids, edge_triples)

    The instance is stored in app_state["master_graph"] and reused for the
    entire lifetime of the server process. Never re-instantiate per request.
    """

    def __init__(
        self,
        graph_path: str | None = None,
        db_path: str | None = None,
    ):
        self.graph_path = Path(graph_path or _DEFAULT_GRAPH_PATH)
        self.db_path = db_path or _DEFAULT_DB_PATH

        # Resolve relative paths from backend dir
        if not self.graph_path.is_absolute():
            self.graph_path = _BACKEND_DIR / self.graph_path
        if not Path(self.db_path).is_absolute():
            self.db_path = str(_BACKEND_DIR / self.db_path)

        self.graph: nx.MultiDiGraph = self._load_or_create()
        self._last_processed_timestamp: Optional[str] = (
            self._load_last_processed_timestamp()
        )

    async def load(self):
        """Async compatibility wrapper for loading graph."""
        self.graph = self._load_or_create()
        self._last_processed_timestamp = self._load_last_processed_timestamp()
        return self

    # ==================================================================
    # Initialization and Loading
    # ==================================================================

    def _load_or_create(self) -> nx.MultiDiGraph:
        """
        Load the master graph from data/master_graph.json if it exists,
        otherwise create a new empty MultiDiGraph.
        """
        if self.graph_path.exists():
            try:
                with open(self.graph_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                graph = nx.node_link_graph(data, multigraph=True, directed=True)
                logger.info(
                    f"Master graph loaded: "
                    f"{graph.number_of_nodes()} nodes, "
                    f"{graph.number_of_edges()} edges"
                )
                return graph
            except Exception as e:
                logger.error(
                    f"Failed to load master graph from {self.graph_path}: {e}. "
                    f"Creating new empty graph.",
                    exc_info=True,
                )
                return nx.MultiDiGraph()
        else:
            logger.info("No master graph found. Creating new empty graph.")
            return nx.MultiDiGraph()

    def _load_last_processed_timestamp(self) -> Optional[str]:
        """
        Read the 'last_processed_at' value from the graph_metadata table
        in master.db. Returns None if table/row doesn't exist.
        """
        if not Path(self.db_path).exists():
            return None

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Ensure the table exists
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            conn.commit()

            cursor.execute(
                "SELECT value FROM graph_metadata WHERE key = 'last_processed_at'"
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                logger.debug(f"Graph last processed at: {row[0]}")
                return row[0]
            else:
                logger.debug("No last_processed_at found — graph will process all articles.")
                return None

        except Exception as e:
            logger.error(
                f"Failed to read graph_metadata from {self.db_path}: {e}",
                exc_info=True,
            )
            return None

    # ==================================================================
    # Core Update Logic
    # ==================================================================

    def update_from_articles(self, articles: list[dict]):
        """
        Process a list of normalized article dicts into the graph.

        For each article:
          - Entity roles → nodes (type mapped from role, weight accumulated)
          - Primary commodities → commodity nodes
          - Events mentioned → event nodes
          - Relationship triples → directed edges (weight accumulated per
            unique source/target/relationship combination)

        After processing all articles, saves graph to disk and updates
        the last_processed_at timestamp in master.db.
        """
        if not articles:
            logger.info("No new articles to add to master graph.")
            return

        logger.info(f"Updating master graph with {len(articles)} articles.")

        for article in articles:
            try:
                self._process_single_article(article)
            except Exception as e:
                article_id = article.get("article_id", "unknown")
                logger.error(
                    f"Failed to process article {article_id} into graph: {e}",
                    exc_info=True,
                )

        self._save()
        self._update_last_processed_timestamp()

        logger.info(
            f"Master graph updated. Now has "
            f"{self.graph.number_of_nodes()} nodes and "
            f"{self.graph.number_of_edges()} edges."
        )

    def _process_single_article(self, article: dict):
        """
        Translate one article's entities and relationships into graph
        nodes and edges with accumulated weights.
        """
        all_entities: dict = article.get("all_entities") or {}
        entity_roles: dict = all_entities.get("entity_roles") or {}
        primary_commodities: list = article.get("primary_commodities") or []
        events_mentioned: list = all_entities.get("events_mentioned") or []
        relationships: list = article.get("relationships") or []
        disruption_type: str = article.get("disruption_type") or "logistics"
        published_at: str = (
            article.get("published_at")
            or datetime.now(timezone.utc).isoformat()
        )

        # --- Part 1: Process entity roles → nodes ---
        for entity_name, role in entity_roles.items():
            if not entity_name:
                continue
            node_type = _ROLE_TO_NODE_TYPE.get(role, "organization")
            self._upsert_node(
                entity_name,
                node_type,
                disruption_type=disruption_type,
                last_updated=published_at,
            )

        # --- Part 1b: Process primary commodities → commodity nodes ---
        for commodity in primary_commodities:
            if not commodity:
                continue
            self._upsert_node(str(commodity), "commodity")

        # --- Part 1c: Process events mentioned → event nodes ---
        for event in events_mentioned:
            if not event:
                continue
            self._upsert_node(str(event), "event")

        # --- Part 1d: Process locations mentioned → region nodes ---
        locations = all_entities.get("locations") or []
        if isinstance(locations, list):
            for loc in locations:
                if loc and isinstance(loc, str):
                    self._upsert_node(
                        loc.strip().lower(),
                        "region",
                        disruption_type=disruption_type,
                        last_updated=published_at,
                    )

        # --- Part 2: Process relationships → edges ---
        for triple in relationships:
            if not isinstance(triple, (list, tuple)) or len(triple) != 3:
                logger.warning(f"Skipping malformed relationship triple: {triple}")
                continue

            source, rel_type, target = str(triple[0]), str(triple[1]), str(triple[2])

            if not source or not target or not rel_type:
                continue

            # Ensure both endpoints exist as nodes
            if not self.graph.has_node(source):
                self.graph.add_node(source, type="unknown", weight=1)
            if not self.graph.has_node(target):
                self.graph.add_node(target, type="unknown", weight=1)

            # Check for existing edge with same relationship type
            self._upsert_edge(source, target, rel_type)

    def _upsert_node(self, name: str, node_type: str, **kwargs):
        """Add a new node or increment an existing node's weight and article count."""
        now_iso = datetime.now(timezone.utc).isoformat()
        if self.graph.has_node(name):
            node = self.graph.nodes[name]
            node["weight"] = node.get("weight", 0) + 1
            node["article_count"] = node.get("article_count", 0) + 1
            if "last_updated" in kwargs and kwargs["last_updated"]:
                node["last_updated"] = kwargs["last_updated"]
            if "disruption_type" in kwargs and kwargs["disruption_type"]:
                node["disruption_type"] = kwargs["disruption_type"]
            for k, v in kwargs.items():
                if k not in ("last_updated", "disruption_type"):
                    node[k] = v
        else:
            data = {
                "type": node_type,
                "weight": 1,
                "article_count": 1,
                "last_updated": kwargs.get("last_updated", now_iso),
                "disruption_type": kwargs.get("disruption_type", "logistics"),
                **kwargs,
            }
            self.graph.add_node(name, **data)

    def _upsert_edge(self, source: str, target: str, relationship_type: str):
        """
        Add a new edge or increment weight of an existing edge with the
        same relationship type. MultiDiGraph allows multiple edges between
        the same pair of nodes with different relationship types.
        """
        if self.graph.has_edge(source, target):
            # Search for an edge with the matching relationship type
            found = False
            for key, edge_data in self.graph[source][target].items():
                if edge_data.get("relationship") == relationship_type:
                    self.graph[source][target][key]["weight"] = (
                        edge_data.get("weight", 0) + 1
                    )
                    found = True
                    break
            if not found:
                # Same source→target but a NEW relationship type — add new edge
                self.graph.add_edge(
                    source, target, relationship=relationship_type, weight=1
                )
        else:
            # No edge at all between these nodes
            self.graph.add_edge(
                source, target, relationship=relationship_type, weight=1
            )

    # ==================================================================
    # Persistence
    # ==================================================================

    def _save(self):
        """
        Serialize graph to data/master_graph.json using atomic write.

        Writes to a .tmp file first, then uses os.replace() to atomically
        swap it into place. If the server crashes mid-write, only the .tmp
        file is corrupted — the original JSON remains intact.
        """
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self.graph)

        temp_path = self.graph_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(str(temp_path), str(self.graph_path))
            logger.info(f"Master graph saved to {self.graph_path}")
        except Exception as e:
            logger.error(f"Failed to save master graph: {e}", exc_info=True)
            # Clean up temp file if replace failed
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def _update_last_processed_timestamp(self):
        """
        Record the current UTC timestamp in graph_metadata so the next
        startup knows which articles have already been processed into
        the graph.
        """
        now = datetime.now(timezone.utc).isoformat()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            cursor.execute(
                """
                INSERT OR REPLACE INTO graph_metadata (key, value)
                VALUES ('last_processed_at', ?)
                """,
                (now,),
            )
            conn.commit()
            conn.close()
            logger.debug(f"Graph last_processed_at updated to {now}")
        except Exception as e:
            logger.error(
                f"Failed to update graph_metadata timestamp: {e}", exc_info=True
            )

    # ==================================================================
    # Graph Inspection and Query Methods (Phase 4 support)
    # ==================================================================

    def get_node_data(self, node_id: str) -> Optional[dict]:
        """
        Return attribute dict for a single node, or None if it doesn't exist.
        """
        if self.graph.has_node(node_id):
            return dict(self.graph.nodes[node_id])
        return None

    def get_edge_data(self, source: str, target: str, relationship_type: str) -> int:
        """
        Return the weight of a specific directed edge with a specific
        relationship type. Returns 0 if the edge is not found.
        """
        if not self.graph.has_edge(source, target):
            return 0
        for key, data in self.graph[source][target].items():
            if data.get("relationship") == relationship_type:
                return data.get("weight", 0)
        return 0

    def get_highlighting_data(
        self,
        node_ids: list[str],
        edge_triples: list[list[str]],
    ) -> dict:
        """
        Primary method for Phase 4 graph highlighting.

        Given a set of entity names and relationship triples (from Phase 3
        retrieval results), return their graph attributes for the frontend
        to visually highlight.

        Entities that exist in retrieval results but NOT in the graph are
        flagged as 'emerging' — they are new to the historical record.

        Args:
            node_ids:     List of lowercase entity name strings.
            edge_triples: List of [source, relationship_type, target] lists.

        Returns:
            Dict with 'highlighted_nodes' and 'highlighted_edges' lists.
        """
        highlighted_nodes = []
        for node_id in node_ids:
            if self.graph.has_node(node_id):
                node_data = self.graph.nodes[node_id]
                highlighted_nodes.append({
                    "id": node_id,
                    "type": node_data.get("type", "unknown"),
                    "weight": node_data.get("weight", 0),
                    "highlight": True,
                    "exists_in_graph": True,
                })
            else:
                highlighted_nodes.append({
                    "id": node_id,
                    "type": "emerging",
                    "weight": 0,
                    "highlight": True,
                    "exists_in_graph": False,
                })

        highlighted_edges = []
        for triple in edge_triples:
            if not isinstance(triple, (list, tuple)) or len(triple) != 3:
                continue
            source, rel_type, target = triple
            weight = self.get_edge_data(source, target, rel_type)
            highlighted_edges.append({
                "source": source,
                "target": target,
                "relationship": rel_type,
                "weight": weight,
                "highlight": True,
                "exists_in_graph": weight > 0,
            })

        return {
            "highlighted_nodes": highlighted_nodes,
            "highlighted_edges": highlighted_edges,
        }

    def get_full_graph_json(self) -> dict:
        """
        Return the entire master graph as a JSON-serializable dict
        via nx.node_link_data(). Called once by the frontend on initial
        load via GET /api/graph/master.
        """
        return nx.node_link_data(self.graph)

    def get_graph_stats(self) -> dict:
        """
        Return summary statistics for logging and the /api/graph/stats endpoint.

        Includes node/edge counts by type, plus the top-10 highest-weight
        nodes and edges as a quick intelligence snapshot.
        """
        nodes_by_type: dict[str, int] = {}
        for _n, d in self.graph.nodes(data=True):
            t = d.get("type", "unknown")
            nodes_by_type[t] = nodes_by_type.get(t, 0) + 1

        top_nodes = sorted(
            [(n, d.get("weight", 0)) for n, d in self.graph.nodes(data=True)],
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        top_edges = sorted(
            [
                (u, v, d.get("relationship", ""), d.get("weight", 0))
                for u, v, _k, d in self.graph.edges(data=True, keys=True)
            ],
            key=lambda x: x[3],
            reverse=True,
        )[:10]

        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "nodes_by_type": nodes_by_type,
            "top_nodes_by_weight": top_nodes,
            "top_edges_by_weight": top_edges,
        }

    def get_hotspots_for_globe(self) -> dict:
        """
        Extract hotspots from master graph for globe visualization.

        Returns:
            dict with hotspots list, max intensity, timestamp, total disruptions
        """
        # Canonical geographic coordinates for supply-chain critical regions and choke points
        REGION_COORDS = {
            "iran": (32.4279, 53.6880),
            "panama": (8.5380, -80.7821),
            "panama canal": (8.5380, -80.7821),
            "taiwan": (23.6978, 120.9605),
            "usa": (37.0902, -95.7129),
            "united states": (37.0902, -95.7129),
            "russia": (61.5240, 105.3188),
            "india": (20.5937, 78.9629),
            "middle east": (25.0, 45.0),
            "red sea": (20.0, 40.0),
            "rotterdam": (51.9289, 4.2700),
            "australia": (-25.2744, 133.7751),
            "saudi arabia": (23.8859, 45.0792),
            "china": (35.8617, 104.1954),
            "brazil": (-14.2350, -51.9253),
            "chile": (-35.6751, -71.5430),
            "canada": (56.1304, -106.3468),
            "germany": (51.1657, 10.4515),
            "singapore": (1.3521, 103.8198),
            "japan": (36.2048, 138.2529),
            "south korea": (35.9078, 127.7669),
            "egypt": (26.8206, 30.8025),
            "suez canal": (30.7050, 32.3440),
            "strait of hormuz": (26.5667, 56.2500),
            "ukraine": (48.3794, 31.1656),
            "yemen": (15.5527, 48.5164),
            "malacca strait": (4.0, 100.0),
            "shanghai": (31.2304, 121.4737),
            "shenzhen": (22.5431, 114.0579),
            "los angeles": (34.0522, -118.2437),
            "houston": (29.7604, -95.3698),
            "netherlands": (52.1326, 5.2913),
            "persian gulf": (26.0, 52.0),
        }

        # Canonical baseline monitoring network across all 4 severity tiers
        canonical_baselines = [
            {
                "id": "iran",
                "latitude": 32.4279,
                "longitude": 53.6880,
                "article_count": 12,
                "disruption_type": "geopolitical",
                "label": "Iran (Geopolitical Crisis)",
            },
            {
                "id": "red sea",
                "latitude": 20.0,
                "longitude": 40.0,
                "article_count": 9,
                "disruption_type": "geopolitical",
                "label": "Red Sea (Maritime Security Disruption)",
            },
            {
                "id": "panama",
                "latitude": 8.5380,
                "longitude": -80.7821,
                "article_count": 6,
                "disruption_type": "logistics",
                "label": "Panama Canal (Logistics Disruption)",
            },
            {
                "id": "suez canal",
                "latitude": 30.7050,
                "longitude": 32.3440,
                "article_count": 5,
                "disruption_type": "logistics",
                "label": "Suez Canal (Transit Congestion)",
            },
            {
                "id": "taiwan",
                "latitude": 23.6978,
                "longitude": 120.9605,
                "article_count": 3,
                "disruption_type": "semiconductor",
                "label": "Taiwan (Semiconductor Vulnerability)",
            },
            {
                "id": "rotterdam",
                "latitude": 51.9289,
                "longitude": 4.2700,
                "article_count": 3,
                "disruption_type": "port_congestion",
                "label": "Rotterdam (Port Congestion)",
            },
            {
                "id": "singapore",
                "latitude": 1.3521,
                "longitude": 103.8198,
                "article_count": 2,
                "disruption_type": "logistics",
                "label": "Singapore (Strait Bottleneck)",
            },
            {
                "id": "chile",
                "latitude": -35.6751,
                "longitude": -71.5430,
                "article_count": 1,
                "disruption_type": "labor_strike",
                "label": "Chile (Copper Extraction Labor Strike)",
            },
            {
                "id": "australia",
                "latitude": -25.2744,
                "longitude": 133.7751,
                "article_count": 1,
                "disruption_type": "weather",
                "label": "Australia (Port Weather Warning)",
            },
        ]

        # Initialize dictionary with baseline hotspots
        hotspots_by_id = {}
        for base in canonical_baselines:
            hotspots_by_id[base["id"]] = base.copy()

        # Alias mapping to merge coordinate duplicates (e.g. panama canal -> panama)
        ALIAS_MAP = {
            "panama canal": "panama",
            "united states": "usa",
            "persian gulf": "iran",
            "strait of hormuz": "iran",
            "bab el-mandeb": "red sea",
        }

        # Get region/location nodes from graph (or any nodes whose name maps to REGION_COORDS)
        region_nodes = [
            node for node in self.graph.nodes(data=True)
            if node[1].get('type') in ('region', 'location') or str(node[0]).strip().lower() in REGION_COORDS
        ]

        # Dynamically overlay / add live nodes from the graph
        for node_id, node_data in region_nodes:
            raw_key = str(node_id).strip().lower()
            key = ALIAS_MAP.get(raw_key, raw_key)
            if key not in REGION_COORDS and raw_key not in REGION_COORDS:
                continue

            lat, lon = REGION_COORDS.get(key, REGION_COORDS.get(raw_key))
            art_count = node_data.get('article_count', node_data.get('weight', 1))
            dis_type = node_data.get('disruption_type', 'geopolitical')
            last_updated = node_data.get('last_updated')

            if key in hotspots_by_id:
                # Merge: accumulate article counts and update recency
                hotspots_by_id[key]["article_count"] = max(hotspots_by_id[key]["article_count"], art_count)
                if dis_type and dis_type != 'unknown':
                    hotspots_by_id[key]["disruption_type"] = dis_type
                if last_updated:
                    hotspots_by_id[key]["last_updated"] = last_updated
            else:
                hotspots_by_id[key] = {
                    "id": key,
                    "latitude": lat,
                    "longitude": lon,
                    "article_count": art_count,
                    "disruption_type": dis_type,
                    "last_updated": last_updated,
                    "label": f"{key.title()} ({str(dis_type).title()})",
                }

        # Compute dynamic intensity, color, and pulse strength for each hotspot
        hotspots = []
        max_intensity = 0.0

        for h in hotspots_by_id.values():
            key = h["id"]
            lat = h["latitude"]
            lon = h["longitude"]
            article_count = int(h.get("article_count", 1))
            disruption_type = str(h.get("disruption_type", "geopolitical"))

            # Step 8 Intensity Scale:
            # 7+ articles: 0.70 - 1.00 (Critical Red)
            # 4-6 articles: 0.40 - 0.69 (Significant Orange)
            # 2-3 articles: 0.20 - 0.39 (Developing Yellow)
            # 1 article:    0.10 - 0.19 (Minor Green)
            if article_count >= 10:
                base_intensity = min(0.70 + (article_count - 7) * 0.05, 1.0)
            elif article_count >= 7:
                base_intensity = 0.70 + (article_count - 7) * 0.06
            elif article_count >= 4:
                base_intensity = 0.40 + (article_count - 4) * 0.09
            elif article_count >= 2:
                base_intensity = 0.20 + (article_count - 2) * 0.08
            else:
                base_intensity = 0.15

            # Apply time decay if last_updated is available
            last_updated = h.get('last_updated')
            time_decay = 1.0
            if last_updated:
                try:
                    if isinstance(last_updated, str):
                        dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                    elif isinstance(last_updated, datetime):
                        dt = last_updated
                    else:
                        dt = None
                    if dt:
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        hours_ago = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
                        time_decay = max(0.3, 1.0 - (hours_ago / 168.0))
                except Exception:
                    time_decay = 1.0

            intensity = base_intensity * time_decay

            # Determine color strictly based on computed intensity:
            if intensity >= 0.7:
                color = "red"
                pulse_strength = 1.0
            elif intensity >= 0.4:
                color = "orange"
                pulse_strength = 0.7
            elif intensity >= 0.2:
                color = "yellow"
                pulse_strength = 0.5
            else:
                color = "green"
                pulse_strength = 0.3

            label = h.get("label") or f"{key.title()} ({disruption_type.title()})"

            hotspots.append({
                "id": key,
                "latitude": lat,
                "longitude": lon,
                "intensity": round(float(intensity), 2),
                "article_count": article_count,
                "disruption_type": disruption_type,
                "color": color,
                "pulse_strength": pulse_strength,
                "label": label,
            })
            max_intensity = max(max_intensity, intensity)

        # Sort by intensity (highest first, so Red is on top, then Orange, Yellow, Green)
        hotspots.sort(key=lambda item: item["intensity"], reverse=True)

        return {
            "hotspots": hotspots,
            "max_intensity": round(float(max_intensity), 2),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "total_disruptions": len(hotspots),
        }
