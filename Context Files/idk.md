# ImpactChain AI — Complete Backend Pipeline Architecture

---

## Overview

Four-phase pipeline. No hardcoded entity lists anywhere. Every entity, commodity, relationship, and dependency is discovered dynamically at runtime.

- **Phase 1** — Article arrives, gets processed by spaCy then Groq, merged and stored in master SQLite DB
- **Phase 2** — Master DB contents are converted to embeddings, stored in ChromaDB, and the master graph is built and persisted locally
- **Phase 3** — Query arrives, gets embedded, ChromaDB retrieves relevant records, full records fetched from master DB
- **Phase 4** — Master graph is loaded, relevant nodes and edges from Phase 3 results are highlighted and returned

Phase 1 and Phase 2 are both triggered on server startup and run sequentially. Phase 3 and Phase 4 are triggered per user query and run sequentially.

---

## Tech Stack

| Component | Technology | Why |
|---|---|---|
| Basic Entity Extraction | spaCy `en_core_web_lg` | Fast, local, no API cost, handles standard NER well |
| Relationship + Relevance Extraction | Groq API `llama3-70b-8192` | Context-aware, understands dependencies, free tier unlimited |
| Master Database | SQLite via `sqlite3` or `SQLAlchemy` | Lightweight, file-based, persists across restarts, no server process needed |
| Vector Database | ChromaDB (persistent mode) | Local, free, semantic similarity search, persists across restarts |
| Embedding Generation | `sentence-transformers` `all-MiniLM-L6-v2` | Runs fully locally, zero API cost, good semantic quality, consistent across ingestion and query |
| Master Graph (in-memory) | NetworkX `DiGraph` | Industry standard graph library, fast traversal, flexible node/edge attributes |
| Master Graph (on-disk) | JSON via `nx.node_link_data()` | Human-readable, lightweight, no graph DB server needed |
| Article Ingestion | NewsAPI + RSS via `feedparser` + `aiohttp` | Dual-source, free tier, async concurrent polling |
| Async Runtime | Python `asyncio` + `aiohttp` | Concurrent ingestion from multiple sources simultaneously |
| API Layer | FastAPI | Async-native, lightweight, serves query endpoints to frontend |

---

## Data Directory Layout

```
project/
└── data/
    ├── master.db                  # SQLite: normalized articles, entities, relationships, chains
    ├── master_graph.json          # NetworkX graph: grows with each article, never resets
    └── chroma_db/                 # ChromaDB persistent storage: grows with each article
        ├── chroma.sqlite3
        └── [ChromaDB collection files]
```

All three files persist across server restarts. On startup, all three are loaded from disk before any new ingestion begins.

---

## PHASE 1: INGESTION — Article to Master DB

### Step 1.1 — Dual Source Article Ingestion

**Tech:** `aiohttp`, `feedparser`, `newsapi-python`

Both sources are polled concurrently using `asyncio`. This means RSS feeds and NewsAPI are queried at the same time, not sequentially.

**Source A — NewsAPI:**
The system calls `/v2/top-headlines` with broad category parameters: `business`, `technology`, `science`, `general`. No keyword search parameters are passed. The goal is to pull the widest possible set of current headlines and let downstream processing decide relevance. The free tier gives 5000 requests/month. At one startup poll per day, that is 5000/30 = 166 articles batches per month, well within limits.

**Source B — RSS Feeds:**
RSS feed URLs are hardcoded as a URL list (not a keyword list — this is a list of feed endpoints, not content filters). Recommended feeds: Reuters business, CNBC economy, BBC business, Al Jazeera economy, Economic Times, Financial Express, Bloomberg public RSS, AP business, WSJ economy RSS, Mint, Business Standard. `feedparser` parses each feed and returns entries with `title`, `summary`, `link`, `published`. RSS has no API key and no rate limit.

Each article at the end of this step is a raw Python dictionary:

```json
{
  "title": "Houthi attacks disrupt Red Sea shipping lanes",
  "description": "Ongoing attacks by Houthi militants have forced major shipping companies...",
  "content": "Full article body text...",
  "source_name": "Reuters",
  "source_type": "rss",
  "published_at": "2025-01-15T10:30:00Z",
  "url": "https://reuters.com/...",
  "article_id": "a3f9c2d1e7b5f8a9c4e6d2f1b8a3c5e7"
}
```

**Article ID Generation and Deduplication:**

An immutable `article_id` is generated immediately upon article receipt. The `article_id` is a SHA-256 hash of the article URL. This ensures:
- Same URL always produces the same `article_id` (deterministic)
- The `article_id` never changes across the article's lifecycle
- URLs are the unique key; if the same URL is ingested twice, it has the same `article_id`

Before any processing begins, the `article_id` is checked against the `article_id` column in the `articles` table of master.db. If a record with that `article_id` already exists, the article is dropped entirely and never proceeds to Steps 1.2, 1.3, 1.4, or 1.5. This prevents reprocessing the same article across multiple server restarts or overlapping polls.

This deduplication is done at the SQL level by checking the `article_id` column for existence, not by scanning URLs. This is faster and avoids any URL formatting inconsistencies (trailing slashes, query params, etc.).

---

### Step 1.2 — Basic Entity Extraction (spaCy)

**Tech:** `spaCy` with `en_core_web_lg` model, loaded once at server startup and reused for every article

The combined text of `title + description + content` is passed through the spaCy NLP pipeline. No custom components, no custom entity rulers, no keyword lists. The model uses its own trained weights.

Entity types extracted and kept:

- `ORG` — companies, government bodies, international organizations, agencies
- `GPE` — countries, cities, states, territories
- `LOC` — non-political geographic features: seas, canals, straits, mountain ranges, ports
- `PRODUCT` — named products and goods (often catches commodity names in commercial contexts)
- `EVENT` — named events: wars, disasters, elections, summits
- `NORP` — nationalities, political groups, religious groups (geopolitical context)
- `MONEY` — monetary values and price mentions (price signal detection)
- `PERCENT` — percentage values (volatility signal detection)
- `QUANTITY` — measurements and volumes (useful in logistics and commodity context)

All other entity types (DATE, TIME, ORDINAL, CARDINAL, LAW, LANGUAGE, WORK_OF_ART, FAC) are discarded.

The output of Step 1.2 is a partial entity scaffold, not the final entity set:

```json
{
  "article_id": "a3f9c2d1...",
  "raw_entities": {
    "organizations": ["Maersk", "OPEC", "Houthi"],
    "locations": ["Red Sea", "Suez Canal", "Yemen", "Cape of Good Hope"],
    "products_mentioned": ["crude oil", "LNG"],
    "events_mentioned": ["attacks", "sanctions"],
    "norp_mentioned": ["Houthi"],
    "money_signals": ["$90 per barrel", "$2.1 billion"],
    "percent_signals": ["12% increase", "8% drop"],
    "quantity_signals": ["2 million barrels"]
  }
}
```

This scaffold is passed as-is to Groq in Step 1.3. spaCy's job ends here.

---

### Step 1.3 — Relationship and Relevance Extraction (Groq)

**Tech:** Groq API, model `llama3-70b-8192`, Python `groq` client, API key from `GROQ_API_KEY` environment variable in `.env`

Groq receives two things: the full article text and the spaCy scaffold from Step 1.2. Groq is explicitly told not to re-extract basic named entities because spaCy already handled that. Its job is everything spaCy cannot do: supply-chain relevance judgment, commodity identification, entity role assignment, relationship extraction, and economic impact chain generation.

**System Prompt sent to Groq:**

```
You are a supply chain intelligence extraction engine.

You will receive a news article and a set of named entities already extracted by spaCy NER.

Your job is NOT to re-extract organizations, locations, or people. spaCy has already done that.

Your job is ONLY to determine the following:

1. SUPPLY CHAIN RELEVANCE
   Decide if this article is supply-chain relevant. Return true or false.
   Supply chain relevance means the article describes or implies an event that affects
   the movement, price, availability, or production of any physical good, commodity,
   raw material, logistics network, transportation route, or industrial output.
   
   Return true for: commodity disruptions, shipping route issues, factory closures,
   trade sanctions, natural disasters affecting logistics, port closures, energy supply
   changes, agricultural disruptions, semiconductor shortages, fuel price changes,
   labor strikes at logistics or industrial facilities, trade policy changes.
   
   Return true for gray zone cases: political events in commodity-producing regions,
   government policy changes that indirectly restrict trade, elections in resource-heavy
   countries, conflict in regions with major shipping routes.
   
   Return false for: celebrity news, sports, entertainment, purely domestic political
   scandals unrelated to trade or industry, general crime news, health news unrelated
   to industrial or logistics disruption.

2. CONFIDENCE SCORE
   Return a float between 0.0 and 1.0 representing how confident you are in the
   supply-chain relevance judgment. High confidence = clearly relevant or clearly
   irrelevant. Low confidence = genuinely ambiguous.

3. PRIMARY COMMODITIES AFFECTED
   Identify which commodities are affected by the events in this article.
   Do not use a predefined list. Extract from context.
   Common examples: crude oil, natural gas, LNG, semiconductors, lithium, cobalt,
   wheat, corn, soybeans, shipping containers, copper, aluminum, steel, rare earth metals.
   Return as an array. Return null if no commodity is clearly affected.

4. ENTITY ROLES
   For each entity already found by spaCy (organizations and locations), assign a
   supply chain role. Roles must be one of:
   "supplier" — produces or originates the commodity
   "consumer" — buys or uses the commodity
   "logistics_node" — a route, port, canal, or transit point
   "regulatory_body" — controls policy, price, or access
   "disruption_cause" — the entity or actor causing the disruption
   "price_influencer" — influences commodity pricing without directly supplying or consuming
   
   Only assign roles to entities that have a clear supply chain role in THIS article.
   Skip entities that are incidental mentions.

5. RELATIONSHIPS
   Express relationships between entities as triples: [source, relationship_type, target]
   Relationship types must be one of:
   "disrupts", "supplies", "controls_price_of", "depends_on", "routes_through",
   "regulates", "produces", "consumes", "competes_with", "sanctions", "reroutes_around"
   
   Only include relationships that are explicitly stated or strongly implied by the article.
   Do not infer relationships that are not present in the article.

6. ECONOMIC IMPACT CHAIN
   Describe the downstream propagation of this event as an ordered list of steps.
   Start from the triggering event and end at the furthest downstream economic effect
   that is reasonably implied by the article.
   Each step should be a short descriptive phrase.
   Maximum 10 steps.

7. EVENT CATEGORY
   Classify the event as exactly one of:
   war, weather, policy, logistics, industrial, geopolitical, financial, other

Return ONLY a valid JSON object. No explanation text. No markdown formatting. No backticks.
No preamble. No postamble. The response must be directly parseable by Python json.loads().
```

**User message sent to Groq:**

```
Article:
{full article text here}

spaCy Entities Already Extracted:
{spacy_scaffold as JSON string}
```

**Expected JSON response from Groq:**

```json
{
  "is_supply_chain_relevant": true,
  "confidence": 0.91,
  "primary_commodities": ["crude oil", "liquefied natural gas"],
  "entity_roles": {
    "maersk": "logistics_node",
    "red sea": "logistics_node",
    "opec": "regulatory_body",
    "yemen": "disruption_cause",
    "suez canal": "logistics_node",
    "cape of good hope": "logistics_node"
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
    "Shipping freight rates increase sharply",
    "Crude oil and LNG delivery delays to European markets",
    "Crude oil spot price increases",
    "Fuel costs increase globally",
    "Logistics and freight costs increase across all industries",
    "Consumer goods prices rise due to increased shipping costs"
  ],
  "event_category": "geopolitical"
}
```

**Rejection logic:**
- If `is_supply_chain_relevant` is `false`: article is dropped entirely. Nothing stored anywhere.
- If `confidence` is below `0.40`: article stored in `low_confidence_queue` table in SQLite only. Does not proceed to Phase 2 processing (no embedding, no graph contribution).
- If Groq returns invalid JSON or fails: article is stored as-is in a `failed_extractions` table with the raw Groq response for debugging. Does not proceed further.

---

### Step 1.4 — Merge and Normalize

**Tech:** Pure Python

The spaCy scaffold (Step 1.2) and Groq output (Step 1.3) are merged into one canonical normalized article record. This is the single source of truth for the article going forward. Both upstream databases (SQLite and ChromaDB) and the master graph are built from this record, never from raw article text or intermediate outputs.

**CRITICAL NORMALIZATION RULE — Entity Name Standardization:**

ALL extracted entity names must be converted to lowercase before storage anywhere. This applies to:
- All organization names from spaCy and Groq: "Maersk" → "maersk", "OPEC" → "opec"
- All location names: "Red Sea" → "red sea", "Suez Canal" → "suez canal"
- All commodity names: "Crude Oil" → "crude oil", "LNG" → "lng"
- All event names: "Sanctions" → "sanctions"
- Entity names in `entity_roles` dictionary keys: all lowercase
- Entity names in relationship triples: all lowercase (both source and target)
- Entity names in the master graph: all nodes stored as lowercase strings

This ensures that "crude oil", "Crude Oil", and "CRUDE OIL" are treated as the same entity across all phases. Without this standardization, Phase 4 highlighting will fail to match nodes correctly, ChromaDB entity references will be inconsistent, and the master graph will contain duplicate nodes for the same real-world entity.

**Canonical normalized record structure:**

```json
{
  "article_id": "a3f9c2d1e7b5f8a9c4e6d2f1b8a3c5e7",
  "source_name": "Reuters",
  "source_type": "rss",
  "title": "Houthi attacks disrupt Red Sea shipping lanes",
  "content_snippet": "First 1000 characters of article text",
  "url": "https://reuters.com/...",
  "published_at": "2025-01-15T10:30:00Z",
  "ingested_at": "2025-01-15T11:00:00Z",
  "is_relevant": true,
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
}
```

---

### Step 1.5 — Store in Master Database (SQLite)

**Tech:** `sqlite3` or `SQLAlchemy`, file at `data/master.db`

The master database is the structured ground truth for everything in the pipeline. It is append-only in normal operation. Records are never deleted unless manually purged.

**`articles` table:**
One row per article. Stores `article_id`, `title`, `source_name`, `source_type`, `published_at`, `ingested_at`, `event_category`, `is_relevant`, `confidence`, and `full_json` (the entire canonical normalized record as a JSON string). The `full_json` column is what Phase 3 fetches when reconstructing full records from article IDs.

**`entities` table:**
One row per unique entity name across all articles. Stores `entity_id` (slug), `entity_name`, `entity_type` (organization / location / commodity / event), `first_seen_at`, `article_count`. When an entity appears in a new article, if it already exists in this table its `article_count` is incremented. This gives a historical frequency signal for each entity.

**`relationships` table:**
One row per unique relationship triple. Stores `source_entity_id`, `relationship_type`, `target_entity_id`, `first_seen_at`, `occurrence_count`. When the same triple appears in a new article, `occurrence_count` is incremented rather than inserting a duplicate row. Relationship strength is implicitly encoded in `occurrence_count`.

**`economic_chains` table:**
One row per article. Stores `article_id`, `chain_steps_json` (the impact chain array as JSON), `primary_commodity`, `created_at`. This table exists for fast lookups of impact chains by commodity without needing to deserialize `full_json` from the articles table.

**`low_confidence_queue` table:**
Articles with confidence below 0.40. Stores `article_id`, `title`, `confidence`, `raw_groq_response`, `created_at`. Does not participate in any downstream processing.

**`failed_extractions` table:**
Articles where Groq returned invalid JSON or the API call failed. Stores `article_id`, `title`, `error_message`, `raw_groq_response`, `created_at`.

Phase 1 ends here. The article is now fully normalized and stored in SQLite.

---

## PHASE 2: EMBEDDING AND GRAPH CONSTRUCTION

Phase 2 runs after Phase 1 completes on server startup. It reads from master.db and writes to ChromaDB and master_graph.json. It is NOT run during Phase 1 ingestion. The separation is intentional: ingestion and intelligence layer construction are decoupled.

On subsequent server startups, Phase 2 only processes articles that were added since the last time it ran. It checks the ChromaDB collection for existing article IDs and skips any article that already has an embedding stored.

---

### Step 2.1 — Read All Relevant Articles from Master DB

**Tech:** SQLite3

All rows from the `articles` table where `is_relevant = true` and `confidence >= 0.40` are fetched. The `full_json` column is deserialized back into Python dictionaries. This gives the complete set of canonical normalized records.

On a fresh startup this is all historical articles. On subsequent startups it is only new articles not yet in ChromaDB.

---

### Step 2.2 — Generate Embeddings

**Tech:** `sentence-transformers` library, model `all-MiniLM-L6-v2`

The model is loaded once and reused for all articles in this batch and for all future query embeddings. Using the same model for both ingestion and querying is mandatory — they must live in the same vector space for similarity to be meaningful.

**What gets embedded per article:**

A compound semantic string is constructed from the canonical record. This string concentrates the supply-chain signal from the article into a single dense passage. Raw article text is NOT embedded because it dilutes the signal with journalistic prose, quotes, and background context irrelevant to supply chain analysis.

The compound string template:

```
{title}.
Commodities affected: {primary_commodities joined by comma}.
Entities: {entity_name} ({entity_role}) for each entity in entity_roles.
Relationships: {source} {relationship_type} {target} for each relationship triple.
Economic impact: {economic_impact_chain joined as narrative sentence}.
Event type: {event_category}.
Source: {source_name}.
```

Example compound string for the Red Sea article (note: all entity names in lowercase):

```
Houthi attacks disrupt Red Sea shipping lanes.
Commodities affected: crude oil, liquefied natural gas.
Entities: maersk (logistics node), red sea (logistics node), opec (regulatory body), yemen (disruption cause), suez canal (logistics node), cape of good hope (logistics node).
Relationships: yemen disrupts red sea, red sea routes through suez canal, suez canal disrupts crude oil, maersk depends on red sea, opec controls price of crude oil.
Economic impact: Houthi attacks on Red Sea vessels causes rerouting via Cape of Good Hope causes transit time increase causes crude oil delivery delays causes crude oil price increase causes global fuel cost increase.
Event type: geopolitical.
Source: Reuters.
```

This string is passed to `sentence-transformers` and returns a 384-dimensional float vector.

---

### Step 2.3 — Store in ChromaDB

**Tech:** ChromaDB persistent client, collection named `supply_chain_articles`

ChromaDB is initialized pointing to `data/chroma_db/`. If the collection `supply_chain_articles` already exists (from a previous run), it is loaded. If not, it is created.

Per article, the following is stored:

- `id`: the article_id (SHA-256 hash of URL). This is the foreign key back to master.db.
- `embedding`: the 384-dimensional vector from Step 2.2.
- `document`: the compound semantic string used to generate the embedding. Stored for human-readable inspection during debugging.
- `metadata`: a flat dictionary of filterable fields. ChromaDB metadata values must be strings, integers, or floats — no nested objects or arrays.

```json
{
  "source_name": "Reuters",
  "source_type": "rss",
  "event_category": "geopolitical",
  "primary_commodity": "crude oil",
  "published_at": 1736939400,
  "confidence": 0.91
}
```

`primary_commodity` stores only the first commodity from the array because ChromaDB metadata must be flat scalar values.

After storing all articles from the current batch, ChromaDB flushes to disk automatically in persistent mode. No manual save call is needed.

---

### Step 2.4 — Build and Persist Master Graph

**Tech:** NetworkX `DiGraph`, `nx.node_link_data()` for serialization, JSON file at `data/master_graph.json`

On first server startup, the master graph is built from scratch from all articles in master.db. On subsequent startups, the master graph is loaded from `master_graph.json` and only new articles (those not yet reflected in the graph) are processed to update it.

To track which articles have been added to the graph, a separate `graph_metadata` table in SQLite stores the last article ingestion timestamp at which the graph was updated.

**Graph structure:**

Nodes represent entities. Each node has:
- `id`: the entity name (e.g., "crude oil", "Red Sea", "Maersk")
- `type`: one of `commodity`, `location`, `organization`, `event`
- `weight`: integer, incremented by 1 each time this entity appears in any article

Edges represent relationships. Each directed edge has:
- `source`: entity name
- `target`: entity name
- `relationship`: the relationship type string (e.g., "disrupts", "supplies")
- `weight`: integer, incremented by 1 each time this exact triple appears in any article

**Build logic per article:**

For each entity in `entity_roles`: if the node does not exist, create it with `weight=1` and assign its `type` based on its role (disruption_cause and regulatory_body are mapped to `organization`, logistics_node is mapped to `location`, commodities are mapped to `commodity`). If the node already exists, increment its `weight` by 1.

For each triple in `relationships`: if the directed edge does not exist between source and target with that relationship type, create it with `weight=1`. If the edge already exists, increment its `weight` by 1.

**Persistence:**

After processing all new articles, the graph is serialized using `nx.node_link_data(graph)` which produces a JSON-serializable dictionary. This is written to `data/master_graph.json`. The file is overwritten completely on each save.

On next startup, the graph is restored using `nx.node_link_graph(data)` applied to the loaded JSON.

The master graph never shrinks. Nodes and edges are only added or have their weights incremented. Over time, edge weights represent historical relationship frequency and node weights represent historical entity mention frequency. This is the intelligence layer that enables pattern detection, anomaly detection, and trend analysis in future phases.

Phase 2 ends here. ChromaDB and master_graph.json are now fully up to date.

---

## PHASE 3: QUERY — RETRIEVAL AND RECORD FETCH

Phase 3 is triggered per user query via a FastAPI endpoint. It runs every time a user asks something.

---

### Step 3.1 — Receive Query via API

**Tech:** FastAPI, HTTP POST endpoint `/api/query`

Request body:

```json
{
  "query": "How does the Red Sea situation affect oil prices?",
  "top_k": 10,
  "filters": {
    "event_category": "geopolitical",
    "days_back": 30
  }
}
```

`top_k` defaults to 10 if not provided. `filters` is optional and can be empty. `days_back` translates to a ChromaDB metadata filter on `published_at` unix timestamp.

---

### Step 3.2 — Embed the Query

**Tech:** Same `sentence-transformers` model instance loaded at startup (`all-MiniLM-L6-v2`)

The query string is embedded using the same model and same parameters used during Phase 2. The resulting vector lives in the same 384-dimensional space as all stored article embeddings. This is what makes cosine similarity meaningful.

No prompt engineering or preprocessing is applied to the query before embedding. It is embedded as-is.

---

### Step 3.3 — Retrieve from ChromaDB

**Tech:** ChromaDB `collection.query()`

The query embedding is passed to ChromaDB along with `top_k` and any metadata filters. ChromaDB returns the `top_k` most similar articles by cosine similarity, along with their IDs, distances, and stored metadata.

The returned distances are cosine distances, not similarities. Lower distance = more similar. Articles with distance above 0.8 are considered low-relevance and optionally filtered out before proceeding.

The primary output of this step is a list of `article_id` values and their ChromaDB metadata, ordered from most to least similar.

---

### Step 3.4 — Fetch Full Records from Master DB

**Tech:** SQLite3

The article IDs from Step 3.3 are used to fetch the corresponding `full_json` values from the `articles` table in master.db. The JSON strings are deserialized back into Python dictionaries.

This gives the complete normalized records for all retrieved articles, including:
- All entity names and roles
- All relationship triples
- Full economic impact chains
- Source metadata

These records are the primary output of Phase 3. They are returned directly to the caller as structured JSON and also passed to Phase 4 for graph highlighting.

**Phase 3 API response structure:**

```json
{
  "query": "How does the Red Sea situation affect oil prices?",
  "retrieved_count": 10,
  "results": [
    {
      "article_id": "a3f9c2d1e7b5f8a9c4e6d2f1b8a3c5e7",
      "title": "Houthi attacks disrupt Red Sea shipping lanes",
      "source_name": "Reuters",
      "published_at": "2025-01-15T10:30:00Z",
      "similarity_score": 0.94,
      "primary_commodities": ["crude oil", "liquefied natural gas"],
      "economic_impact_chain": ["...", "..."],
      "entity_roles": { "...": "..." },
      "relationships": [["...", "...", "..."]]
    }
  ],
  "aggregated_commodities": ["crude oil", "liquefied natural gas", "shipping containers"],
  "aggregated_entities": ["red sea", "maersk", "suez canal", "yemen", "opec"],
  "highlighted_node_ids": ["crude oil", "red sea", "maersk", "suez canal", "yemen", "opec"],
  "highlighted_edge_ids": [
    ["yemen", "disrupts", "red sea"],
    ["red sea", "routes_through", "suez canal"],
    ["suez canal", "disrupts", "crude oil"]
  ]
}
```

The `highlighted_node_ids` and `highlighted_edge_ids` fields are pre-computed here by aggregating all entity names and relationship triples across all retrieved records. These are passed directly to Phase 4.

---

## PHASE 4: GRAPH HIGHLIGHTING

Phase 4 runs immediately after Phase 3 returns its results, in the same request lifecycle.

---

### Step 4.1 — Load Master Graph from Memory

**Tech:** NetworkX `DiGraph`

The master graph is loaded once at server startup and held in memory for the lifetime of the server process. It is not reloaded per query. Phase 4 reads directly from the in-memory NetworkX object.

This means graph access is instant — no file I/O per query.

---

### Step 4.2 — Identify Relevant Nodes and Edges

**Tech:** Pure Python, NetworkX graph attribute access

The `highlighted_node_ids` and `highlighted_edge_ids` computed in Phase 3 Step 3.4 are used here.

For nodes: iterate through `highlighted_node_ids` and verify each exists in the master graph. Only nodes that exist in the graph are included. Nodes that appear in the retrieved articles but have never been stored in the graph (which should not happen in normal operation) are flagged as missing.

For edges: iterate through `highlighted_edge_ids` (each being a [source, relationship, target] triple) and verify each edge exists in the master graph. Only edges that exist are included.

Additionally, for each highlighted node, the system fetches the node's `weight` from the master graph. For each highlighted edge, it fetches the edge's `weight`. These weights are returned to the frontend as signals for visual emphasis — higher weight means more historically significant.

---

### Step 4.3 — Serialize and Return Graph Highlighting Data

**Tech:** Pure Python dict construction, FastAPI JSON response

The master graph itself is NOT serialized and sent to the frontend. Only the highlighting metadata is sent. The frontend is responsible for rendering the master graph separately (it should receive the full master graph once on initial load and cache it). Per-query, only the highlighting data is sent.

Highlighting response appended to the Phase 3 API response:

```json
{
  "graph_highlight": {
    "highlighted_nodes": [
      { "id": "crude oil", "type": "commodity", "weight": 842, "highlight": true },
      { "id": "red sea", "type": "location", "weight": 631, "highlight": true },
      { "id": "maersk", "type": "organization", "weight": 214, "highlight": true },
      { "id": "suez canal", "type": "location", "weight": 588, "highlight": true },
      { "id": "yemen", "type": "organization", "weight": 197, "highlight": true }
    ],
    "highlighted_edges": [
      { "source": "yemen", "target": "red sea", "relationship": "disrupts", "weight": 143, "highlight": true },
      { "source": "red sea", "target": "suez canal", "relationship": "routes_through", "weight": 289, "highlight": true },
      { "source": "suez canal", "target": "crude oil", "relationship": "disrupts", "weight": 201, "highlight": true }
    ]
  }
}
```

The frontend uses this to visually highlight the relevant portion of the master graph without rebuilding or replacing it. All non-highlighted nodes and edges remain visible but visually dimmed. The highlighted portion is the query-relevant sub-network glowing within the full historical graph.

---

## Separate Endpoint: Full Master Graph for Initial Frontend Load

**Tech:** FastAPI GET endpoint `/api/graph/master`

On frontend initialization, the full master graph is fetched once via this endpoint. The master graph is serialized using `nx.node_link_data()` and returned as JSON. The frontend stores this and renders it. All subsequent queries only return highlighting data (Phase 4 output), not the full graph again. This avoids sending the full graph on every query.

---

## Key Design Principles

**Phase 1 and Phase 2 are decoupled.** Ingestion writes to SQLite only. Embedding and graph construction read from SQLite and write to ChromaDB and the graph file. This means if Groq fails or spaCy fails during ingestion, Phase 2 is unaffected. If ChromaDB needs to be rebuilt, it can be rebuilt from master.db without re-ingesting any articles.

**The master graph is never rebuilt from scratch on startup.** It is loaded from disk and only new articles are applied to it. This means startup time stays constant regardless of how many historical articles exist.

**ChromaDB is also never rebuilt from scratch on startup.** New articles are added to the existing collection. Article IDs are checked against existing ChromaDB IDs to skip already-embedded articles.

**No hardcoded extraction lists anywhere.** spaCy uses trained model weights. Groq uses language understanding. No commodity list, company watchlist, or logistics location list is maintained manually anywhere in the codebase.

**Embedding model is local.** `sentence-transformers` runs on CPU locally with no API calls. This makes embedding generation completely free, completely offline, and completely unlimited. It also ensures embedding consistency — the same model version is always used for both ingestion and queries.

**The master graph is the historical intelligence layer.** Edge weights and node weights encode how frequently relationships and entities have appeared across all historical articles. This is information that cannot be derived from any single article or from ChromaDB alone. It enables future anomaly detection, trend analysis, and pattern recognition.

---

## Known Deferred Items

- Dynamic refresh scheduling (currently Phase 1 and 2 run on server startup only)
- Low confidence queue review interface
- Master graph pruning for very stale low-weight edges (relevant after 12+ months of data)
- ChromaDB collection TTL strategy for very large volumes
- `/api/graph/master` pagination or streaming for very large graphs
- Relationship type vocabulary expansion as new event patterns emerge
- Multi-commodity article handling in ChromaDB metadata (currently only first commodity stored as flat metadata)
