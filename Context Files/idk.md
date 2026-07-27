# ImpactChain AI — Complete Backend Pipeline Architecture

---

## Overview

This document describes the complete backend pipeline for ImpactChain AI, from raw article ingestion to structured storage in the master database, vector database, and persistent master graph. No hardcoded entity lists exist anywhere in this pipeline. Every entity, commodity, relationship, and dependency is discovered dynamically at runtime.

The pipeline has two distinct phases:

- **Phase 1: Ingestion Pipeline** — article comes in, gets processed, gets stored everywhere it needs to be
- **Phase 2: Query Pipeline** — user asks something, system retrieves, builds a temporary graph, returns structured data

---

## Tech Stack Summary

| Component | Technology | Why |
|---|---|---|
| Basic Entity Extraction | spaCy (`en_core_web_lg`) | Fast, local, no API cost, good NER for persons/orgs/locations/products |
| Relationship + Context Extraction | Groq API (`llama3-70b-8192`) | Context-aware, understands dependencies, free tier unlimited |
| Master Database (structured) | SQLite via `sqlite3` or `SQLAlchemy` | Lightweight, file-based, no server needed, persists across restarts |
| Vector Database | ChromaDB | Local, free, semantic similarity search, persistent across restarts |
| Embedding Generation | Groq Embedding API or `sentence-transformers` (`all-MiniLM-L6-v2`) | Free, fast, good semantic quality |
| Master Graph | NetworkX (`DiGraph`) + JSON persistence | In-memory graph with disk backup, no graph DB server needed |
| Article Ingestion Sources | NewsAPI + RSS feeds via `feedparser` + `aiohttp` | Dual-source, free tier, async |
| Async Runtime | Python `asyncio` + `aiohttp` | Concurrent ingestion from multiple sources simultaneously |
| API Layer | FastAPI | Async-native, lightweight, serves query endpoints |

---

## PHASE 1: INGESTION PIPELINE

### Step 1.1 — Article Ingestion (Dual Source)

**Tech:** `aiohttp`, `feedparser`, `NewsAPI Python client`

Articles arrive from two sources simultaneously using async HTTP calls:

**Source A — NewsAPI:**
The system calls the NewsAPI `/v2/top-headlines` and `/v2/everything` endpoints using broad category filters like `business`, `technology`, `science`. No keyword filters are used here. The goal is to pull a wide range of headlines and let the pipeline decide what is supply-chain relevant downstream. The free tier gives 5000 requests/month which at one call every 30 minutes is well within limits.

**Source B — RSS Feeds:**
A list of RSS feed URLs (Reuters business feed, CNBC, BBC business, Al Jazeera economy, Economic Times, Financial Express, Bloomberg public feeds, AP business) is polled using `feedparser`. RSS has no API key requirement and no rate limit. Each feed returns 10–30 articles per poll. This is the primary volume source.

Both sources are polled on server startup. Dynamic refresh scheduling comes in a later version.

Each article at this stage is a raw dictionary with fields: `title`, `description`, `content`, `source_name`, `published_at`, `url`.

Deduplication happens here using URL hashing. If the URL hash already exists in the master database, the article is dropped before any processing begins.

---

### Step 1.2 — Basic Entity Extraction (spaCy)

**Tech:** `spaCy` with `en_core_web_lg` model

The raw article text (title + description + content combined) is passed through spaCy's NLP pipeline. No custom entity lists are loaded. The model runs its own trained NER and returns entities across its standard 18 entity types.

The entity types we care about and extract from spaCy output are:

- `ORG` — organizations, companies, government bodies, international agencies
- `GPE` — countries, cities, states, geopolitical entities
- `LOC` — non-GPE locations, mountain ranges, bodies of water, geographic features, shipping routes
- `PRODUCT` — products, objects, vehicles, named items (often catches commodity names like "crude oil" in product context)
- `EVENT` — named events like wars, elections, disasters
- `NORP` — nationalities, religious groups, political groups (useful for geopolitical context)
- `MONEY` — monetary values, price mentions (useful for detecting price movement signals)
- `PERCENT` — percentage mentions (useful for detecting volatility signals)
- `QUANTITY` — measurements, which often appear in commodity/logistics context

Everything else (DATE, TIME, ORDINAL, etc.) is discarded at this stage.

The output of this step is a structured partial entity object per article:

```
{
  "article_id": "<hash>",
  "raw_entities": {
    "organizations": ["Maersk", "TSMC", "OPEC"],
    "locations": ["Red Sea", "Taiwan", "Suez Canal"],
    "products_mentioned": ["crude oil", "semiconductors"],
    "events_mentioned": ["sanctions", "earthquake"],
    "money_signals": ["$90 per barrel"],
    "percent_signals": ["12% increase"]
  }
}
```

This is NOT the final entity set. It is a scaffold that gets passed to Groq in the next step.

**What spaCy cannot do here:**
- It cannot tell you that "Red Sea" is a shipping route that affects oil logistics
- It cannot identify that "OPEC" is related to commodity supply control
- It cannot extract relationship dependencies (which entity causes what effect on another entity)
- It cannot identify supply-chain relevance

These gaps are intentional and are filled by Groq.

---

### Step 1.3 — Full Extraction via Groq (Relationships + Dependencies + Relevance)

**Tech:** Groq API, model `llama3-70b-8192`, Python `groq` client library

The Groq call receives:
- The full original article text
- The spaCy-extracted entity scaffold from Step 1.2

The system prompt instructs Groq to:
1. Ignore re-extracting basic named entities (organizations, locations, people) since spaCy already did that
2. Focus exclusively on what spaCy cannot determine: supply-chain relevance, commodity identification, dependency relationships, and economic impact chains
3. Return a strict JSON object with no explanation text, no markdown, no preamble

The user message to Groq is structured as follows:

```
System:
You are a supply chain intelligence extraction engine.
You receive a news article and a set of pre-extracted named entities from spaCy NER.
Your job is NOT to re-extract basic named entities.
Your job is ONLY to determine:
1. Whether this article is supply-chain relevant (true/false).
   Supply chain relevance means: the article describes or implies an event that 
   affects the movement, price, availability, or production of physical goods, 
   commodities, raw materials, logistics networks, or industrial output.
   Political news, celebrity news, sports, entertainment = false.
   Political news that CAUSES commodity disruption = true (gray zone, always include).
2. The primary commodity or commodities affected. 
   Extract from context. Do not use a predefined list. 
   Examples: crude oil, lithium, wheat, semiconductors, natural gas, shipping containers.
   If no commodity is clearly affected, return null.
3. The supply chain role of each spaCy-extracted entity.
   For each org, location, and product already found by spaCy, assign a role:
   - "supplier", "consumer", "logistics_node", "regulatory_body", "disruption_cause", "price_influencer"
4. Relationships between entities.
   Express as: [source_entity, relationship_type, target_entity]
   Relationship types: "disrupts", "supplies", "controls_price_of", "depends_on",
   "routes_through", "regulates", "produces", "consumes", "competes_with", "sanctions"
5. Economic impact chain.
   Express the downstream propagation as an ordered list.
   Example: ["Red Sea disruption", "shipping delays", "crude oil price increase", 
              "fuel cost increase", "logistics cost increase"]
6. Event category: one of [war, weather, policy, logistics, industrial, geopolitical, financial, other]
7. Confidence score: 0.0 to 1.0 — how confident you are this is genuinely supply-chain relevant.

Return ONLY a valid JSON object. No explanation. No markdown. No extra text.

Article:
{full article text}

spaCy Entities Already Found:
{spacy_entity_scaffold as JSON string}
```

**The expected JSON output from Groq:**

```json
{
  "is_supply_chain_relevant": true,
  "confidence": 0.91,
  "primary_commodities": ["crude oil", "liquefied natural gas"],
  "entity_roles": {
    "Maersk": "logistics_node",
    "Red Sea": "logistics_node",
    "OPEC": "regulatory_body",
    "Yemen": "disruption_cause",
    "Suez Canal": "logistics_node"
  },
  "relationships": [
    ["Yemen", "disrupts", "Red Sea"],
    ["Red Sea", "routes_through", "Suez Canal"],
    ["Suez Canal", "disrupts", "crude oil"],
    ["OPEC", "controls_price_of", "crude oil"],
    ["Maersk", "depends_on", "Red Sea"]
  ],
  "economic_impact_chain": [
    "Houthi attacks on Red Sea shipping",
    "Suez Canal route disruption",
    "Rerouting via Cape of Good Hope",
    "Shipping time +14 days",
    "Crude oil delivery delays",
    "Crude oil spot price increase",
    "Fuel cost increase globally",
    "Logistics and freight cost increase"
  ],
  "event_category": "geopolitical"
}
```

If `is_supply_chain_relevant` is `false`, the article is dropped and nothing is stored anywhere. Pipeline terminates for that article.

If `confidence` is below `0.4`, the article is tagged as `low_confidence` and stored but flagged. It does not contribute to the master graph or ChromaDB in Phase 1 — it goes into a review queue in SQLite for later inspection.

---

### Step 1.4 — Merge and Normalize

**Tech:** Pure Python

At this point, two outputs exist:
- spaCy entities (Step 1.2)
- Groq relationships + roles + impact chain (Step 1.3)

These are merged into a single normalized article record:

```json
{
  "article_id": "sha256_hash_of_url",
  "source_name": "Reuters",
  "source_type": "rss",
  "title": "Houthi attacks disrupt Red Sea shipping lanes",
  "content_snippet": "First 1000 chars of article...",
  "url": "https://...",
  "published_at": "2025-01-15T10:30:00Z",
  "ingested_at": "2025-01-15T11:00:00Z",
  "is_relevant": true,
  "confidence": 0.91,
  "event_category": "geopolitical",
  "primary_commodities": ["crude oil", "liquefied natural gas"],
  "all_entities": {
    "organizations": ["Maersk", "OPEC"],
    "locations": ["Red Sea", "Suez Canal", "Yemen"],
    "entity_roles": {
      "Maersk": "logistics_node",
      "Red Sea": "logistics_node",
      "OPEC": "regulatory_body",
      "Yemen": "disruption_cause",
      "Suez Canal": "logistics_node"
    }
  },
  "relationships": [
    ["Yemen", "disrupts", "Red Sea"],
    ["Red Sea", "routes_through", "Suez Canal"],
    ["Suez Canal", "disrupts", "crude oil"],
    ["OPEC", "controls_price_of", "crude oil"],
    ["Maersk", "depends_on", "Red Sea"]
  ],
  "economic_impact_chain": [
    "Houthi attacks on Red Sea shipping",
    "Suez Canal route disruption",
    "Crude oil delivery delays",
    "Crude oil spot price increase",
    "Logistics cost increase globally"
  ],
  "money_signals": ["$90 per barrel"],
  "percent_signals": ["12% increase"]
}
```

This normalized record is the canonical representation of the article. Everything downstream uses this.

---

### Step 1.5 — Store in Master Database (SQLite)

**Tech:** `SQLite3` (via Python `sqlite3` or `SQLAlchemy` ORM)

The master database is a SQLite file stored at `data/master.db`. It persists across server restarts. It is the ground truth for all structured article data.

**Tables:**

**`articles` table:**
Stores the full normalized article record as a JSON blob alongside key queryable fields. Fields: `article_id`, `title`, `source_name`, `source_type`, `published_at`, `ingested_at`, `event_category`, `is_relevant`, `confidence`, `full_json`.

**`entities` table:**
One row per unique entity across all articles. Fields: `entity_id`, `entity_name`, `entity_type` (organization/location/commodity/event), `first_seen_at`, `article_count`. This is how the system tracks which entities appear most frequently over time. `entity_id` is a slug of the entity name (lowercase, underscored).

**`relationships` table:**
One row per unique relationship triple. Fields: `relationship_id`, `source_entity_id`, `relationship_type`, `target_entity_id`, `first_seen_at`, `occurrence_count`. If the same relationship appears in multiple articles, `occurrence_count` is incremented rather than creating duplicate rows. This naturally weights frequent relationships as stronger.

**`economic_chains` table:**
One row per article's impact chain stored as a JSON array. Fields: `chain_id`, `article_id`, `chain_steps_json`, `primary_commodity`, `created_at`.

**`low_confidence_queue` table:**
Articles with confidence below 0.4 land here for optional manual review later.

---

### Step 1.6 — Store in ChromaDB (Vector Database)

**Tech:** `ChromaDB` (persistent mode), embedding model `all-MiniLM-L6-v2` from `sentence-transformers` or Groq's embedding endpoint

ChromaDB is initialized in persistent mode, storing its files at `data/chroma_db/`. It loads from disk on startup. A single collection named `articles` is used.

**What gets embedded:**
The embedding is generated from a semantically rich string composed of:
- Article title
- Primary commodities
- Entity names and their roles
- Economic impact chain steps joined as a sentence

This compound string is richer than embedding raw article text because it concentrates the supply-chain signal rather than diluting it with journalistic prose.

Example string that gets embedded for the Red Sea article:
```
"Houthi attacks disrupt Red Sea shipping lanes. 
Commodities affected: crude oil, liquefied natural gas. 
Entities: Maersk (logistics node), Red Sea (logistics node), OPEC (regulatory body), Yemen (disruption cause). 
Impact chain: Houthi attacks disrupts Suez Canal route, causes crude oil delivery delays, causes crude oil price increase, causes global logistics cost increase."
```

**What gets stored in ChromaDB:**
- `id`: article_id (matches master DB)
- `embedding`: vector of the compound string above
- `document`: the compound string (for human-readable retrieval context)
- `metadata`: flat key-value pairs for filtered retrieval — `source_name`, `event_category`, `primary_commodity` (first commodity only, as metadata must be flat), `published_at` (unix timestamp), `confidence`

ChromaDB metadata supports filtering during queries. For example: retrieve articles similar to a query BUT only where `event_category = "geopolitical"` and `published_at > (now - 7 days)`.

---

### Step 1.7 — Update Master Graph

**Tech:** `NetworkX` (`DiGraph`), JSON serialization via `nx.node_link_data`, stored at `data/master_graph.json`

The master graph is a directed graph maintained in memory as a NetworkX `DiGraph` object. On server startup, it is loaded from `master_graph.json`. If the file does not exist, an empty graph is created. After every article is processed, the graph is updated and the JSON file is overwritten.

**Node types and attributes:**

Each node has a `type` attribute (`commodity`, `location`, `organization`, `event_category`) and a `weight` attribute that increments by 1 each time the node appears in a new article. Highly weighted nodes are the most frequently mentioned entities across all historical articles.

**Edge types and attributes:**

Each directed edge has a `relationship` attribute (one of: `disrupts`, `supplies`, `controls_price_of`, `depends_on`, `routes_through`, `regulates`, `produces`, `consumes`, `competes_with`, `sanctions`) and a `weight` attribute that increments each time the same relationship appears in a new article. Highly weighted edges are the strongest historically observed dependencies.

**Update logic:**

For each article:
1. For each entity in `entity_roles`, add a node if it does not exist, or increment its `weight` if it does
2. For each triple in `relationships`, add a directed edge from source to target with the given relationship type if it does not exist, or increment the edge `weight` if it does
3. Serialize the updated graph to `master_graph.json`

The master graph never shrinks. It only grows. Over time it becomes a historical map of which supply chain entities are most connected and most frequently co-disrupted.

---

## PHASE 2: QUERY PIPELINE

### Step 2.1 — Receive User Query

**Tech:** FastAPI endpoint (GET or POST)

A query arrives at the FastAPI backend. It is a natural language string. Examples:
- "How does the Red Sea situation affect oil prices?"
- "What is happening with semiconductor supply?"
- "Show me disruptions affecting shipping routes"

---

### Step 2.2 — Embed the Query

**Tech:** Same embedding model used in Step 1.6 (`sentence-transformers` or Groq embedding)

The query string is embedded using the same model and parameters used during ingestion. This ensures the query vector lives in the same embedding space as the stored article vectors, making similarity meaningful.

---

### Step 2.3 — Retrieve from ChromaDB

**Tech:** ChromaDB `collection.query()`

The query embedding is used to retrieve the top-N most semantically similar articles from ChromaDB. N is configurable but defaults to 10. Optional metadata filters can be applied at this step (e.g., only last 30 days, only geopolitical category).

The result is a list of article IDs and their metadata. The metadata alone (entity roles, relationships, commodities, impact chains) is sufficient for graph construction. Full article text is not needed here.

---

### Step 2.4 — Fetch Full Records from SQLite

**Tech:** SQLite3

Using the article IDs from ChromaDB results, the system fetches the corresponding full normalized records from the `articles` table in master.db. This gives access to all relationship triples and economic impact chains for those specific articles.

---

### Step 2.5 — Build Temporary Graph (Sub-graph)

**Tech:** NetworkX

A fresh temporary `DiGraph` is constructed using only the entities and relationships extracted from the retrieved articles. This is not a subset of the master graph — it is built fresh from the retrieved article data.

This means the temp graph is fully query-scoped. If you asked about the Red Sea, it contains only nodes and edges that appeared in the 10 most semantically similar articles about the Red Sea, not the entire historical network.

The temp graph is built as follows:
1. For each retrieved article, iterate through its `entity_roles` and `relationships` from the normalized JSON
2. Add nodes with type and weight attributes
3. Add directed edges with relationship type
4. If duplicate nodes or edges appear across multiple retrieved articles, merge them and increment weight

The resulting temp graph is a focused, query-relevant sub-network.

---

### Step 2.6 — Serialize and Return

**Tech:** `nx.node_link_data()`, FastAPI JSON response

The temp graph is serialized to a JSON-compatible format using NetworkX's `node_link_data()` function. This produces a standard node-link JSON structure that any frontend graph library (D3.js, Cytoscape.js, vis.js, Sigma.js) can consume directly.

The API response also includes:
- The list of retrieved article titles and sources (provenance)
- The economic impact chains from retrieved articles (ordered step sequences)
- The primary commodities found

No LLM reasoning is involved in this step. The system returns structured graph data and the raw economic chains. The frontend is responsible for visual rendering.

---

## Data Directory Layout

```
project/
└── data/
    ├── master.db              # SQLite: all normalized article records, entities, relationships
    ├── master_graph.json      # NetworkX graph serialized: grows with each article, never resets
    └── chroma_db/             # ChromaDB persistent storage directory
        ├── chroma.sqlite3
        └── [collection files]
```

---

## Key Design Principles

**No hardcoded extraction lists anywhere.** spaCy uses its own trained model weights. Groq uses language understanding. Neither requires a commodity list, company watchlist, or logistics location list to be maintained by hand.

**Two databases serve two different purposes.** SQLite stores structured, queryable, relational data (entities, relationships, chains, article records). ChromaDB stores semantic vectors for similarity-based retrieval. They are complementary, not redundant.

**The master graph accumulates historical intelligence.** Unlike ChromaDB which stores per-article embeddings, the master graph stores aggregated relationship weights. A relationship that appears in 500 articles over a year will have edge weight 500. This is historical signal that cannot be derived from any single article alone.

**The temp graph is ephemeral and query-scoped.** It is not persisted anywhere. It is built per query, returned to the caller, and discarded.

**spaCy and Groq are complementary, not redundant.** spaCy handles fast local NER for surface-level entity identification. Groq handles the semantically hard part: relevance judgment, role assignment, relationship extraction, and impact chain generation. Calling Groq without spaCy would waste tokens on basic entity extraction. Calling spaCy without Groq would miss all relational intelligence.

---

## Known Limitations and Deferred Items

- Dynamic refresh scheduling (currently runs on startup only)
- Low confidence queue review mechanism
- Master graph pruning strategy for stale or low-weight edges (relevant after months of data)
- ChromaDB collection strategy for very large article volumes (sharding, TTL)
- Embedding model selection finalization (Groq endpoint vs local sentence-transformers)
- Relationship type vocabulary may need expansion as new event patterns emerge
