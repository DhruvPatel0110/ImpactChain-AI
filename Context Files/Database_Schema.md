# database_schema.md

# Database Schema Context

# Core Philosophy

The database should NOT behave like:
a simple article storage system.

Instead:
it should function as:
an interconnected economic intelligence memory system.

The schema must support:

* realtime events
* historical intelligence
* semantic retrieval
* supply chain relationships
* market correlations
* contextual reasoning

---

# Primary Entity Types

1. Event
2. Article
3. Industry
4. Commodity
5. Company
6. Stock Data
7. Supply Chain Relationship
8. Historical Parallel
9. Embedding Metadata
10. Significance Metadata

---

# 1. EVENT ENTITY

Represents:
a unified real-world event cluster.

Example:

* Iran conflict
* Taiwan earthquake
* refinery explosion
* Red Sea shipping disruption

---

# Event Fields

event_id

* unique identifier

title

* normalized event title

summary

* AI-generated contextual summary

event_type

* war
* weather
* logistics
* manufacturing
* geopolitical
* commodity disruption

origin_region

* primary source region

affected_regions

* impacted geographic regions

industries_affected

* linked industry references

commodities_affected

* linked commodity references

companies_affected

* linked company references

significance_score

* dynamic weighted score

significance_tier

* major/moderate/minor

embedding_reference

* vector DB linkage

created_at
updated_at

---

# 2. ARTICLE ENTITY

Represents:
individual source articles.

---

# Article Fields

article_id
source_name
source_type
headline
article_text
published_timestamp
url
language
author
related_event_id

Purpose:
traceability and clustering.

---

# 3. INDUSTRY ENTITY

Represents:
economic sectors.

Examples:

* oil
* logistics
* semiconductors
* aviation
* agriculture

---

# Industry Fields

industry_id
industry_name
description
linked_companies
linked_commodities

---

# 4. COMMODITY ENTITY

Represents:
economically relevant commodities.

Examples:

* crude oil
* lithium
* wheat
* semiconductors
* natural gas

---

# Commodity Fields

commodity_id
commodity_name
category
current_price
historical_price_data
volatility_metrics

---

# 5. COMPANY ENTITY

Represents:
public/private companies.

Examples:

* Reliance
* ONGC
* TSMC
* BPCL

---

# Company Fields

company_id
company_name
industry_reference
stock_symbol
exchange
country
linked_supply_chain_entities

---

# 6. STOCK DATA ENTITY

Represents:
market behavior.

---

# Stock Fields

stock_id
company_reference
timestamp
open_price
close_price
high_price
low_price
volume
volatility_score

---

# 7. SUPPLY CHAIN RELATIONSHIP ENTITY

Represents:
downstream propagation chains.

Example:
Crude Oil
→ Petrol
→ Logistics
→ Ecommerce

---

# Relationship Fields

relationship_id
source_entity
target_entity
relationship_type
impact_weight
dependency_strength

---

# 8. HISTORICAL PARALLEL ENTITY

Represents:
historically similar disruptions.

VERY IMPORTANT FEATURE.

Example:
War-driven oil disruption
vs
refinery-driven oil disruption

Similar downstream economic effects.

---

# Historical Parallel Fields

parallel_id
current_event_reference
historical_event_reference
similarity_score
matching_reason
commodity_overlap
industry_overlap

---

# 9. EMBEDDING METADATA ENTITY

Tracks:
semantic vector references.

---

# Embedding Fields

embedding_id
embedding_type
vector_reference
source_entity
created_timestamp

---

# 10. SIGNIFICANCE METADATA ENTITY

Tracks:
event importance evolution.

---

# Significance Fields

score_id
event_reference
embedding_density
source_diversity
financial_reaction
industry_spread
geographic_spread
update_frequency
final_score

---

# RELATIONSHIP MODEL

Articles
→ grouped into Events

Events
→ linked to Industries

Industries
→ linked to Commodities

Commodities
→ linked to Companies

Companies
→ linked to Stocks

Events
→ linked to Historical Parallels

Events
→ linked to Embeddings

---

# DATABASE PHILOSOPHY

The system should evolve into:
an interconnected graph-like economic memory system.

Even if initially implemented using:
traditional databases + vector DB.

Future evolution may include:

* graph databases
* Neo4j
* knowledge graphs
* causal inference engines

---

# Final Objective

The schema should support:
long-term contextual intelligence rather than temporary article storage.