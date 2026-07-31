"""
ImpactChain AI — Phase 1 Configuration

Loads environment variables from .env, validates mandatory keys,
and defines all constants used across the ingestion pipeline.
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env from project root (one level above backend/)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)
else:
    # Also try backend-local .env
    _BACKEND_ENV = Path(__file__).resolve().parent / ".env"
    if _BACKEND_ENV.exists():
        load_dotenv(_BACKEND_ENV)

# ---------------------------------------------------------------------------
# Mandatory API Keys — raise at import time if missing
# ---------------------------------------------------------------------------
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY") or os.getenv("NEWS_API_KEY", "")

if not GROQ_API_KEY:
    print("ERROR: GROQ_API_KEY is not set in .env — Phase 1 cannot run.", file=sys.stderr)
if not NEWSAPI_KEY:
    print("WARNING: NEWSAPI_KEY is not set in .env — NewsAPI source will be skipped.", file=sys.stderr)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/master.db")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "phase1.log"

# Configure root logger for the pipeline
_log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter(_log_format))

_console_handler = logging.StreamHandler()
_console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
_console_handler.setFormatter(logging.Formatter(_log_format))

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[_file_handler, _console_handler],
)

# ---------------------------------------------------------------------------
# Groq Models (Primary 70B, Fallback 8B with 500k TPD daily quota)
# ---------------------------------------------------------------------------
GROQ_MODEL: str = "llama-3.3-70b-versatile"
FALLBACK_GROQ_MODEL: str = "llama-3.1-8b-instant"

# ---------------------------------------------------------------------------
# NewsAPI Settings
# ---------------------------------------------------------------------------
NEWSAPI_BASE_URL: str = "https://newsapi.org/v2/top-headlines"
NEWSAPI_CATEGORIES: list[str] = ["business", "technology", "science"]
NEWSAPI_PAGE_SIZE: int = 50

# ---------------------------------------------------------------------------
# RSS Feed URLs — hardcoded per spec
# ---------------------------------------------------------------------------
RSS_FEEDS: list[dict] = [
    {"name": "BBC Business", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    {"name": "Economic Times", "url": "https://economictimes.indiatimes.com/rssfeedstopstories.cms"},
    {"name": "Financial Express", "url": "https://www.financialexpress.com/feed/"},
    {"name": "Mint Economy", "url": "https://www.livemint.com/rss/economy"},
    {"name": "CNBC World News", "url": "https://search.cnbc.com/rs/search/combinedrenderer/view.xml?partnerId=2000&keywords=business&target=all"},
    {"name": "Google News Business", "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB"},
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex"},
    {"name": "MarketWatch Top Stories", "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories"},
    {"name": "Al Jazeera Economy", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "WSJ Markets", "url": "https://feeds.content.dowjones.io/public/rss/WSJcomUSBusiness"},
]

# ---------------------------------------------------------------------------
# spaCy Model
# ---------------------------------------------------------------------------
SPACY_MODEL: str = "en_core_web_lg"

# Entity types to extract from spaCy NER
SPACY_ENTITY_TYPES: set[str] = {
    "ORG", "GPE", "LOC", "PRODUCT", "EVENT", "NORP",
    "MONEY", "PERCENT", "QUANTITY",
}
