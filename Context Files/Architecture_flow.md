# architecture_flow.md

# ImpactChain AI — System Architecture & Data Flow

# Core Philosophy

The system should behave like:
a realtime economic intelligence engine.

The architecture is designed around:
continuous ingestion → contextual understanding → semantic memory → economic reasoning → interactive visualization.

The goal is NOT simply:
collecting news articles.

The goal is:
understanding how global events propagate through supply chains, industries, commodities, and markets.

---

# High-Level System Flow

External Sources
→ Data Ingestion Layer
→ Preprocessing Layer
→ Event Grouping
→ Embedding Generation
→ Event Clustering
→ Significance Grading
→ Vector Database Storage
→ Historical Retrieval
→ AI Reasoning Engine
→ Frontend Dashboard APIs

---

# Detailed Data Flow

# 1. DATA SOURCE LAYER

The system continuously gathers realtime data from:

* News APIs
* RSS feeds
* Government websites
* Stock exchanges
* Commodity APIs
* Company announcements
* Weather/disaster APIs
* Economic portals
* Financial websites

Purpose:
maximize contextual diversity and realtime awareness.

---

# 2. INGESTION LAYER

Responsibilities:

* async API calls
* RSS polling
* scraping public feeds
* scheduled background fetching
* source normalization

The ingestion layer should:
continuously gather data in parallel.

Recommended:

* asyncio
* aiohttp
* background schedulers

---

# 3. PREPROCESSING LAYER

Raw data is noisy and inconsistent.

The preprocessing layer:

* removes duplicates
* extracts entities
* extracts regions
* extracts timestamps
* identifies industries
* identifies commodities
* identifies companies
* cleans article text
* generates summaries
* standardizes metadata

Output:
normalized event candidates.

---

# 4. CANDIDATE EVENT GROUPING

Before embeddings:
events are heuristically grouped using:

* keyword overlap
* region overlap
* entity overlap
* timestamps
* commodity similarity
* industry overlap

Purpose:
reduce unnecessary embedding comparisons.

Example:
articles mentioning:

* Iran
* crude oil
* shipping
* Middle East

within similar timestamps
may become one candidate event pool.

---

# 5. EMBEDDING GENERATION

The grouped event candidates are converted into embeddings.

Embedding targets:

* event summaries
* article clusters
* commodity movement summaries
* industry impact summaries
* supply chain relationships

Purpose:
semantic understanding.

---

# 6. EVENT CLUSTERING

Recommended:
DBSCAN clustering.

Reason:

* density-based
* detects natural event clusters
* identifies noise
* handles evolving event streams well

Hybrid strategy:

1. heuristic grouping
2. embedding clustering

Purpose:
identify semantically related event clusters.

---

# 7. SIGNIFICANCE GRADER

Each event cluster receives:
a dynamic significance score.

Factors:

* embedding density
* source diversity
* geographic spread
* financial reaction
* industry spread
* update frequency

Purpose:
determine dashboard prominence.

Output:

* major event
* moderate event
* minor event

---

# 8. VECTOR DATABASE STORAGE

The vector database acts as:
the system's long-term economic memory.

Stores:

* embeddings
* metadata
* historical events
* commodity movement
* stock reactions
* industry impacts
* event summaries

Recommended:

* ChromaDB
* FAISS

Purpose:
semantic retrieval and historical intelligence.

---

# 9. HISTORICAL EVENT RETRIEVAL

One of the most important system features.

The retrieval layer searches for:
historically similar economic interference patterns.

NOT:
necessarily same event causes.

Example:
Iran conflict
and
refinery explosion

may both correlate with:
crude oil supply disruption.

Purpose:
retrieve historically similar downstream effects.

---

# 10. AI REASONING ENGINE

The AI layer receives:

* current event data
* historical parallels
* commodity movement
* supply chain relationships
* stock reactions
* industry mappings

The LLM generates:

* contextual summaries
* market explanations
* impact reasoning
* historical comparisons
* influence analysis

The system should NEVER claim:
deterministic stock prediction.

Instead:
contextual intelligence.

---

# 11. FRONTEND API LAYER

The backend exposes APIs for:

* live event feeds
* event detail pages
* significance-ranked events
* historical comparisons
* stock movement summaries
* supply chain visualizations
* industry mappings

Frontend becomes:
the visualization layer.

Backend remains:
the intelligence layer.

---

# 12. FRONTEND DASHBOARD

Displays:

* major events
* minor events
* supply chain impact chains
* stock reactions
* historical parallels
* commodity movement
* industry intelligence

The frontend should feel like:
an interactive geopolitical-economic intelligence platform.

---

# EVENT LIFECYCLE FLOW

News Appears
→ Ingestion
→ Normalization
→ Grouping
→ Embedding
→ Clustering
→ Significance Scoring
→ Storage
→ Historical Matching
→ AI Analysis
→ Dashboard Display

---

# ECONOMIC PROPAGATION MODEL

Example:

War
→ crude oil disruption
→ fuel cost increase
→ logistics pressure
→ ecommerce margin pressure
→ transportation volatility
→ stock market reactions

The system should eventually understand:
multi-layer economic ripple effects.

---

# FUTURE SCALABILITY

Potential future additions:

* graph databases
* knowledge graphs
* temporal event evolution
* causal inference
* realtime alerts
* anomaly detection
* adaptive weighting
* confidence scoring
* event momentum tracking

---

# Final Objective

The architecture should evolve into:
a realtime global economic relationship engine capable of understanding how world events propagate through interconnected supply chains and financial systems.