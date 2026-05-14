# PROJECT_CONTEXT.md

# Project Name

ImpactChain AI

# Project Type

AI Supply Chain & Market Impact Intelligence Platform

# Core Objective

ImpactChain AI is an AI-powered business intelligence platform designed to monitor real-world global events and analyze their downstream effects on supply chains, industries, commodities, and stock markets.

The platform continuously gathers live data from multiple sources such as:

* global news
* geopolitical developments
* logistics reports
* commodity prices
* weather incidents
* industrial failures
* economic disruptions

The system then identifies:

* affected industries
* disrupted supply chains
* related commodities/products
* historically similar market reactions
* possible future impacts

The goal is NOT to guarantee stock prediction.

Instead, the platform focuses on:

* contextual reasoning
* event intelligence
* historical correlation analysis
* economic relationship mapping
* downstream impact analysis

The system compares current events with historically similar supply-chain-impact scenarios irrespective of the original cause.

Example:

* Current Event:
  Iran conflict → crude oil supply disruption → oil price increase

* Historical Parallel:
  Refinery explosion → crude oil supply disruption → similar oil price increase

Even though the causes differ, the magnitude and type of supply chain interference may historically correlate with similar market behavior.

The platform will use those historical similarities to provide:

* contextual market insights
* industry impact explanations
* possible future influence patterns

without claiming deterministic prediction.

# Main System Components

1. Frontend Dashboard

* realtime event dashboard
* interactive visualizations
* supply chain graphs
* stock impact visualizations
* industry breakdowns

Refer:
frontend_context.md

2. Data Gathering + Clustering + Vector Database

* live news ingestion
* multi-source aggregation
* event clustering
* embeddings
* vector retrieval pipeline

Refer:
data_pipeline_context.md

3. Event Grader

* classifies events as significant or insignificant
* based on volume, spread, and impact intensity

Refer:
grader_context.md

4. Backend Intelligence Layer

* RAG retrieval
* event reasoning
* historical matching
* impact analysis
* MCP/API integrations

Refer:
backend_context.md

# Main Philosophy

The project aims to behave like an intelligent economic relationship engine rather than a traditional prediction system.

The focus is:
Event → Supply Chain → Industry → Commodity → Market Impact

rather than:
"AI predicts stock price"

# Planned Stack

Frontend:

* React (preferred)
* Plotly
* Recharts
* TailwindCSS

Backend:

* FastAPI
* Python

AI:

* Groq
* LangChain

Data:

* ChromaDB
* FAISS
* embeddings

Visualization:

* Plotly
* NetworkX

Data Sources:

* RSS feeds
* News APIs
* yfinance
* commodity APIs
* weather APIs

Infrastructure:

* GitHub Codespaces
* Docker later if needed

# Constraints

* Entire stack should remain free or near-free
* Minimal local machine load
* Cloud-based development
* Modular architecture
* Realtime/live-ish data flow

# Long-Term Vision

The platform should eventually evolve into an interactive global economic intelligence dashboard capable of:

* tracking worldwide disruptions
* mapping supply chain effects
* comparing historical market behavior
* providing contextual AI-driven insights
* visually representing interconnected economic systems
