# ImpactChain AI — Month 1 Weekly Tasklist (4 Weeks)

**Timeline**: 3-3.5 months total (compressed)
**Month 1 Goal**: MVP foundation — news flowing → preprocessing → grouped events → dashboard displaying
**Hours Target**: 15-20/week
**Environment**: Codespaces/Replit (FREE, unlimited)
**Budget**: ₹0 (free APIs only)

---

# WEEK 1: Project Setup + Ingestion Architecture

**Hours Target**: 14-16 hours
**Outcome**: FastAPI running, NewsAPI + RSS feeds configured, basic async ingestion skeleton ready

## Prereqs (Learn These First)
- [ ] Async/await fundamentals in Python (why it matters for concurrent API calls)
- [ ] aiohttp library basics (making async HTTP requests)
- [ ] REST API concepts (headers, params, rate limiting)
- [ ] Codespaces/Replit interface (terminal, file editor, running servers)
- [ ] Git basics (commit, push, basic workflow)

## Weekly Checklist

### Day 1-2: Setup (Mon-Tue)
- [ ] Create GitHub Codespaces environment (Python 3.10+, Node.js pre-installed)
- [ ] Initialize FastAPI backend project structure (separate folder from frontend)
- [ ] Initialize React frontend project (TypeScript optional, CSS-in-JS ready)
- [ ] Set up `.env` file structure (API keys, environment variables)
- [ ] Create `.gitignore` (exclude .env, node_modules, __pycache__)
- [ ] Confirm FastAPI runs locally on Codespaces without errors

### Day 3-4: API Setup (Wed-Thu)
- [ ] Register & get NewsAPI free tier key (5000 req/month limit documented)
- [ ] Document NewsAPI rate limit strategy (cache articles, don't re-fetch duplicates)
- [ ] Identify & list 5-8 RSS feeds (Reuters, CNBC, BBC, Bloomberg, Al Jazeera, Economic Times, etc.)
- [ ] Test RSS feed URLs are accessible (no 404s, returns valid XML)
- [ ] Plan ingestion service architecture (what endpoints needed, data format)

### Day 5: Backend Skeleton (Fri)
- [ ] Create `news_api_service.py` — async wrapper for NewsAPI calls (no implementation, just structure)
- [ ] Create `rss_feed_service.py` — async RSS parser service (no implementation, just structure)
- [ ] Create `ingestion_orchestrator.py` — combines both sources, deduplicates (no implementation)
- [ ] Create `/api/articles` endpoint in FastAPI (returns mock data for now)
- [ ] Document API response format expected from both sources
- [ ] Commit to GitHub with clear commit message

---

# WEEK 2: Ingestion Pipeline Complete + Preprocessing Foundation

**Hours Target**: 16-18 hours
**Outcome**: Live news data flowing, articles normalized with extracted entities, preprocessing service skeleton ready

## Prereqs (Learn These First)
- [ ] Entity extraction concepts (NER vs regex, when to use each)
- [ ] spaCy basics OR decide on regex-only approach for MVP (NO complex dependencies)
- [ ] Data normalization patterns (standardizing dates, text cleaning)
- [ ] JSON data handling in Python (storing/loading articles)
- [ ] Caching strategies (when to cache, TTL, invalidation)

## Weekly Checklist

### Day 1-2: NewsAPI Integration (Mon-Tue)
- [ ] Implement NewsAPI service — async requests for multiple keywords concurrently
- [ ] Add caching layer — store fetched articles in JSON file with timestamps
- [ ] Implement rate limit handling — track API calls, stop if approaching 5000/month
- [ ] Test with real API calls — fetch 20+ articles, verify response structure
- [ ] Add error handling — API failures, network timeouts, malformed responses

### Day 3-4: RSS Feed Integration (Wed-Thu)
- [ ] Implement RSS feed service — async fetch + parse XML for all configured feeds
- [ ] Test all RSS feeds — verify they return valid articles
- [ ] Deduplicate across RSS feeds — same article shouldn't appear twice
- [ ] Merge NewsAPI + RSS articles — combine both into single article list
- [ ] Sort by date (newest first) — chronological ordering

### Day 5: Preprocessing Setup (Fri)
- [ ] Define entity extraction approach (hardcoded lists: regions, companies, industries, commodities)
- [ ] Create `preprocessing_service.py` skeleton — no implementation yet
- [ ] Document what needs extracting (regions, timestamps, keywords, source normalization)
- [ ] Create normalized article data model/schema
- [ ] Update `/api/articles` endpoint to return real data from NewsAPI + RSS
- [ ] Test end-to-end: article fetch → normalize (basic) → return via API

---

# WEEK 3: Preprocessing + Event Grouping + Dashboard Start

**Hours Target**: 17-19 hours
**Outcome**: Articles processed with entities extracted, basic event grouping working, React dashboard displaying grouped events

## Prereqs (Learn These First)
- [ ] React hooks basics (useState, useEffect, API fetching)
- [ ] TailwindCSS quick setup (dark theme, custom colors)
- [ ] Component design patterns (reusable cards, grids, filters)
- [ ] Event clustering heuristics (why articles should group together)
- [ ] Frontend state management basics (why you need it, Zustand intro)

## Weekly Checklist

### Day 1-2: Preprocessing Implementation (Mon-Tue)
- [ ] Implement entity extraction — identify regions, companies, industries, commodities in article text
- [ ] Implement date/timestamp normalization — parse ISO formats consistently
- [ ] Implement text cleaning — remove junk, extract summary, generate keywords
- [ ] Create normalized article schema — standardized structure from all sources
- [ ] Test preprocessing on 30+ real articles — verify extraction accuracy
- [ ] Update ingestion pipeline — fetch → preprocess → store

### Day 3: Event Grouping Implementation (Wed)
- [ ] Implement heuristic event grouper — articles with shared regions/industries/commodities group together
- [ ] Add temporal window — articles within 24 hours considered for grouping
- [ ] Implement deduplication within groups — same URL shouldn't appear twice
- [ ] Create event consolidation logic — merge titles, summaries, metadata
- [ ] Test grouping on real articles — manually verify 10+ groups make sense
- [ ] Create `/api/events` endpoint — returns grouped events instead of raw articles

### Day 4-5: React Dashboard (Thu-Fri)
- [ ] Create event card component — display title, regions, industries, source count, article count
- [ ] Create event grid component — responsive layout (1/2/3 columns based on screen size)
- [ ] Implement API fetch in React — GET /api/events, handle loading states
- [ ] Implement basic filtering — filter events by industry or region
- [ ] Style with TailwindCSS — dark theme, Bloomberg-like aesthetic
- [ ] Test end-to-end — backend → API → frontend → display
- [ ] Ensure mobile responsive — test on different screen widths

---

# WEEK 4: Event Grouping Refinement + Significance Grading Foundation + Polish

**Hours Target**: 15-17 hours
**Outcome**: Event grouping working well manually verified, basic significance scoring implemented, Month 1 MVP complete

## Prereqs (Learn These First)
- [ ] Significance scoring concepts (why density + diversity matter)
- [ ] Weighted scoring systems (how to combine multiple factors)
- [ ] Refresh/polling strategies (when to re-fetch, how often)
- [ ] Performance basics (why caching matters, when APIs get slow)

## Weekly Checklist

### Day 1-2: Grouping Refinement (Mon-Tue)
- [ ] Review event grouping output — manually check 20+ events for quality
- [ ] Adjust heuristics if needed — increase/decrease keyword overlap threshold
- [ ] Test edge cases — duplicate articles, malformed data, missing fields
- [ ] Add logging — understand what articles are grouping together and why
- [ ] Verify deduplication works — no duplicate URLs in events

### Day 3: Basic Significance Grading (Wed)
- [ ] Implement significance scorer — calculate simple score based on:
  - Article count in cluster (more = more significant)
  - Source diversity (more different sources = more significant)
  - Geographic spread (articles mentioning multiple regions = more significant)
  - Industry spread (affecting multiple industries = more significant)
- [ ] Classify events into tiers: Major (score >= 0.7), Moderate (0.4-0.7), Minor (< 0.4)
- [ ] Create `/api/events?tier=major` endpoint — filter by significance
- [ ] Test scoring — verify top events actually look important

### Day 4-5: Frontend Polish + Testing (Thu-Fri)
- [ ] Add refresh button — manually trigger new ingestion cycle
- [ ] Implement auto-refresh — poll `/api/events` every 2 minutes
- [ ] Add event tier visual indicators — color/size based on major/moderate/minor
- [ ] Add loading skeleton/spinner — better UX while fetching
- [ ] Add error states — handle API failures gracefully
- [ ] Test full workflow end-to-end: News → Ingest → Process → Group → Score → Display
- [ ] Commit all Month 1 work to GitHub
- [ ] Create comprehensive README — how to run backend + frontend locally
- [ ] Document API endpoints — what each endpoint does, sample responses

---

# MONTH 1 SUCCESS CRITERIA

✅ **MUST HAVE** (non-negotiable):
- [ ] FastAPI backend running on Codespaces without errors
- [ ] NewsAPI + RSS feeds fetching real data continuously
- [ ] Articles normalized + preprocessed (entities extracted)
- [ ] Events grouped heuristically (20-40 events from 100+ articles)
- [ ] React dashboard displaying events beautifully
- [ ] Basic significance grading working
- [ ] Full workflow tested end-to-end
- [ ] All code committed to GitHub
- [ ] README documentation complete

✅ **SHOULD HAVE** (nice-to-have):
- [ ] Caching layer preventing duplicate fetches
- [ ] Error handling for API failures
- [ ] Mobile-responsive dashboard
- [ ] Filtering by industry/region working
- [ ] Logging what's happening in backend

❌ **DO NOT START** (save for Month 2):
- [ ] Embeddings or vector DB
- [ ] DBSCAN clustering
- [ ] Historical event matching
- [ ] Voice bot
- [ ] Interactive maps
- [ ] LLM reasoning engine

---

# MONTH 1 QUICK REFERENCE

| Week | Focus | Key Deliverable |
|------|-------|-----------------|
| 1 | Setup + architecture | FastAPI + Codespaces running, APIs configured |
| 2 | Ingestion pipeline | Live news flowing from NewsAPI + RSS |
| 3 | Preprocessing + grouping + dashboard | Events grouped + displayed in React |
| 4 | Refinement + significance grading | Month 1 MVP complete, repo pushed |

---

# TRANSITION: Month 1 → Month 2

**Before starting Month 2:**
- [ ] Review all Month 1 code — is it clean? Does it work reliably?
- [ ] Check API usage — are you approaching NewsAPI limits?
- [ ] Test stability — run backend for 24 hours, check for memory leaks
- [ ] Document what worked + what sucked
- [ ] Create UML/architecture diagrams (as you mentioned you'd do)
- [ ] Plan Month 2 learning (embeddings, DBSCAN, ChromaDB)

---

# MONTHS 2-3: COMPRESSED TIMELINE (3-3.5 months total)

**Adjusted Schedule** (since you have exams in Month 4, finishing by end of Month 3):

## Month 2 (Weeks 5-9): Intelligence Layer + Maps
**Compress these together:**
- Week 5-6: Embeddings + ChromaDB + DBSCAN clustering
- Week 7: Significance grading (refined)
- Week 8: Historical event retrieval + basic RAG
- Week 9: Leaflet.js world map + hotspots

## Month 3 (Weeks 10-12): Maps + Polish + Optional Voice Bot
- Week 10-11: Interactive map features + stock market visualization + dashboard interconnection
- Week 12: Full system testing + performance optimization + documentation + deployment

**This compresses the original 4-month plan into 3-3.5 months by:**
- Running embedding/clustering/maps in parallel (Week 9 starts maps while finishing intelligence)
- Skipping fancy voice bot UI polish (keep it simple OR skip entirely if tight on time)
- Focusing on core features: intelligence → maps → interconnection
- Aggressive testing + debugging combined with features (not at the end)

---

# FINAL REMINDERS FOR MONTH 1

🎯 **Stick to this checklist** — it's the only "roadmap" you need
🎯 **No overthinking** — you know the architecture, just implement
🎯 **Test frequently** — don't build for 2 weeks then test
🎯 **Commit daily** — GitHub is your safety net
🎯 **Use Codespaces** — your i3 shitbox can't handle this
🎯 **API limits matter** — cache aggressively, don't re-fetch

**You've got 4 weeks. Let's go.** 💪
