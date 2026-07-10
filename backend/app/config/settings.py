"""
Central configuration for the entire application.

Loads:
- Environment variables (.env)
- Future configuration files

Every other module imports values from here.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ===========================
# API KEYS
# ===========================

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# ===========================
# RSS FEEDS
# ===========================

with open(
    Path(__file__).parent / "rss_feeds.json",
    "r",
    encoding="utf-8"
) as f:
    RSS_FEEDS = json.load(f)