# grader_context.md

# Event Grader Context

# Core Objective

The Event Grader is responsible for determining:

* which events are globally/significantly important
* which events are smaller/localized disruptions
* how prominently an event should appear in the frontend dashboard

The grader should NOT rely on fixed hardcoded thresholds alone.

Instead, the platform should dynamically evaluate event significance using:

* clustering
* embedding density
* source diversity
* industry spread
* financial reaction
* update frequency

The goal is to create:
an adaptive realtime event significance engine.

---

# Core Philosophy

Significance is RELATIVE, not absolute.

Example:

* 200 articles may represent a massive global event during a quiet news cycle
* 200 articles may represent a minor event during a globally chaotic period

Therefore:
fixed embedding/article count thresholds alone are insufficient.

The grader should instead:
analyze event density and contextual impact dynamically.

---

# High-Level Workflow

1. Gather raw articles/data
2. Perform preprocessing
3. Create candidate event groups
4. Generate embeddings
5. Cluster semantically similar events
6. Calculate significance score
7. Assign frontend visibility level

---

# 1. INITIAL EVENT GROUPING

Before embeddings are generated, the system should first perform lightweight grouping using:

* keywords
* timestamps
* regions
* industries
* companies
* commodities
* event categories

Purpose:
reduce unnecessary embedding comparisons and computational cost.

Example:
Articles mentioning:

* Iran
* crude oil
* shipping
* Middle East

within similar timestamps may first be grouped into one candidate event pool.

This stage acts as:
candidate event filtering.

---

# 2. EMBEDDING GENERATION

After initial grouping:
embeddings should be generated for:

* event summaries
* article clusters
* entity relationships
* contextual descriptions

Purpose:
semantic similarity analysis.

Embeddings help identify:
different articles discussing the same real-world event even when wording differs.

Example:

* "Oil volatility rises after Middle East tensions"
* "Iran conflict impacts crude supply"

should still map semantically close.

---

# 3. CLUSTERING ENGINE

# Recommended Algorithm:

DBSCAN

Reason:

* density-based clustering
* automatically identifies cluster groups
* detects noise/outliers
* no fixed cluster count required
* works well for realtime evolving event streams

The grader should use:
hybrid clustering.

Meaning:

1. heuristic grouping first
2. semantic embedding clustering second

This avoids:
full brute-force embedding comparison across all articles.

---

# 4. SIGNIFICANCE SCORE ENGINE

The system should NOT classify events using:
hardcoded article count alone.

Instead:
every event cluster receives a weighted significance score.

Example:
0.18
0.52
0.87

The frontend then decides:

* major card
* medium card
* small list item

based on score ranges.

---

# 5. FACTORS CONTRIBUTING TO SIGNIFICANCE SCORE

## A. Embedding Density

Measures:
how many semantically related articles belong to the event cluster.

Higher density generally indicates:
larger global attention.

---

## B. Source Diversity (VERY IMPORTANT)

Measures:
how many UNIQUE source types discuss the same event.

Examples:

* Reuters
* CNBC
* government portals
* local newspapers
* corporate announcements
* commodity reports

Events covered across multiple source categories receive higher significance.

Reason:
cross-source attention usually indicates real-world impact.

---

## C. Geographic Spread

Measures:
how globally widespread the event discussion is.

Examples:

* local factory incident
* regional disruption
* multi-country geopolitical issue

Broader geographic discussion increases significance.

---

## D. Industry Spread

Measures:
how many industries are affected.

Example:
Single local factory issue
vs
oil + logistics + aviation + shipping disruption

Broader economic influence increases significance.

---

## E. Financial Reaction

Measures:
observable economic reaction signals.

Examples:

* stock volatility
* commodity spikes
* index movement
* supply shortages
* price fluctuations

The stronger the measurable economic response,
the higher the significance score.

---

## F. Update Frequency

Measures:
how rapidly new related articles/data continue arriving.

Fast-growing event clusters may indicate:
breaking or escalating situations.

---

# 6. WEIGHTED SIGNIFICANCE FORMULA

Example conceptual scoring model:

score =
0.30 * embedding_density

* 0.25 * source_diversity
* 0.20 * financial_reaction
* 0.15 * industry_spread
* 0.10 * geographic_spread

Weights are adjustable and experimental.

The platform should support:
dynamic tuning later.

---

# 7. EVENT CLASSIFICATION

After scoring:
events are grouped into visibility tiers.

Example:

## Tier 1 — Major Events

Examples:

* wars
* geopolitical crises
* major supply disruptions
* semiconductor shortages

Frontend:
large prominent dashboard cards.

---

## Tier 2 — Moderate Events

Examples:

* regional strikes
* refinery failures
* localized commodity disruption

Frontend:
medium cards or secondary panels.

---

## Tier 3 — Minor Events

Examples:

* small local factory incidents
* temporary regional delays

Frontend:
compact list entries.

---

# IMPORTANT FRONTEND PHILOSOPHY

Classification affects:
visibility and priority ONLY.

NOT:
data completeness.

Even smaller events should still contain:

* supply chain analysis
* historical parallels
* stock effects
* contextual reasoning

The difference is:
dashboard prominence.

---

# 8. HISTORICAL EVENT MEMORY

The grader should also contribute to:
historical event intelligence.

Each event cluster should store:

* significance score history
* article growth over time
* financial reactions
* affected industries

This allows:
future historical comparisons and trend analysis.

---

# 9. FUTURE SCALABILITY IDEAS

Potential future improvements:

* adaptive weights
* temporal decay scoring
* anomaly detection
* knowledge graphs
* event momentum tracking
* realtime escalation alerts
* confidence scoring
* source credibility weighting

---

# Final Goal

The Event Grader should evolve into:
an intelligent realtime event prioritization engine capable of distinguishing globally impactful economic disruptions from localized informational noise using contextual, semantic, and financial analysis.