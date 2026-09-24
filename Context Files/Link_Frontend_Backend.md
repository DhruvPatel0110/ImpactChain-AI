# Link_Frontend_Backend.md

## Overview

The frontend accesses the **master graph** (built by backend Phases 1–2) to:
1. **Globe visualization**: Highlight countries/regions with supply chain disruptions
2. **Dashboard**: Display entity cards (commodities, companies, regions) and their relationships

The backend serves this graph via a single, stable REST API endpoint. The frontend queries once on load, caches, and updates on interval.

---

## Architecture

```
Backend (FastAPI):
  Phase 1: Ingestion → Raw articles + embeddings
  Phase 2: Master Graph → NetworkX MultiDiGraph + SQLite
  ↓
API Endpoint: GET /api/master_graph
  Returns: Entire graph (nodes + edges) + metadata
  ↓
Frontend (React):
  - Cache graph in Zustand store on load
  - On user interaction (globe click, filter) → transform graph → highlight
  - Fetch `/api/master_graph` every 5–10 min to refresh
```

---

## Step 1: Backend API Endpoint

**File**: `backend/app/api/graph_api.py`

```python
from fastapi import APIRouter, HTTPException
from app.master_graph import MasterGraph
import json

router = APIRouter(prefix="/api", tags=["graph"])

# Initialize master graph (loaded once at startup)
master_graph_instance = None

async def init_graph():
    global master_graph_instance
    master_graph_instance = MasterGraph()
    await master_graph_instance.load()

@router.get("/master_graph")
async def get_master_graph():
    """
    Returns the entire master graph as JSON.
    
    Response format:
    {
        "nodes": [
            {"id": "iran", "type": "region", "metadata": {...}},
            {"id": "crude oil", "type": "commodity", "metadata": {...}},
            ...
        ],
        "edges": [
            {"source": "iran", "target": "crude oil", "weight": 0.85, "type": "supplies"},
            ...
        ],
        "timestamp": "2025-09-21T10:00:00Z",
        "total_events": 42
    }
    """
    if master_graph_instance is None:
        raise HTTPException(status_code=500, detail="Graph not initialized")
    
    try:
        return master_graph_instance.to_json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph serialization failed: {str(e)}")

@router.get("/master_graph/highlight/{entity_id}")
async def get_entity_context(entity_id: str):
    """
    Returns a sub-graph focused on a single entity and its neighbors.
    
    Used when user clicks on a globe region or dashboard card.
    
    Response format:
    {
        "entity": {"id": "iran", "type": "region", ...},
        "neighbors": [
            {"id": "crude oil", "type": "commodity", "relationship": "supplies", "weight": 0.85},
            ...
        ],
        "second_order": [
            {"id": "petrol", "type": "commodity", "path": ["crude oil", "petrol"], "weight": 0.72},
            ...
        ],
        "events_mentioning_entity": [
            {"headline": "...", "timestamp": "...", "source": "..."},
            ...
        ]
    }
    """
    if master_graph_instance is None:
        raise HTTPException(status_code=500, detail="Graph not initialized")
    
    try:
        entity_id = entity_id.lower()
        return master_graph_instance.get_entity_context(entity_id, depth=2)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found in graph")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context retrieval failed: {str(e)}")

@router.get("/master_graph/search")
async def search_graph(query: str, entity_type: str = None):
    """
    Search for entities by name or substring.
    
    Query params:
    - query: "iran", "crude", etc.
    - entity_type: Optional filter by "region", "commodity", "company"
    
    Returns: List of matching entities with metadata
    """
    if master_graph_instance is None:
        raise HTTPException(status_code=500, detail="Graph not initialized")
    
    try:
        results = master_graph_instance.search_entities(query, entity_type)
        return {"query": query, "results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
```

**Add to `backend/app/main.py`:**

```python
from fastapi import FastAPI
from app.api.graph_api import router as graph_router
from app.api.graph_api import init_graph

app = FastAPI()

@app.on_event("startup")
async def startup():
    await init_graph()

app.include_router(graph_router)
```

---

## Step 2: Frontend Store (Zustand)

**File**: `frontend/src/store/graphStore.js`

```javascript
import create from 'zustand';

export const useGraphStore = create((set, get) => ({
  graph: null,
  loading: true,
  error: null,
  lastFetch: null,

  // Fetch entire master graph from backend
  fetchMasterGraph: async () => {
    set({ loading: true, error: null });
    try {
      const response = await fetch('http://localhost:8000/api/master_graph');
      if (!response.ok) throw new Error(`API error: ${response.status}`);
      
      const data = await response.json();
      set({
        graph: data,
        loading: false,
        lastFetch: new Date(),
      });
    } catch (err) {
      set({
        error: err.message,
        loading: false,
      });
    }
  },

  // Get context for a single entity (used when user clicks)
  fetchEntityContext: async (entityId) => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/master_graph/highlight/${entityId}`
      );
      if (!response.ok) throw new Error(`Entity not found: ${entityId}`);
      
      return await response.json();
    } catch (err) {
      set({ error: err.message });
      return null;
    }
  },

  // Search graph for entities
  searchGraph: async (query, entityType = null) => {
    try {
      const params = new URLSearchParams({ query });
      if (entityType) params.append('entity_type', entityType);
      
      const response = await fetch(
        `http://localhost:8000/api/master_graph/search?${params}`
      );
      if (!response.ok) throw new Error('Search failed');
      
      return await response.json();
    } catch (err) {
      set({ error: err.message });
      return null;
    }
  },

  // Helper: get all nodes of a specific type
  getNodesByType: (type) => {
    const { graph } = get();
    if (!graph) return [];
    return graph.nodes.filter(node => node.type === type);
  },

  // Helper: get all edges connected to an entity
  getEntityEdges: (entityId) => {
    const { graph } = get();
    if (!graph) return [];
    return graph.edges.filter(
      edge => edge.source === entityId || edge.target === entityId
    );
  },
}));
```

---

## Step 3: Globe Component Integration

**File**: `frontend/src/components/GlobeViewer.jsx`

```javascript
import React, { useEffect, useState } from 'react';
import { useGraphStore } from '../store/graphStore';

export default function GlobeViewer() {
  const { graph, fetchMasterGraph, fetchEntityContext } = useGraphStore();
  const [highlightedCountries, setHighlightedCountries] = useState([]);
  const [selectedEntity, setSelectedEntity] = useState(null);

  // On mount: fetch master graph
  useEffect(() => {
    fetchMasterGraph();
  }, []);

  // When graph loads: extract all regions and highlight them
  useEffect(() => {
    if (!graph) return;

    const regions = graph.nodes
      .filter(node => node.type === 'region')
      .map(node => node.id);

    setHighlightedCountries(regions);
  }, [graph]);

  // When user clicks on globe:
  // 1. Get entity context from backend
  // 2. Pass to dashboard for display
  const handleCountryClick = async (countryId) => {
    const context = await fetchEntityContext(countryId);
    setSelectedEntity(context);
    
    // Pass to dashboard
    window.dispatchEvent(
      new CustomEvent('entitySelected', { detail: context })
    );
  };

  if (!graph) return <div>Loading globe...</div>;

  return (
    <div className="globe-container">
      {/* Your existing globe.gl component */}
      {/* Highlight countries in highlightedCountries */}
      {/* On click, call handleCountryClick() */}
    </div>
  );
}
```

---

## Step 4: Dashboard Integration

**File**: `frontend/src/components/Dashboard.jsx`

```javascript
import React, { useEffect, useState } from 'react';
import { useGraphStore } from '../store/graphStore';
import EntityCard from './EntityCard';

export default function Dashboard() {
  const { graph } = useGraphStore();
  const [displayedEntity, setDisplayedEntity] = useState(null);
  const [supplyChainNodes, setSupplyChainNodes] = useState([]);

  // Listen for globe clicks
  useEffect(() => {
    const handleEntitySelected = (event) => {
      const { entity, neighbors, second_order } = event.detail;
      setDisplayedEntity(entity);
      setSupplyChainNodes([entity, ...neighbors, ...second_order]);
    };

    window.addEventListener('entitySelected', handleEntitySelected);
    return () => window.removeEventListener('entitySelected', handleEntitySelected);
  }, []);

  // Filter graph to show only supply chain entities
  useEffect(() => {
    if (!displayedEntity || !graph) return;

    const relatedNodes = graph.nodes.filter(node =>
      supplyChainNodes.some(scNode => scNode.id === node.id)
    );

    setSupplyChainNodes(relatedNodes);
  }, [displayedEntity, graph]);

  return (
    <div className="dashboard">
      <h2>Supply Chain Context</h2>
      {displayedEntity && (
        <div className="entity-focus">
          <h3>{displayedEntity.id}</h3>
          <p>{displayedEntity.type}</p>
        </div>
      )}
      <div className="entity-grid">
        {supplyChainNodes.map(node => (
          <EntityCard key={node.id} entity={node} />
        ))}
      </div>
    </div>
  );
}
```

---

## Step 5: Refresh Strategy

**File**: `frontend/src/hooks/useGraphRefresh.js`

```javascript
import { useEffect } from 'react';
import { useGraphStore } from '../store/graphStore';

/**
 * Periodically refresh master graph from backend.
 * Default: every 5 minutes.
 */
export function useGraphRefresh(intervalMs = 5 * 60 * 1000) {
  const { fetchMasterGraph } = useGraphStore();

  useEffect(() => {
    const timer = setInterval(fetchMasterGraph, intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);
}
```

**Use in your main App component:**

```javascript
import { useGraphRefresh } from './hooks/useGraphRefresh';

function App() {
  useGraphRefresh(5 * 60 * 1000); // Refresh every 5 min
  
  return (
    // your app
  );
}
```

---

## Step 6: Example Workflow

### User clicks on "Iran" on globe:

1. **Globe component**: `handleCountryClick("iran")`
2. **Backend**: `GET /api/master_graph/highlight/iran`
   - Returns: Iran node + direct neighbors (crude oil, shipping lanes, etc.)
   - Returns: Second-order neighbors (petrol, logistics, etc.)
   - Returns: Recent events mentioning Iran
3. **Dashboard**: Receives context via `entitySelected` event
4. **Cards display**: Commodities → Companies → Transportation routes
5. **Supply chain is now visible** on screen

### User searches "semiconductor" in dashboard:

1. **Dashboard search**: `GET /api/master_graph/search?query=semiconductor`
2. **Backend**: Returns matching nodes
3. **Display**: Shows all semiconductor-related entities + their connections

---

## Step 7: Data Format Reference

### Master Graph JSON:

```json
{
  "nodes": [
    {
      "id": "iran",
      "type": "region",
      "metadata": {
        "event_count": 12,
        "last_updated": "2025-09-21T10:00:00Z",
        "primary_industries": ["oil", "shipping"],
        "severity": "high"
      }
    },
    {
      "id": "crude oil",
      "type": "commodity",
      "metadata": {
        "current_price": 82.50,
        "price_change": "+5.2%",
        "producing_regions": ["iran", "saudi arabia"],
        "dependent_industries": ["logistics", "aviation", "petrochemicals"]
      }
    }
  ],
  "edges": [
    {
      "source": "iran",
      "target": "crude oil",
      "weight": 0.92,
      "type": "supplies",
      "events": 8,
      "last_mentioned": "2025-09-21T08:30:00Z"
    }
  ],
  "timestamp": "2025-09-21T10:00:00Z",
  "total_events": 42,
  "total_nodes": 156,
  "total_edges": 342
}
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **CORS errors** | Add CORS middleware to FastAPI: `from fastapi.middleware.cors import CORSMiddleware` |
| **Graph returns null** | Ensure backend Phase 2 completed; check master_graph.json exists |
| **No regions highlighted** | Verify NER is extracting regions; check entity_filter.py isn't filtering them out |
| **Stale data on globe** | Reduce refresh interval (default 5 min); check backend is updating master graph |
| **Entity not found on search** | Entity may be filtered; check entity relevance scoring in Phase 2B |

---

## Summary

1. **Backend** builds master graph (phases 1–2) ✅
2. **Backend** serves via `/api/master_graph` + contextual endpoints
3. **Frontend** fetches once, caches, refreshes every 5 min
4. **Globe** highlights countries from graph nodes
5. **Dashboard** displays entities + supply chain on user click
6. **Workflow**: Click → Context API call → Event dispatch → Dashboard update

No hardcoded lists. All filtering from master graph.
