# frontend_context.md

# Frontend Vision

The frontend is designed to function as a realtime economic intelligence dashboard that visually represents global disruptions and their downstream effects across supply chains, industries, commodities, and stock markets.

The dashboard should feel:

* modern
* interactive
* analytical
* data-heavy
* visually clean
* realtime/live

Primary frontend stack preference:

* React
* TailwindCSS
* Plotly/Recharts
* Framer Motion later if needed

Power BI may optionally be explored for advanced analytics visualization, but React is preferred for flexibility and realtime interactivity.

# Frontend Architecture

## 1. Main Homepage

The homepage acts as the central event intelligence board.

It contains:

* major/significant events
* smaller/insignificant events
* realtime updates
* trending disruptions
* economic alerts

The UI should resemble:

* geopolitical intelligence dashboard
* financial analytics platform
* supply chain monitoring system

rather than a normal news website.

---

## 1.1 Significant Events Section

Large visual event cards/square blocks.

Examples:

* Iran conflict
* Red Sea disruption
* Taiwan earthquake
* Russia conflict
* Semiconductor shortage

These appear prominently due to high impact/intensity.

Each major event card contains:

* event title
* origin region
* affected regions
* event category
* severity level
* event summary
* industries affected
* commodities impacted

When clicked, a detailed event analysis page opens.

---

## 1.2 Event Detail Page

The detailed page contains multiple layers of analysis.

### A. Supply Chain Interference Analysis

Displays:

* affected supply chain entities/products
* disruption magnitude
* before vs after price movement
* commodity changes

Example:
Crude Oil
→ Petrol
→ Diesel
→ Plastic
→ Transportation
→ Logistics

Each entity should display:

* price changes
* disruption intensity
* dependency relationships
* downstream effects

The products should be ordered based on:
highest impact magnitude → lowest impact magnitude.

Potential visualizations:

* flow graphs
* dependency trees
* network diagrams
* impact chains
* heatmaps

---

### B. Industry Stock Effects

Displays:

* affected industries
* major companies within those industries
* preferably NSE/BSE companies initially

Example:
Oil Industry:

* Reliance
* ONGC
* BPCL
* IOC

For each company:

* current stock movement
* historical parallels
* possible future influence

---

### Historical Analysis Section

VERY IMPORTANT LOGIC:

Historical comparison should NOT depend on the original cause of the event.

Instead, it should depend on:

* magnitude of supply chain disruption
* similarity of commodity movement
* industry interference intensity

Example:
Current Event:
Iran conflict → crude oil +12%

Historical Event:
Refinery explosion → crude oil +10%

Even though causes differ, the market consequences may be historically similar.

The platform should display:

* similar past events
* stock reactions during those events
* industry behavior
* market volatility
* commodity movement

This creates:
contextual historical intelligence.

---

### Future Influence Section

The platform should NEVER claim guaranteed prediction.

Instead, it should provide:

* probabilistic influence analysis
* possible future market effects
* short-term and long-term influence patterns

Example:
"Historically similar disruptions have correlated with increased logistics costs and short-term oil-sector volatility."

This section should emphasize:

* contextual intelligence
* historical analogs
* uncertainty awareness

rather than deterministic prediction.

---

## 1.3 Insignificant Events Section

Smaller events appear in compact list/cards.

Examples:

* localized factory incident
* small logistics disruption
* regional weather issue

Even though displayed differently, opening the event should still provide:

* supply chain analysis
* historical parallels
* stock effects
* industry impact

The only difference is:
severity and visibility.

---

# Frontend Object Model Idea

Proposed conceptual architecture:

Each event behaves as an object containing:

* event metadata
* supply chain data
* commodity data
* industry mappings
* historical parallels
* stock effects
* future influence summaries

The frontend simply changes:

* display priority
* UI prominence
* card size

based on significance grading.

The internal structure remains consistent.

---

# Frontend Goals

The frontend should:

* visually explain economic relationships
* simplify complex global events
* provide interactive exploration
* feel analytical and intelligent
* encourage event-to-impact discovery

The UI should feel like:
Bloomberg + geopolitical intelligence + AI reasoning dashboard.
