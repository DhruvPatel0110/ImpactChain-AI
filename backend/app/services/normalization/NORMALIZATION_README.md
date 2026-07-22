# Normalization Pipeline

4-step pipeline that transforms raw news articles into consolidated, commodity-grouped supply-chain events.

## Architecture

```
NewsAPI + RSS → raw_articles → spaCy NER → extracted_entities
    → relevance filter → clustering → consolidation → master_events
```

## Quick Start

### 1. Install dependencies

```bash
cd backend
pip install -r req.txt
python -m spacy download en_core_web_sm
```

### 2. Run the test suite

```bash
cd backend
python tests/test_normalization_end_to_end.py
```

This loads 18 synthetic articles and validates every pipeline step.

### 3. Run with FastAPI

```bash
cd backend
uvicorn app.main:app --reload
```

Then trigger the pipeline:

```bash
# Trigger full pipeline (ingest from live APIs + normalize)
curl -X POST http://localhost:8000/api/pipeline/run

# Query events
curl http://localhost:8000/api/events
curl http://localhost:8000/api/events?commodity=crude+oil

# Get single event detail
curl http://localhost:8000/api/events/crude_oil_20240712_001

# Pipeline stats
curl http://localhost:8000/api/stats
```

## Pipeline Steps

| Step | File | What it does |
|------|------|-------------|
| 1 | `step1_ingestion.py` | Store raw articles, dedup by URL, normalize timestamps |
| 2 | `step2_ner_extraction.py` | spaCy NER + PhraseMatcher for commodities/signals |
| 3A | `step3_filtering.py` | 5-condition supply-chain relevance filter |
| 3B/3C | `step3_clustering.py` | 2-pass Jaccard clustering + primary source selection |
| 3D | `step3_consolidation.py` | UNION merge entities across clusters |
| 4 | `step4_master_db.py` | Store master events + compute relevance score |

## Debugging Clustering & Filtering

The pipeline uses `loguru` for detailed logging. Set log level to DEBUG to see:

- **Filtering decisions**: Which condition matched/failed for each article
- **Clustering decisions**: Jaccard scores, time gaps, pass 1 vs pass 2 matches
- **Primary selection**: Why a specific article was chosen as primary
- **Entity merges**: What entities were merged from which articles

Example debug output:
```
  ✓ RELEVANT article 3 ('Shipping rates spike...'): COND1: commodities_found=['crude oil', 'freight']
  ✗ IRRELEVANT article 12 ('US election polls...'): No conditions met
  PASS1 (jaccard=0.85, gap=5.5h): Article 2 merged into cluster with article 1
  PRIMARY selected: article 1 (score=12.5, source=Reuters)
```

## Schema Design

### Why SQLite?
- No setup required
- Single file database
- Good enough for development + testing
- Schema is designed to migrate to PostgreSQL without changes (just swap connection logic)

### Why TEXT for JSON arrays?
- SQLite doesn't have native JSONB
- Entity arrays stored as JSON strings (`json.dumps()` / `json.loads()`)
- Flexible: adding new entity types never requires schema migration
- Queryable via `LIKE '%crude oil%'` for simple filters

### Why fresh DB each run?
- You're iterating on pipeline logic rapidly
- Stale data from previous runs would confuse debugging
- Raw payloads are preserved in the articles — you can re-process anytime
- When ready for persistence: just set `fresh_db=False`

## Keyword Customization

All keyword lists live in `keywords.py`:

| List | Purpose | Used in |
|------|---------|---------|
| `COMMODITY_TERMS` | PhraseMatcher commodity detection | Step 2 |
| `SUPPLY_CHAIN_SIGNALS` | PhraseMatcher signal detection | Step 2 |
| `COMPANY_WATCHLIST` | Relevance filter condition 2 | Step 3A |
| `LOGISTICS_LOCATIONS` | Relevance filter condition 3 | Step 3A |
| `SOURCE_CREDIBILITY_RANK` | Primary source tiebreaker | Step 3C |

Add terms as you discover gaps. The PhraseMatcher is case-insensitive.

## Relevance Score Formula

```
relevance_score = (
    normalized_source_count × 0.25
    + normalized_article_count × 0.15
    + normalized_price_signals × 0.30
    + normalized_sc_signals × 0.20
    + normalized_commodity_count × 0.10
)
```

Each factor normalized to 0–1 by dividing by the max observed value in the current batch.

## Limitations

1. **No persistent storage**: DB wiped each run. Fix: set `fresh_db=False`
2. **English only**: spaCy `en_core_web_sm` works only on English text
3. **No cross-commodity clustering**: Articles are compared within primary commodity groups. An event affecting both oil and LNG won't merge with a pure oil cluster
4. **48h clustering window**: Events spanning 3+ days create separate clusters
5. **No semantic similarity**: Clustering uses Jaccard on extracted entities, not text embeddings (Month 2)
6. **SQLite concurrency**: Single-writer. Don't run pipeline concurrently

## Future Improvements (Month 2+)

- `embedding_id`: ChromaDB embeddings for semantic search
- `significance_tier` + `significance_score`: AI-powered event grading
- Cross-commodity clustering via embeddings
- Temporal event chaining (linking evolving events over days/weeks)
- Historical parallel detection (finding similar past events)
