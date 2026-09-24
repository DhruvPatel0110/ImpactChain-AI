# Fix_Dynamic_Filtering.md

## The Problem

You're seeing "semiconductors" in master graph even though it's not relevant anymore because:

1. **Entity extraction is working** (spaCy/Groq finds "semiconductor")
2. **But relevance judgment is static** (hardcoded list of "supply chain entities")
3. **Result**: Every article mentioning any entity gets stored, even if unrelated to disruption

Example:
- Article: "Ed Sheeran concert semiconductor hologram tech"
  - Extracted: `semiconductor`
  - Relevance check: ✓ "semiconductor" is on supply chain watchlist
  - Stored: YES (wrong!)
  
---

## Root Cause

Somewhere in your Phase 1/2 pipeline, you're doing something like:

```python
# BAD (static list)
SUPPLY_CHAIN_ENTITIES = ["semiconductor", "oil", "shipping", "lithium"]

if any(entity.lower() in SUPPLY_CHAIN_ENTITIES for entity in extracted_entities):
    store_article()  # Store if ANY entity matches
```

This doesn't answer: **"Is this article ACTUALLY about a supply chain disruption?"**

It only asks: **"Does it mention a supply chain entity?"** (Yes → store)

---

## The Fix: Dynamic Relevance Scoring

Replace static lists with **semantic relevance judgment** using Groq:

### Step 1: Identify Where Filtering Happens

**Find this file** (likely in your backend):
- `app/ingestion.py` or `app/phases/phase1.py`
- Look for: entity extraction → storage decision

**Look for code like:**
```python
if entity in SUPPLY_CHAIN_KEYWORDS:
    # Store article
```

---

### Step 2: Create a Relevance Scorer

**File**: `backend/app/relevance_scorer.py`

```python
from app.groq_client import groq_client
import json

class RelevanceScorer:
    """
    Judges if an article is actually about supply chain disruption.
    Uses Groq for semantic understanding (not keyword matching).
    """
    
    def __init__(self):
        self.cache = {}  # Simple in-memory cache
    
    def score_article(self, headline: str, summary: str, entities: list) -> dict:
        """
        Returns:
        {
            "relevant": bool,
            "score": float (0-1),
            "reason": str,
            "disruption_type": str or None,
            "affected_domains": list
        }
        """
        
        # Cache key to avoid re-scoring same article
        cache_key = f"{headline}:{','.join(sorted(entities))}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Build prompt for Groq
        prompt = f"""
Analyze this article and judge if it describes a SUPPLY CHAIN DISRUPTION.

Headline: {headline}
Summary: {summary}
Mentioned entities: {', '.join(entities)}

Answer ONLY with JSON (no markdown, no explanation):
{{
    "relevant": true/false,
    "score": 0.0-1.0 (confidence),
    "reason": "brief explanation",
    "disruption_type": "geopolitical|natural_disaster|industrial_failure|logistics|commodity_crisis|economic_shock|none",
    "affected_domains": ["oil", "semiconductors", "shipping"] (only if relevant=true)
}}

Guidelines for RELEVANT articles:
- Describes actual disruption: war, embargo, strike, natural disaster, factory explosion
- Impacts supply chain: mentions shortage, price spike, route blocked, production halted
- Actionable intelligence: readers can understand economic consequences

Guidelines for IRRELEVANT articles:
- Technology feature article mentioning a company
- Product launch or corporate news
- Historical or educational content
- Entertainment news (e.g., "hologram concert using semiconductors")
- Opinion/speculation without confirmed disruption

BE STRICT. Only mark as relevant if clear supply chain impact exists.
"""
        
        try:
            response = groq_client.messages.create(
                model="llama3-70b-8192",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse Groq response
            result_text = response.content[0].text.strip()
            
            # Remove markdown backticks if present
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            
            result = json.loads(result_text)
            
            # Validate response
            if not isinstance(result.get("relevant"), bool):
                raise ValueError("Missing 'relevant' field")
            
            # Cache and return
            self.cache[cache_key] = result
            return result
            
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            print(f"Groq response: {result_text}")
            return {
                "relevant": False,
                "score": 0.0,
                "reason": "Failed to parse Groq response",
                "disruption_type": None,
                "affected_domains": []
            }
        except Exception as e:
            print(f"Relevance scoring error: {e}")
            return {
                "relevant": False,
                "score": 0.0,
                "reason": f"Scoring error: {str(e)}",
                "disruption_type": None,
                "affected_domains": []
            }
    
    def batch_score(self, articles: list) -> list:
        """
        Score multiple articles.
        
        Args:
            articles: [{"headline": str, "summary": str, "entities": list}, ...]
        
        Returns:
            [{"article": {...}, "relevance": {...}}, ...]
        """
        results = []
        for article in articles:
            relevance = self.score_article(
                article["headline"],
                article["summary"],
                article["entities"]
            )
            results.append({
                "article": article,
                "relevance": relevance
            })
        return results
    
    def clear_cache(self):
        """Clear in-memory cache (call periodically to free memory)"""
        self.cache.clear()
```

---

### Step 3: Integrate into Ingestion Pipeline

**File**: `backend/app/ingestion.py` (modify existing)

```python
from app.relevance_scorer import RelevanceScorer
from app.entity_filter import EntityFilter

relevance_scorer = RelevanceScorer()
entity_filter = EntityFilter()

async def process_article(article: dict) -> dict:
    """
    Process raw article through full pipeline.
    Returns: None if irrelevant, else enriched article.
    """
    
    # Step 1: Extract entities (existing code)
    entities = extract_entities_via_spacy_groq(article["title"], article["description"])
    
    # Step 2: Filter false positives (existing entity_filter.py)
    entities = entity_filter.filter_entities(entities)
    
    # Step 3: NEW - Dynamic relevance scoring
    relevance = relevance_scorer.score_article(
        headline=article["title"],
        summary=article["description"],
        entities=entities
    )
    
    # Step 4: Decision
    if not relevance["relevant"]:
        # Log rejection for debugging
        print(f"[FILTERED] {article['title'][:50]}... → {relevance['reason']}")
        return None
    
    if relevance["score"] < 0.5:
        # Low confidence - log but don't store
        print(f"[LOW_CONFIDENCE] {article['title'][:50]}... (score: {relevance['score']})")
        return None
    
    # Step 5: Enrich article metadata with relevance data
    enriched_article = {
        **article,
        "entities": entities,
        "relevance_score": relevance["score"],
        "disruption_type": relevance["disruption_type"],
        "affected_domains": relevance["affected_domains"],
        "relevance_reason": relevance["reason"],
    }
    
    return enriched_article

async def ingest_articles():
    """Existing ingestion loop"""
    articles_from_newsapi = await fetch_newsapi()
    articles_from_rss = await fetch_rss_feeds()
    
    all_articles = articles_from_newsapi + articles_from_rss
    
    relevant_articles = []
    for article in all_articles:
        processed = await process_article(article)
        if processed:
            relevant_articles.append(processed)
    
    # Store only relevant articles
    await store_articles(relevant_articles)
    
    print(f"Ingestion complete: {len(relevant_articles)}/{len(all_articles)} articles relevant")
    
    return relevant_articles
```

---

### Step 4: Query Phase 1 API Endpoint

**File**: `backend/app/api/articles_api.py` (modify existing)

Add filtering options:

```python
@router.get("/api/articles")
async def get_articles(
    relevant_only: bool = True,
    min_score: float = 0.5,
    disruption_type: str = None,
    limit: int = 50
):
    """
    Get articles with dynamic filtering.
    
    Query params:
    - relevant_only: Only return relevant articles (default: True)
    - min_score: Minimum relevance score (0-1, default: 0.5)
    - disruption_type: Filter by type (geopolitical|natural_disaster|etc)
    - limit: Number of results
    """
    articles = fetch_articles_from_db()
    
    # Filter by relevance
    if relevant_only:
        articles = [a for a in articles if a.get("relevance_score", 0) >= min_score]
    
    # Filter by disruption type
    if disruption_type:
        articles = [a for a in articles if a.get("disruption_type") == disruption_type]
    
    # Sort by score (newest/highest first)
    articles.sort(key=lambda a: (-a.get("relevance_score", 0), -a.get("timestamp", 0)))
    
    return articles[:limit]
```

---

### Step 5: Monitoring & Debugging

**File**: `backend/app/monitoring/relevance_monitor.py`

```python
class RelevanceMonitor:
    """Track filtering accuracy over time"""
    
    def __init__(self):
        self.stats = {
            "total_ingested": 0,
            "total_relevant": 0,
            "total_filtered": 0,
            "by_disruption_type": {},
            "filtering_ratio": 0.0
        }
    
    def record(self, article: dict, is_relevant: bool, score: float):
        self.stats["total_ingested"] += 1
        
        if is_relevant:
            self.stats["total_relevant"] += 1
            dtype = article.get("disruption_type", "unknown")
            self.stats["by_disruption_type"][dtype] = \
                self.stats["by_disruption_type"].get(dtype, 0) + 1
        else:
            self.stats["total_filtered"] += 1
        
        self.stats["filtering_ratio"] = \
            self.stats["total_filtered"] / self.stats["total_ingested"]
    
    def report(self):
        print(f"Ingestion Stats:")
        print(f"  Total ingested: {self.stats['total_ingested']}")
        print(f"  Relevant: {self.stats['total_relevant']}")
        print(f"  Filtered out: {self.stats['total_filtered']}")
        print(f"  Filtering ratio: {self.stats['filtering_ratio']:.1%}")
        print(f"  By type: {self.stats['by_disruption_type']}")
```

---

## Testing This Fix

### Test Case 1: True Positive (should be relevant)

```python
article = {
    "title": "Iran blocks Strait of Hormuz shipping lane amid tensions",
    "description": "Middle East geopolitical tensions escalate as Iran restricts oil shipping...",
    "entities": ["iran", "crude oil", "shipping lanes"]
}

result = relevance_scorer.score_article(
    article["title"],
    article["description"],
    article["entities"]
)

assert result["relevant"] == True, "Should be relevant"
assert result["disruption_type"] == "geopolitical", "Should be geopolitical"
```

### Test Case 2: False Positive (should NOT be relevant)

```python
article = {
    "title": "Ed Sheeran's new concert uses hologram semiconductor technology",
    "description": "The singer showcases cutting-edge semiconductor tech in concert...",
    "entities": ["semiconductor", "technology"]
}

result = relevance_scorer.score_article(
    article["title"],
    article["description"],
    article["entities"]
)

assert result["relevant"] == False, "Should not be relevant"
```

### Test Case 3: Medium Confidence

```python
article = {
    "title": "Semiconductor exports may face new regulations",
    "description": "Policymakers consider new rules affecting semiconductor trade...",
    "entities": ["semiconductor", "trade"]
}

result = relevance_scorer.score_article(
    article["title"],
    article["description"],
    article["entities"]
)

# May be relevant but lower score (0.4-0.6)
print(f"Score: {result['score']} (check if >= 0.5 threshold)")
```

---

## Timeline

| Stage | Effort | Notes |
|-------|--------|-------|
| **Create RelevanceScorer** | 1-2 hrs | Copy + test on sample articles |
| **Integrate into pipeline** | 1-2 hrs | Modify existing ingestion.py |
| **Test on live API** | 1 hr | Monitor filtering ratio |
| **Fine-tune Groq prompt** | 2-3 hrs | Adjust if too strict/loose |
| **Clean master graph** | 1-2 hrs | Re-ingest last 100 articles with new logic |

**Total: 6-10 hours to full dynamic filtering**

---

## Expected Results

**Before (static filtering):**
- Master graph: semiconductor nodes from concert articles, Ed Sheeran articles, tech blogs
- Dashboard noise: unrelated entities mixed with real supply chain disruptions

**After (dynamic filtering):**
- Master graph: semiconductor nodes ONLY from actual supply chain disruptions
- Dashboard clarity: only supply chain-relevant events appear
- Coverage: Real geopolitical/industrial events visible + contextually linked

---

## Groq Prompt Tuning

If filtering is too strict (missing real disruptions):

```python
# Lower the threshold
if relevance["score"] < 0.4:  # Was 0.5
    # Store anyway (with low confidence flag)
```

If filtering is too loose (letting noise through):

```python
# Update Groq prompt with more strict examples:
examples = """
EXAMPLES OF RELEVANT:
- "Taiwan earthquake disrupts semiconductor manufacturing"
- "OPEC reduces oil production by 1 million barrels daily"

EXAMPLES OF IRRELEVANT:
- "New iPhone uses semiconductor chips"
- "Tech company invests in renewable energy"
"""
```

---

## Summary

| Component | Change |
|-----------|--------|
| **Phase 1** | Add `RelevanceScorer` class using Groq for judgment |
| **Ingestion** | Call relevance_scorer before storing articles |
| **API** | Add filters: `relevant_only`, `min_score`, `disruption_type` |
| **Master Graph** | Only includes articles scored as relevant (score >= 0.5) |
| **Dashboard** | Shows clean, contextually-linked supply chain data |

**No more hardcoded lists. Pure semantic understanding.**
