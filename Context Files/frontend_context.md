# frontend_3d_globe_context.md

# ImpactChain AI — 3D Interactive Globe Frontend

# Core Objective

The frontend's primary interface is a fully interactive 3D globe that serves as the
entry point into ImpactChain AI's intelligence layer. Instead of a traditional list/card
dashboard, the user explores global disruptions spatially — zooming into regions,
observing highlighted event zones, and drilling down from "globe → region → pin →
supply chain dashboard."

This document describes ONLY the frontend 3D globe experience, split into 4 buildable
phases. Phase 5 (live backend linkage) is intentionally out of scope here — every phase
below uses static/mock data so the UI can be built, tested, and demoed independently of
the backend pipeline.

---

# ZERO-COST CONSTRAINT

Every tool, library, texture, and dataset referenced in this document is free and
open-source / public-domain. Nothing here requires a paid API key, paid tileset, or
licensed 3D asset. Everything is installable via `npm install` and runs entirely in the
browser (client-side rendering) — no GPU server, no paid hosting required for
development.

---

# OVERALL TECH STACK

## Core 3D Globe Rendering

* **react-globe.gl** — the primary library for this entire build.
  - Built on top of **three-globe** and **three.js**, but exposes a declarative React
    component API, which avoids hand-writing raw three.js scene/camera/renderer
    boilerplate.
  - Natively supports: country/continent polygon layers, point layers, ring layers
    (built-in pulsing/blinking rings — solves Phase 2's "blinking dark red circle"
    requirement out of the box), arcs, HTML/DOM marker layers (usable for the location
    pin in Phase 3), custom textures, and camera fly-to (`pointOfView()`), which solves
    the "zoom into continent" requirement in Phase 1.
  - Free, MIT licensed, no API key.

* **three.js** — installed as a peer dependency of react-globe.gl. Direct three.js
  usage should stay minimal; react-globe.gl's props cover ~90% of what's needed.

## Geographic Boundary Data (continents / countries)

* **world-atlas** (TopoJSON, from the `topojson/world-atlas` GitHub repo, public
  domain / Natural Earth derived) — provides country and land boundary polygons at
  multiple resolutions (110m, 50m, 10m). This is the standard free dataset used in
  virtually every globe.gl demo.
* **Natural Earth** (naturalearthdata.com) — the underlying public-domain source data
  if more granular boundaries (states/provinces within a country, for the "zoom into
  continent → see countries" and eventually "zoom into country → see cities/regions"
  requirement) are needed later.
* Data is fetched either bundled locally (recommended, avoids CORS/network flakiness in
  Codespaces) or via a CDN like unpkg/jsDelivr pointing at the world-atlas package.

## Earth Texture / Visual Detail

* **three-globe example assets** (public domain NASA Blue Marble derivatives, bundled
  with the three-globe repo's `/example/img` folder) — day-texture, bump map, and
  night-lights texture images. These are the same assets used in most free three.js
  globe tutorials and are safe to vendor directly into the project's `/public` folder.
* Optional: NASA Visible Earth imagery (nasa.gov) is public domain and can be swapped
  in for higher resolution textures later at zero cost.

## Framework / Build

* **React** (already in use per the existing `frontend/` folder).
* **Vite** (already the build tool in the existing scaffold — confirmed from the
  uploaded folder structure showing `vite.config.js`).
* **TailwindCSS** — for all non-globe UI chrome (overlays, panels, the supply chain
  dashboard, buttons, legends).

## State Management

* **Zustand** — lightweight, no boilerplate, ideal for tracking "currently selected
  region," "camera zoom level," "active pin," and "dashboard open/closed" state across
  components without prop-drilling. Free, tiny bundle size.

## Animation / Panel Transitions

* **Framer Motion** — for the dashboard slide-in/slide-out panel, pin pop-in animation,
  and smooth UI transitions. Free, npm-installable.

## Icons / Placeholder Imagery (Phase 4)

* **lucide-react** — free icon set, already available in this environment's component
  ecosystem, usable for placeholder commodity/entity icons before real images are
  wired in.
* Placeholder commodity/entity images can be sourced later from Wikimedia Commons
  (public domain / free-licensed images) — no cost, no API key, matches the project's
  existing "Wikipedia as contextual enrichment source" philosophy from the backend
  context docs.

---

# SETUP INSTRUCTIONS (do this first, before Phase 1)

1. Continue using the existing `frontend/` folder (Vite + React scaffold already
   present, per the current project structure).
2. Install the core 3D + supporting libraries:
   - `react-globe.gl`
   - `three` (peer dependency)
   - `zustand`
   - `framer-motion`
   - `lucide-react`
   - `tailwindcss` (if not already configured in the existing scaffold — confirm
     against the existing `vite.config.js` / `package.json` before reinstalling)
3. Create a `data/` folder inside `frontend/src/` to hold all static/mock JSON used by
   Phases 1–4 (boundary GeoJSON/TopoJSON, mock event data, mock supply chain data).
   Keeping this isolated makes Phase 5's eventual swap to live API data a matter of
   replacing the data-fetching layer, not the UI components.
4. Create an `assets/globe/` folder inside `frontend/public/` to hold the vendored
   earth textures (day map, bump map, night lights) so the app has zero runtime
   dependency on an external CDN staying online.
5. Create a top-level `components/globe/` folder inside `frontend/src/` to hold all
   globe-specific components, kept separate from any future dashboard/news-feed
   components so the 3D layer stays modular.
6. This entire stack runs fully client-side. In GitHub Codespaces, `npm run dev` with
   Vite's default port-forwarding is sufficient — no additional cloud services,
   containers, or paid compute are required for any of the 4 phases below.

---

# PHASE 1 — Core Interactive 3D Globe

## Goal

A detailed, fully interactive, rotatable, zoomable 3D globe rendered in-browser, with
drill-down from world view → continent view → country view, each level still rendered
as an interactive 3D globe (not a flat map).

## Scope

* Render the base 3D globe using react-globe.gl with the vendored Earth day/bump/night
  textures.
* Enable default globe interactions out of the box: drag-to-rotate, scroll/pinch to
  zoom, momentum/inertia on drag release.
* Load country + continent boundary polygons from the bundled world-atlas TopoJSON
  data and render them as a polygon layer on top of the globe surface (visible
  borders, subtly styled so they don't visually compete with future highlight layers).
* Group countries into continents using standard continent-code metadata bundled
  alongside the boundary dataset (Natural Earth features include continent
  attribution per country), so a "continent" is a computed grouping of country
  polygons rather than a separately modeled 3D asset.
* Implement click-to-zoom behavior:
  - Clicking a continent's polygon area triggers a smooth camera fly-to
    (`pointOfView()` with animated transition) that centers and zooms the globe on
    that continent's bounding region.
  - Once zoomed to continent level, the individual countries within that continent
    become the interactive/clickable polygon units (still rendered on the same 3D
    globe — this is a camera-level zoom, not a swap to a different model or a 2D map).
  - Clicking a country at this zoom level performs a further camera fly-to, centering
    tightly on that country.
* Implement a "zoom out" control (a persistent UI button, e.g. "Back to World View")
  since drag/scroll alone won't reliably reset a tightly zoomed camera back to the
  full-world framing.
* Basic ambient lighting and subtle auto-rotation on initial load (idle-state
  auto-rotate that pauses the moment the user interacts) to make the initial "open
  hote hi" impression feel alive rather than static.

## Explicit non-goals for Phase 1

* No color-coded event highlighting yet (that's Phase 2).
* No pins yet (Phase 3).
* No dashboard yet (Phase 4).
* No live/dynamic data — country/continent geometry is the only data loaded, and it's
  static boundary data, not event data.

## Data/Asset Notes

* Country + continent boundaries: bundle the world-atlas `countries-110m.json` (or
  `50m` for more coastline detail if performance allows) directly in
  `frontend/src/data/`.
* Textures: vendor the three-globe example Earth textures into
  `frontend/public/assets/globe/`.
* No download "into a 3D modeling tool" is required — the globe itself is procedurally
  generated by three-globe from a sphere + texture + polygon data, not an imported
  `.glb`/`.fbx` model. This avoids any 3D-modeling-software dependency entirely.

---

# PHASE 2 — Event Highlighting Layer

## Goal

Overlay color-coded, behaviorally distinct highlight markers on top of the Phase 1
globe to represent active disruption events, using static/manually-assigned mock data.

## Scope

* Introduce a mock event dataset in `frontend/src/data/mockEvents.json`, where each
  entry has (at minimum): a region/country reference, a tier (e.g. `moderate`,
  `major`, `critical-active`), a color, and a rough centroid coordinate (lat/lng) for
  the highlighted area.
* Manually seed this mock dataset with the exact examples already established:
  - Russia–Ukraine war → moderate tier → orange → highlighted area spans the Russia
    border region and the whole of Ukraine.
  - USA–Iran tension → major tier → red → highlighted areas span Iran, UAE, and USA.
  - Colombia earthquake (today) → critical/active tier → dark red, continuously
    blinking → highlighted area is Colombia only.
* Render highlights using react-globe.gl's built-in ring layer, which natively
  supports pulsing/propagating rings — this is the mechanism used for all three
  tiers, differentiated by:
  - Color (orange / red / dark red) mapped from the tier field.
  - Propagation speed and repeat period (a slower, single/occasional pulse for
    "moderate," a steadier pulse for "major," and a fast, continuous, high-contrast
    pulse for the "blinking" critical/active tier).
  - Ring size/max radius scaled to roughly represent the affected area (e.g. a
    country-sized ring for Ukraine vs. a tighter ring for a single-city earthquake).
* Keep the tier→color→behavior mapping in a single small config object (not scattered
  across components), since this is exactly the piece that gets replaced by the
  real significance-tier data from the backend's Event Grader in Phase 5 — isolating
  it now makes that swap mechanical later.
* All region assignment in this phase is manual/hardcoded in the mock JSON file, as
  explicitly intended — no dynamic logic yet.

## Explicit non-goals for Phase 2

* No backend/API involvement — everything is static mock data.
* No automatic significance calculation — tier is manually assigned per mock entry.
* No pin/drill-down interaction yet (Phase 3).

---

# PHASE 3 — Deeper Highlighting (Region → Pin Drill-Down)

## Goal

Clicking a highlighted ring transitions it into a precise location pin pointing at the
exact affected country/city, as a further drill-down step before opening the dashboard.

## Scope

* On click of any ring-highlight from Phase 2:
  - Trigger a camera fly-to that centers/zooms on that event's region (reusing the
    same fly-to mechanism built in Phase 1 for continent/country zoom).
  - Replace the ring visualization for that specific event with a single static pin
    marker, rendered via react-globe.gl's HTML/DOM marker layer (so it can be a
    normal styled SVG/HTML pin element rather than a 3D-modeled object) positioned at
    the event's precise lat/lng from the mock data.
* Pin styling is uniform across all event tiers, exactly as specified — one pin
  size/shape regardless of whether the underlying event was a red circle or a
  blinking dark-red circle. Tier/severity is something already communicated by the
  ring stage; the pin stage is purely a precision-location indicator.
* Precise coordinates for each mock event (the "exact city/place/country") are added
  as an additional field per entry in the same `mockEvents.json` used in Phase 2,
  keeping one single source of mock truth across Phases 2–4.
* The pin is clickable and is the trigger for Phase 4's dashboard.
* Provide a clear way to back out of the pin view (reusing the Phase 1 "back to world
  view" control, or a dedicated "back to region view" step), so the drill-down doesn't
  strand the user.

## Explicit non-goals for Phase 3

* No dashboard content yet (Phase 4).
* No variety in pin design across severity tiers, as explicitly specified.
* No backend-driven coordinate resolution — coordinates are hardcoded per mock event.

---

# PHASE 4 — Supply Chain Dashboard UI (Static)

## Goal

Clicking a Phase 3 pin opens a supply chain dashboard panel showing the
commodities/entities relevant to that event, using static placeholder content only —
UI/UX only, no real graph logic.

## Scope

* Panel presentation: a slide-in dashboard (side panel or bottom-sheet style, animated
  via Framer Motion) that overlays the globe view without fully replacing it, so the
  globe + pin context remains visible/accessible behind the dashboard.
* Panel contents, per event, sourced from a static mock structure (e.g.
  `frontend/src/data/mockSupplyChain.json`, keyed by the same event ID used in
  `mockEvents.json`):
  - Event title/summary header (reusing the mock event's existing title/summary
    fields).
  - A row/grid of "affected entity" placeholder cards — one per relevant
    commodity/company/industry for that event (e.g. for the Iran/USA event: crude
    oil, natural gas, a couple of relevant company placeholders; for the Colombia
    earthquake: relevant regional export commodities). Each card is a simple
    placeholder: icon or placeholder image, entity name, and entity type label
    (commodity / company / industry) — no computed impact scores or graph edges yet,
    since that depends on the real master graph.
  - Cards use `lucide-react` icons as stand-ins where no image exists yet, and can
    later swap to real images sourced from Wikimedia Commons per entity.
* Close/back interaction: closing the dashboard returns focus to the pin/region view
  from Phase 3, not all the way back to world view, preserving drill-down state.
* Keep the dashboard's data-fetching logic isolated to a single function/hook (e.g.
  `useSupplyChainData(eventId)`) that currently just reads the static JSON — this is
  the exact seam where Phase 5 will later swap in a real API call to the backend's
  `/api/events/{id}/analysis`-style endpoint without touching any dashboard UI
  component.

## Explicit non-goals for Phase 4

* No real entity/commodity relationship logic — placeholders only, as specified.
* No connection to the master graph, ChromaDB, or any backend endpoint.
* No dynamic significance-based layout differences — same card-grid treatment
  regardless of event tier, since deeper dashboard planning is intentionally deferred.

---

# CROSS-PHASE FOLDER STRUCTURE (target end state after Phase 4)

```
frontend/
  public/
    assets/
      globe/            # vendored earth textures (day/bump/night)
  src/
    components/
      globe/
        Globe.jsx              # Phase 1 base globe + polygon layer + fly-to
        HighlightLayer.jsx     # Phase 2 ring layer + tier config
        LocationPin.jsx        # Phase 3 HTML marker layer
      dashboard/
        SupplyChainPanel.jsx   # Phase 4 slide-in panel
        EntityCard.jsx         # Phase 4 placeholder entity card
    data/
      worldBoundaries.json     # Phase 1 (world-atlas TopoJSON, bundled)
      mockEvents.json          # Phase 2 + 3 (tier, color, region, precise coords)
      mockSupplyChain.json     # Phase 4 (placeholder entities per event)
    state/
      globeStore.js            # Zustand store: selected region/event, zoom state,
                                # dashboard open/closed
    hooks/
      useSupplyChainData.js    # Phase 4 seam for future Phase 5 API swap
```

---

# FINAL NOTE ON PHASE 5

Live linkage to the FastAPI backend (event feed, significance tiers, master graph
data, historical parallels) is intentionally excluded from this document. Each phase
above has been built with one deliberate seam per data type (`mockEvents.json` →
future `/api/events/geospatial`, `mockSupplyChain.json` → future
`/api/events/{id}/analysis`) specifically so that connecting to the real backend later
is a data-source swap rather than a UI rebuild.
