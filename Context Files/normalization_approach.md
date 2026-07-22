# ImpactChain AI — Normalization Approach
## From Raw API Call → Master DB

**Philosophy**: ImpactChain is a supply-chain intelligence tool. News is just the signal source. The system's job is to extract supply-chain-relevant information from that signal, discard the noise, consolidate what remains, and store a clean, queryable master record.

**Core filter before anything else**: If an article doesn't mention something economically consequential to a supply chain — a commodity, a company, a port, a route, a disruption keyword — it doesn't exist in this system.

---

# Architecture Overview

```
NewsAPI Call          RSS Feed Calls
     │                     │
     ▼                     ▼
[raw_articles TABLE]   [raw_articles TABLE]
     │                     │
     └──────────┬──────────┘
                ▼
     [spaCy NER Pipeline]
                │
                ▼
     [extracted_entities TABLE]
                │
                ▼
     [Supply-Chain Relevance Filter]
      ├── RELEVANT → keep
      └── NOT RELEVANT → discard (no DB entry)
                │
                ▼
     [Same-Event Detection]
      ├── Pass 1: Exact entity overlap
      └── Pass 2: Partial overlap + 24h window
                │
                ▼
     [Primary Source Selection]
      └── Most quantitative article wins
                │
                ▼
     [Consolidation + Entity Merging]
                │
                ▼
     [master_events TABLE]
```

---

# DATABASE DESIGN

## Why PostgreSQL

You're clearing the DB every run for now, so persistence isn't the point.
PostgreSQL exposure is — specifically: schema design, normalization, foreign keys, and JSONB columns.

Use PostgreSQL in Codespaces (it's pre-available as a service).
Connection: `postgresql://localhost:5432/impactchain`

When you later add caching and data retention, you switch NOTHING in your schema.
You just stop dropping tables on startup.

## Tables

```sql
-- STEP 1 OUTPUT
raw_articles

-- STEP 2 OUTPUT
extracted_entities

-- STEP 3 OUTPUT (filtered + consolidated)
consolidated_articles   ← intermediate, tracks what survived filtering

-- STEP 4 OUTPUT
master_events
master_event_sources    ← junction table: which articles support which event
```

---

# STEP 1 — RAW INGESTION

## Goal
Fetch from all configured sources and store EVERYTHING, unfiltered, in `raw_articles`.
This is your forensic log. Every article that ever came in lives here before any processing.

## Why One Table (Not Per-Source Tables)

One `raw_articles` table with a `source_name` column is better practice than `newsapi_raw`, `rss_reuters_raw`, etc.
Reason: you'd otherwise be doing `UNION ALL` across 8 tables to run any cross-source query.
A `source_name` column + index gives you the same discrimination with zero query complexity.
The per-source table approach makes sense only when schemas differ dramatically across sources (yours don't — they all produce title, URL, text, date).

## Schema: `raw_articles`

```sql
CREATE TABLE raw_articles (
    id              SERIAL PRIMARY KEY,
    source_name     VARCHAR(100) NOT NULL,       -- "newsapi", "rss_reuters", "rss_cnbc", etc.
    source_type     VARCHAR(20) NOT NULL,         -- "api" or "rss"
    headline        TEXT NOT NULL,
    url             TEXT UNIQUE NOT NULL,          -- dedup key: same URL = same article
    full_text       TEXT,                          -- full article body if available
    summary         TEXT,                          -- RSS description or NewsAPI description
    author          VARCHAR(200),
    published_at    TIMESTAMPTZ,                   -- UTC normalized on insert
    language        VARCHAR(10) DEFAULT 'en',
    raw_payload     JSONB,                         -- the entire original API/RSS response stored as-is
    fetched_at      TIMESTAMPTZ DEFAULT NOW(),
    processed       BOOLEAN DEFAULT FALSE          -- flag: has this article gone through NER yet
);

CREATE INDEX idx_raw_articles_source ON raw_articles(source_name);
CREATE INDEX idx_raw_articles_processed ON raw_articles(processed);
CREATE INDEX idx_raw_articles_published ON raw_articles(published_at);
```

## What Goes Into `raw_payload`

The ENTIRE original JSON object from NewsAPI or the entire parsed RSS item dict from feedparser.
Don't cherry-pick at this stage. You want the full original record so if your preprocessing logic
changes later, you can re-run on the same raw data without re-hitting the APIs.

## Timestamp Normalization on Insert

All `published_at` values are converted to UTC before insert.
NewsAPI returns ISO 8601 strings. RSS returns RFC 2822 or ISO formats depending on feed.
Use `python-dateutil` to parse everything, then `.astimezone(timezone.utc)` before storing.

If timestamp is missing or unparseable: store `fetched_at` as fallback. Never store NULL for published_at.

## Deduplication at Ingestion (URL-based)

Before inserting any article, check if `url` already exists in `raw_articles`.
Use `INSERT ... ON CONFLICT (url) DO NOTHING`.
This is the ONLY deduplication at Step 1. You're not doing semantic dedup yet.
Same article from two different RSS feeds? Both rows exist, one just gets skipped on insert because URL matches.
That's intentional — you want to know it appeared in multiple sources.

## What You're NOT Doing at Step 1

- No entity extraction
- No filtering
- No grouping
- No relevance check
- No content analysis of any kind

Step 1 is a pure pipe. Fetch → normalize timestamp → store.

---

# STEP 2 — spaCy NER PIPELINE

## Goal
Run every unprocessed article through spaCy and store what was extracted.
This runs on ALL raw articles, before any supply-chain relevance filtering.
Reason: you need the extracted entities TO DECIDE relevance. You can't filter before you know what's in the article.

## spaCy Model

Use `en_core_web_sm` for Codespaces (fast, low RAM).
If you want better NER accuracy later, swap to `en_core_web_trf` (transformer-based, heavier).
For MVP: `en_core_web_sm` is sufficient.

Install: `pip install spacy && python -m spacy download en_core_web_sm`

## Entity Types spaCy Extracts (Relevant to ImpactChain)

| spaCy Label | What It Catches | ImpactChain Use |
|-------------|-----------------|-----------------|
| `ORG`       | Companies, institutions, governments | Tesla, TSMC, OPEC, RBI |
| `GPE`       | Countries, cities, states | Iran, India, Mumbai |
| `LOC`       | Non-GPE locations, geographic features | Strait of Hormuz, Red Sea, Pacific Ocean |
| `PRODUCT`   | Named products | Crude oil, LNG (sometimes) |
| `MONEY`     | Monetary values | "$85 per barrel", "₹92 per litre" |
| `PERCENT`   | Percentage values | "3.2% rise", "fell 7%" |
| `DATE`      | Temporal expressions | "last quarter", "since March" |
| `EVENT`     | Named events | "Gulf War", "COVID-19 pandemic" |
| `NORP`      | Nationalities, groups | OPEC nations, G7 |

## Custom Pattern Layer (On Top of spaCy)

spaCy won't catch domain-specific terms like "LPG", "semiconductor", "port strike", "logistics disruption".
You add a `PhraseMatcher` or `EntityRuler` layer on top of the base model.

### COMMODITY_PATTERNS (seed list — you'll expand this)

```python
COMMODITY_TERMS = [
    # Energy
    "crude oil", "brent crude", "WTI", "natural gas", "LNG", "LPG",
    "coal", "petroleum", "diesel", "jet fuel", "kerosene",

    # Metals
    "lithium", "cobalt", "copper", "aluminium", "aluminum", "iron ore",
    "nickel", "zinc", "rare earth", "palladium", "platinum",

    # Agricultural
    "wheat", "corn", "soybean", "rice", "sugar", "cotton", "palm oil",
    "fertilizer", "urea",

    # Tech/Industrial
    "semiconductor", "chip", "microchip", "silicon wafer", "DRAM",
    "NAND flash", "GPU", "CPU",

    # Logistics
    "shipping container", "freight", "cargo", "tanker", "bulk carrier",
]
```

### SUPPLY_CHAIN_SIGNAL_PATTERNS

Terms that indicate a supply-chain-relevant event is being discussed:

```python
SUPPLY_CHAIN_SIGNALS = [
    # Disruption signals
    "shortage", "supply disruption", "supply chain", "bottleneck", "backlog",
    "port congestion", "strike", "blockade", "sanctions", "trade restriction",
    "tariff", "embargo", "export ban", "import ban",

    # Location signals (when in article = logistics relevant)
    "port", "strait", "canal", "shipping lane", "warehouse", "logistics hub",
    "Suez Canal", "Panama Canal", "Strait of Hormuz", "Strait of Malacca",
    "Red Sea", "South China Sea",

    # Price signal terms
    "price spike", "price surge", "price drop", "price hike", "rate increase",
    "inflationary", "cost pressure", "margin pressure",
]
```

## What You're Building: A Quantitative Signal Score

For every article, during NER, you compute a `quantitative_score`.
This will be used later to pick the "most informative" primary source.

```
quantitative_score = (
    (count of MONEY entities × 2)       ← prices, costs, values = most useful
    + (count of PERCENT entities × 2)   ← rate changes, percentage shifts = very useful
    + (count of ORG entities × 1)       ← companies mentioned
    + (count of commodity matches × 1.5) ← commodity terms from custom patterns
    + (count of supply chain signals × 1) ← disruption/logistics keywords
)
```

Higher score = more data-rich article = better primary source candidate.

## Schema: `extracted_entities`

```sql
CREATE TABLE extracted_entities (
    id                  SERIAL PRIMARY KEY,
    article_id          INTEGER NOT NULL REFERENCES raw_articles(id) ON DELETE CASCADE,

    -- Named entity lists (arrays of strings)
    orgs                TEXT[],        -- ORG entities: ["Tesla", "OPEC", "RBI"]
    gpe_locations       TEXT[],        -- GPE: ["Iran", "India", "Mumbai"]
    geo_locations       TEXT[],        -- LOC: ["Strait of Hormuz", "Red Sea"]
    events_named        TEXT[],        -- EVENT: ["Gulf War"]
    
    -- Commodity-specific extraction
    commodities_found   TEXT[],        -- matched against COMMODITY_TERMS list
    
    -- Supply chain signals
    sc_signals_found    TEXT[],        -- matched against SUPPLY_CHAIN_SIGNALS list
    
    -- Quantitative extractions
    money_mentions      TEXT[],        -- raw strings: ["$85 per barrel", "₹92/litre"]
    percent_mentions    TEXT[],        -- raw strings: ["3.2% rise", "fell 7%"]
    
    -- Computed at extraction time
    quantitative_score  FLOAT NOT NULL DEFAULT 0,
    
    -- Relevance flag (set during filtering, Step 3)
    is_sc_relevant      BOOLEAN DEFAULT NULL,   -- NULL = not yet evaluated

    extracted_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ee_article ON extracted_entities(article_id);
CREATE INDEX idx_ee_relevant ON extracted_entities(is_sc_relevant);
CREATE INDEX idx_ee_commodities ON extracted_entities USING GIN(commodities_found);
```

## Processing Loop

```
For each raw_article WHERE processed = FALSE:
    1. Combine headline + summary + full_text into one string
    2. Run spaCy NLP on combined text
    3. Extract all entity types listed above
    4. Run PhraseMatcher for COMMODITY_TERMS and SUPPLY_CHAIN_SIGNALS
    5. Compute quantitative_score
    6. INSERT into extracted_entities
    7. UPDATE raw_articles SET processed = TRUE WHERE id = article_id
```

Run this as an async batch after each ingestion cycle.
Process all new articles in one pass, not one-by-one (batching is faster with spaCy's `nlp.pipe()`).

---

# STEP 3A — SUPPLY-CHAIN RELEVANCE FILTER

## Goal
Decide: does this article contain anything useful for supply-chain analysis?
If not, mark it as irrelevant and never touch it again.

## Relevance Criteria

An article is supply-chain relevant (is_sc_relevant = TRUE) if it satisfies AT LEAST ONE of:

```
CONDITION 1 (Commodity): commodities_found is NOT empty
    → "Oil prices rise after Iran tensions" → commodities_found = ["crude oil"] → RELEVANT

CONDITION 2 (Known Company): orgs contains a company name that's in a curated list
    → "Tesla halts production" → orgs = ["Tesla"] → RELEVANT
    → Wait — how do you know "Tesla" is a supply-chain company not "Tesla the musician"?
    → You maintain a COMPANY_WATCHLIST (50-100 major supply-chain companies)
    → Tesla, TSMC, Samsung, Reliance, ONGC, BPCL, Apple, Intel, Foxconn, Maersk, etc.
    → Cross-reference orgs against this list

CONDITION 3 (Strategic Location): geo_locations or gpe_locations contains a known logistics location
    → "Port of Singapore congested" → geo_locations = ["Port of Singapore"] → RELEVANT
    → Uses same PhraseMatcher pattern as SUPPLY_CHAIN_SIGNALS for location terms
    → "port", "strait", "canal", "shipping lane" in locations = RELEVANT

CONDITION 4 (Disruption Signal): sc_signals_found is NOT empty AND quantitative_score > 0
    → "Major shortage hits semiconductor supply" → sc_signals = ["shortage", "supply chain"] → RELEVANT
    → Note: sc_signals alone without any quantitative signal is weaker — a generic "supply chain" mention
       with no entities/prices is marginal. Require at least quantitative_score > 0 for this condition.

CONDITION 5 (Price Movement): money_mentions OR percent_mentions is NOT empty AND
                              (commodities_found NOT empty OR orgs in COMPANY_WATCHLIST)
    → "Crude up 3.2%" → percent_mentions = ["3.2%"], commodities = ["crude"] → RELEVANT
    → "Apple stock fell 7%" → percent_mentions = ["7%"], orgs = ["Apple"] in watchlist → RELEVANT
```

## What Gets Discarded

```
"Iran fires missiles at military base" → commodities=[], sc_signals=[], money=[], percent=[]
→ is_sc_relevant = FALSE → ignored

"US election results certified" → no supply-chain entities at all
→ is_sc_relevant = FALSE → ignored

"Iran conflict causes oil prices to spike 4%" → commodities=["oil"], percent=["4%"]
→ is_sc_relevant = TRUE → kept
```

The Iran war article only matters to ImpactChain if it says something about oil, shipping, or ports.
If it's pure geopolitics with no economic signal, discard it.

## Execution

After NER, run relevance filter on all newly extracted entities.
`UPDATE extracted_entities SET is_sc_relevant = TRUE/FALSE WHERE id = ...`

This is a pure in-memory evaluation — no additional API calls, no external lookups.
Just logic on the already-extracted entity arrays.

---

# STEP 3B — SAME-EVENT DETECTION

## Goal
Group relevant articles that describe the same real-world event into clusters.
Cluster = one event with multiple source perspectives.

## Input
All articles WHERE `is_sc_relevant = TRUE`, sorted by `published_at` ascending.

## Pass 1 — Exact Entity Overlap

Two articles are candidates for the same event if:
- Their primary commodity overlap is ≥ 70% (Jaccard similarity on `commodities_found` arrays)
- Their published_at timestamps are within 24 hours of each other

```
Jaccard(A, B) = |A ∩ B| / |A ∪ B|

Article A: commodities = [crude oil, natural gas, LNG]
Article B: commodities = [crude oil, LNG]
Intersection = {crude oil, LNG} → size 2
Union = {crude oil, natural gas, LNG} → size 3
Jaccard = 2/3 = 0.667

Not ≥ 0.70, so this is a Pass 2 candidate, not a Pass 1 match.

Article A: commodities = [crude oil, LNG]
Article C: commodities = [crude oil, LNG]
Jaccard = 1.0 → Pass 1 MATCH
```

When Pass 1 match found:
- Add to the same event cluster
- Continue checking remaining articles

## Pass 2 — Partial Overlap with Secondary Signals

For articles that didn't match in Pass 1, check:
- Commodity Jaccard ≥ 0.40 (partial commodity overlap)
- AND at least one matching ORG entity (same company mentioned in both)
- AND timestamps within 48 hours (wider window for slower-developing events)

OR:
- Commodity Jaccard ≥ 0.40
- AND at least two matching sc_signals (both mention "shortage" + "shipping", for example)
- AND timestamps within 36 hours

If both conditions met → CANDIDATE MATCH
Merge into the same cluster.

If no match at all → Article becomes a NEW event cluster (seed of a new event).

## Implementation Note

Don't do O(n²) comparison across all articles.
Index by `primary_commodity` (the most-mentioned commodity in `commodities_found`).
Compare only within the same primary_commodity group.
This reduces comparison space dramatically.

---

# STEP 3C — PRIMARY SOURCE SELECTION

## Goal
Within each event cluster, pick ONE article as the authoritative source.
The rest become supporting articles (they enrich, don't replace).

## Selection Criteria

Primary source = article with highest `quantitative_score` in the cluster.

```
Recall: quantitative_score =
    (MONEY count × 2)
    + (PERCENT count × 2)
    + (ORG count × 1)
    + (commodity match count × 1.5)
    + (sc_signal count × 1)
```

This ensures the article with the most numbers, prices, and economic specifics wins.
A "Strait of Hormuz blockade causes oil to hit $93/barrel, up 4.2% week-on-week, affecting 20% of global LNG trade"
will always beat "Iran tensions escalate, markets nervous".

## Tiebreaker

If two articles have identical quantitative_score (rare but possible):
- Pick the one from the higher-credibility source
- Maintain a `SOURCE_CREDIBILITY_RANK` dict:

```python
SOURCE_CREDIBILITY_RANK = {
    "reuters": 1,
    "bloomberg": 2,
    "financial_times": 3,
    "wsj": 4,
    "cnbc": 5,
    "economic_times": 6,
    "newsapi": 7,     # generic, lower than named sources
    "other": 99
}
```

Source with lowest rank number wins the tiebreaker.
This is a TIEBREAKER ONLY. Quantitative score always comes first.

---

# STEP 3D — CONSOLIDATION + ENTITY MERGING

## Goal
Build one unified event object from the cluster.
Primary source provides the headline and summary.
All sources contribute their entities to the merged entity set.

## What Merging Looks Like

```
Cluster for "crude oil disruption event" has 4 articles:
    Article A (PRIMARY — highest quantitative_score):
        headline: "Brent crude hits $93, up 4.1% after Hormuz shipping slowdown"
        commodities: [crude oil, Brent crude]
        orgs: [OPEC, Saudi Aramco]
        geo_locations: [Strait of Hormuz]
        money: ["$93", "$89 prior week"]
        percent: ["4.1%"]
        
    Article B:
        headline: "Iran conflict rattles global oil markets"
        commodities: [crude oil, LNG]
        orgs: [Iran government, US State Department]
        geo_locations: [Persian Gulf]
        gpe: [Iran, USA]
        
    Article C:
        headline: "Shipping rates spike as tankers reroute"
        commodities: [crude oil]
        orgs: [Maersk, Hapag-Lloyd]
        sc_signals: [shipping disruption, rerouting, freight cost]
        
    Article D:
        headline: "Indian refineries face supply uncertainty"
        commodities: [crude oil, petroleum]
        orgs: [BPCL, HPCL, IOC]
        gpe: [India]
        money: ["₹8500/barrel import cost"]

MERGED EVENT:
    primary_headline: "Brent crude hits $93, up 4.1% after Hormuz shipping slowdown"
    primary_summary: [from Article A]
    
    merged_commodities: [crude oil, Brent crude, LNG, petroleum]
    merged_orgs: [OPEC, Saudi Aramco, Iran government, US State Department, Maersk, Hapag-Lloyd, BPCL, HPCL, IOC]
    merged_geo_locations: [Strait of Hormuz, Persian Gulf]
    merged_gpe: [Iran, USA, India]
    merged_sc_signals: [shipping disruption, rerouting, freight cost]
    merged_money: ["$93", "$89 prior week", "₹8500/barrel import cost"]
    merged_percent: ["4.1%"]
    
    source_count: 4
    article_ids: [A, B, C, D]
    unique_sources: ["reuters", "bloomberg", "economic_times", "cnbc"]
```

The merged entity set is the UNION of entities across ALL articles.
No entity is lost — if Article D mentions BPCL and Article A doesn't, BPCL is still in the master event.
This is the "extra data" enrichment you described.

## Intermediate Table: `consolidated_articles`

Before writing to master_events, track the clustering output here.

```sql
CREATE TABLE consolidated_articles (
    id                  SERIAL PRIMARY KEY,
    event_cluster_id    VARCHAR(50) NOT NULL,    -- temporary cluster ID, e.g. "cluster_crude_oil_20240712_001"
    article_id          INTEGER REFERENCES raw_articles(id),
    is_primary          BOOLEAN DEFAULT FALSE,
    contribution        TEXT,                    -- what new info this article added (optional, for debugging)
    clustered_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ca_cluster ON consolidated_articles(event_cluster_id);
```

This is a junction table. One cluster_id → many article_ids. One article → one cluster.

---

# STEP 4 — MASTER DB STORAGE

## Goal
Write the final, consolidated, deduplicated, entity-enriched event objects.
This is the table that the FastAPI `/api/events` endpoint reads from.
This is the table that Month 2 will run embeddings on.
This is ImpactChain's source of truth.

## Schema: `master_events`

```sql
CREATE TABLE master_events (
    id                      SERIAL PRIMARY KEY,
    event_uid               VARCHAR(100) UNIQUE NOT NULL,  -- deterministic ID based on primary commodity + date + cluster

    -- Identity
    primary_commodity       VARCHAR(200),        -- the "main thing" this event is about: "crude oil", "semiconductor", etc.
    primary_entity_type     VARCHAR(50),         -- "commodity" | "company" | "logistics_route" | "multi"

    -- Content (from primary source)
    headline                TEXT NOT NULL,
    summary                 TEXT,

    -- Merged entity sets (JSONB — flexible, queryable, no fixed schema needed now)
    commodities             JSONB DEFAULT '[]',   -- ["crude oil", "LNG", "petroleum"]
    companies               JSONB DEFAULT '[]',   -- ["OPEC", "Maersk", "BPCL"]
    regions                 JSONB DEFAULT '[]',   -- GPE: ["Iran", "India", "USA"]
    locations               JSONB DEFAULT '[]',   -- LOC: ["Strait of Hormuz", "Persian Gulf"]
    sc_signals              JSONB DEFAULT '[]',   -- ["shipping disruption", "rerouting"]

    -- Quantitative signals (merged from all sources)
    price_mentions          JSONB DEFAULT '[]',   -- raw strings: ["$93/barrel", "₹8500/barrel"]
    rate_changes            JSONB DEFAULT '[]',   -- raw strings: ["up 4.1%", "fell 7%"]

    -- Source tracking
    source_count            INTEGER DEFAULT 1,    -- how many unique sources
    article_count           INTEGER DEFAULT 1,    -- total articles in cluster
    unique_sources          JSONB DEFAULT '[]',   -- ["reuters", "bloomberg", "cnbc"]
    primary_article_id      INTEGER REFERENCES raw_articles(id),

    -- Temporal
    event_start             TIMESTAMPTZ,          -- earliest article timestamp in cluster
    event_last_seen         TIMESTAMPTZ,          -- latest article timestamp in cluster
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),

    -- Relevance scoring (basic, pre-embedding)
    relevance_score         FLOAT DEFAULT 0,      -- computed from source_count + quantitative signals + sc_signal count

    -- Month 2 hooks (leave NULL for now, populate during embedding phase)
    embedding_id            TEXT,                 -- reference to ChromaDB embedding
    significance_tier       VARCHAR(20),          -- "major" | "moderate" | "minor" (Month 2)
    significance_score      FLOAT                 -- weighted score (Month 2)
);

CREATE INDEX idx_me_commodity ON master_events(primary_commodity);
CREATE INDEX idx_me_tier ON master_events(significance_tier);
CREATE INDEX idx_me_relevance ON master_events(relevance_score DESC);
CREATE INDEX idx_me_event_start ON master_events(event_start DESC);
CREATE INDEX idx_me_commodities ON master_events USING GIN(commodities);
CREATE INDEX idx_me_companies ON master_events USING GIN(companies);
```

## Junction Table: `master_event_sources`

```sql
CREATE TABLE master_event_sources (
    id              SERIAL PRIMARY KEY,
    event_id        INTEGER NOT NULL REFERENCES master_events(id) ON DELETE CASCADE,
    article_id      INTEGER NOT NULL REFERENCES raw_articles(id),
    is_primary      BOOLEAN DEFAULT FALSE,
    source_name     VARCHAR(100),
    contribution    TEXT,           -- optional: what did this article add that primary didn't have
    UNIQUE(event_id, article_id)
);

CREATE INDEX idx_mes_event ON master_event_sources(event_id);
```

## How `relevance_score` Is Computed at Insert (Pre-Embedding)

This is NOT the Month 2 significance grading. This is a simpler pre-embedding score
that gives the `/api/events` endpoint something useful to sort by immediately.

```
relevance_score = (
    source_count × 0.25           ← more sources = more relevant
    + article_count × 0.15        ← more coverage = more relevant
    + price_signals_count × 0.30  ← price + percent mentions are the real signal
    + sc_signals_count × 0.20     ← disruption signals
    + commodity_count × 0.10      ← more commodities affected = broader impact
)
```

Normalize each factor to 0–1 before combining (divide by max observed value across all events in current batch).
This gives a 0–1 score that's meaningful within the current ingestion run.

## event_uid Generation

Deterministic, human-readable ID so you can identify events without querying:

```python
event_uid = f"{primary_commodity.lower().replace(' ', '_')}_{date_str}_{cluster_index}"
# Example: "crude_oil_20240712_001", "semiconductor_20240711_003"
```

---

# FULL PIPELINE SEQUENCE (End to End)

```
1. INGEST
   ├── Call NewsAPI with configured keywords
   ├── Poll all RSS feeds asynchronously
   ├── For each article:
   │     ├── Normalize timestamp to UTC
   │     ├── INSERT INTO raw_articles ON CONFLICT (url) DO NOTHING
   │     └── Mark processed = FALSE

2. NER EXTRACTION
   ├── SELECT * FROM raw_articles WHERE processed = FALSE
   ├── Batch all articles into spaCy nlp.pipe()
   ├── For each article:
   │     ├── Extract all entity types
   │     ├── Run PhraseMatcher for COMMODITY_TERMS + SUPPLY_CHAIN_SIGNALS
   │     ├── Compute quantitative_score
   │     ├── INSERT INTO extracted_entities
   │     └── UPDATE raw_articles SET processed = TRUE

3. RELEVANCE FILTER
   ├── For each extracted_entities row:
   │     ├── Check Conditions 1-5
   │     └── UPDATE extracted_entities SET is_sc_relevant = TRUE/FALSE

4. SAME-EVENT DETECTION
   ├── Load all is_sc_relevant = TRUE articles
   ├── Group by primary_commodity
   ├── Within each commodity group:
   │     ├── Pass 1: Jaccard ≥ 0.70 + 24h window → merge into cluster
   │     └── Pass 2: Jaccard ≥ 0.40 + secondary signals + 48h window → merge into cluster
   └── Articles not matching anything → new cluster (event seed)

5. PRIMARY SELECTION + CONSOLIDATION
   ├── For each cluster:
   │     ├── Find article with highest quantitative_score → PRIMARY
   │     ├── Merge entity arrays (UNION) across all articles
   │     ├── Merge quantitative signals
   │     └── Track which article contributed which entities (optional, for debug)

6. MASTER DB WRITE
   ├── For each cluster:
   │     ├── Generate event_uid
   │     ├── Compute relevance_score
   │     ├── INSERT INTO master_events
   │     └── INSERT INTO master_event_sources (one row per article in cluster)
   └── Done. FastAPI /api/events reads from master_events.
```

---

# WHAT STEP 4 ENABLES IN MONTH 2

The master_events schema is designed with Month 2 in mind.

`commodities` (JSONB array) → spaCy already populated this. Month 2 groups by commodity for DBSCAN input.

`embedding_id` (left NULL now) → Month 2 generates an embedding from headline + summary + merged entities, stores in ChromaDB, puts the ChromaDB doc ID here.

`significance_tier` and `significance_score` (left NULL now) → Month 2 grader reads source_count, article_count, price_mentions, sc_signals and fills these in.

`event_start` and `event_last_seen` → Month 2 historical retrieval uses these to compare current events with past events in similar time patterns.

Nothing in the master_events schema needs to change for Month 2.
You just start populating the NULL columns.

---

# EDGE CASES + DECISION LOG

## What if spaCy finds no commodities but article is clearly supply-chain relevant?

Example: "Suez Canal blocked by grounded vessel"
spaCy finds: LOC = "Suez Canal", ORG = "vessel" (misidentified), no commodity terms
SUPPLY_CHAIN_SIGNALS matches: "canal" → sc_signals_found = ["canal"]
Result: Condition 3 (strategic location) + Condition 4 (sc_signal) → RELEVANT

This case is caught. The `geo_locations` check handles it.

## What if same event has articles spanning 3 days?

Pass 2 uses 48h window. If event is still developing after 48h, the later articles
start new clusters that won't merge with the first batch.
This is acceptable for MVP — you're not doing temporal event chaining yet.
Month 2 historical retrieval will link them by embedding similarity.

## What if primary_commodity is wrong?

Example: Article about "Tesla Gigafactory power outage" gets primary_commodity = "electricity"
but you'd rather it be clustered under "Tesla" (company-primary event).

For MVP, this is fine. The merged_entities still contain Tesla.
Fix this in Month 2 by adding entity_type classification logic.

## What if the same event has articles in multiple languages?

Raw ingestion stores all languages. NER on non-English text with `en_core_web_sm` = bad results.
For MVP: filter to English only at ingestion.
`WHERE language = 'en'` before running NER.
Non-English articles stored in raw_articles but skipped in NER pipeline.

## What about NewsAPI's 5000 request/month limit?

Each API call returns up to 100 articles.
5000 / 100 = 50 calls max per month.
Roughly 1-2 calls per day if you're careful.
For testing: make 1-2 calls per session, store the raw_payload, work from stored data.
You're clearing DB each run, but you can save raw_payload JSONs to a local file for re-seeding.

---

# WHAT THIS IS NOT

- Not a news aggregator. You're not trying to store all news.
- Not a content feed. `/api/events` returns supply-chain events, not headlines.
- Not a search engine. You're building a structured intelligence store.
- Not over-engineered. No Kafka, no Redis, no graph DB, no ML at this stage.

The entire pipeline is: Python + spaCy + PostgreSQL.
That's it. Everything above runs as a Python script triggered after each ingestion cycle.

---

*Written for ImpactChain AI — Week 2 implementation reference*
*Month 2 additions: embedding_id, significance_tier, significance_score*
*Month 3+ additions: historical_parallel_ids, temporal_chain_id*
