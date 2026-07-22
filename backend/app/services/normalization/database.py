"""
Normalization Pipeline — Database Layer

SQLite connection management and schema initialization.
All 5 tables created here:
  - raw_articles (Step 1 output)
  - extracted_entities (Step 2 output)
  - consolidated_articles (Step 3 intermediate)
  - master_events (Step 4 output)
  - master_event_sources (Step 4 junction)

Fresh start each run: DROP all tables before CREATE.
"""

import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from loguru import logger


# Default DB path: backend/data/impactchain.db
_DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "impactchain.db"


def get_db_path() -> str:
    """
    Return SQLite database file path.
    Override with IMPACTCHAIN_DB_PATH environment variable.
    """
    return os.getenv("IMPACTCHAIN_DB_PATH", str(_DEFAULT_DB_PATH))


@contextmanager
def get_connection():
    """
    Context manager for SQLite connections.
    Enables WAL mode, foreign keys, and Row factory.
    Auto-creates the database directory if it does not exist.
    """
    db_path = get_db_path()
    
    # Ensure the parent directory exists before connecting
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()



# =============================================================================
# Schema DDL
# =============================================================================

_SCHEMA_SQL = """
-- ============================================================
-- TABLE 1: raw_articles (Step 1 output)
-- ============================================================
CREATE TABLE IF NOT EXISTS raw_articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name     TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    headline        TEXT,
    url             TEXT UNIQUE NOT NULL,
    full_text       TEXT,
    summary         TEXT,
    author          TEXT,
    published_at    TEXT,
    language        TEXT DEFAULT 'en',
    raw_payload     TEXT,
    fetched_at      TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    processed       BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_raw_articles_source ON raw_articles(source_name);
CREATE INDEX IF NOT EXISTS idx_raw_articles_processed ON raw_articles(processed);
CREATE INDEX IF NOT EXISTS idx_raw_articles_published ON raw_articles(published_at);

-- ============================================================
-- TABLE 2: extracted_entities (Step 2 output)
-- ============================================================
CREATE TABLE IF NOT EXISTS extracted_entities (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id          INTEGER NOT NULL REFERENCES raw_articles(id) ON DELETE CASCADE,
    orgs                TEXT DEFAULT '[]',
    gpe_locations       TEXT DEFAULT '[]',
    geo_locations       TEXT DEFAULT '[]',
    events_named        TEXT DEFAULT '[]',
    commodities_found   TEXT DEFAULT '[]',
    sc_signals_found    TEXT DEFAULT '[]',
    money_mentions      TEXT DEFAULT '[]',
    percent_mentions    TEXT DEFAULT '[]',
    quantitative_score  REAL NOT NULL DEFAULT 0,
    is_sc_relevant      BOOLEAN DEFAULT NULL,
    extracted_at        TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_ee_article ON extracted_entities(article_id);
CREATE INDEX IF NOT EXISTS idx_ee_relevant ON extracted_entities(is_sc_relevant);

-- ============================================================
-- TABLE 3: consolidated_articles (Step 3 intermediate)
-- ============================================================
CREATE TABLE IF NOT EXISTS consolidated_articles (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    event_cluster_id    TEXT NOT NULL,
    article_id          INTEGER NOT NULL REFERENCES raw_articles(id),
    is_primary          BOOLEAN DEFAULT 0,
    clustered_at        TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_ca_cluster ON consolidated_articles(event_cluster_id);

-- ============================================================
-- TABLE 4: master_events (Step 4 output)
-- ============================================================
CREATE TABLE IF NOT EXISTS master_events (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    event_uid               TEXT UNIQUE NOT NULL,
    primary_commodity       TEXT,
    primary_entity_type     TEXT,
    headline                TEXT,
    summary                 TEXT,
    commodities             TEXT DEFAULT '[]',
    companies               TEXT DEFAULT '[]',
    regions                 TEXT DEFAULT '[]',
    locations               TEXT DEFAULT '[]',
    sc_signals              TEXT DEFAULT '[]',
    price_mentions          TEXT DEFAULT '[]',
    rate_changes            TEXT DEFAULT '[]',
    source_count            INTEGER DEFAULT 1,
    article_count           INTEGER DEFAULT 1,
    unique_sources          TEXT DEFAULT '[]',
    primary_article_id      INTEGER REFERENCES raw_articles(id),
    event_start             TEXT,
    event_last_seen         TEXT,
    created_at              TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at              TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    relevance_score         REAL DEFAULT 0,
    embedding_id            TEXT,
    significance_tier       TEXT,
    significance_score      REAL
);

CREATE INDEX IF NOT EXISTS idx_me_commodity ON master_events(primary_commodity);
CREATE INDEX IF NOT EXISTS idx_me_relevance ON master_events(relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_me_event_start ON master_events(event_start DESC);

-- ============================================================
-- TABLE 5: master_event_sources (Step 4 junction)
-- ============================================================
CREATE TABLE IF NOT EXISTS master_event_sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        INTEGER NOT NULL REFERENCES master_events(id) ON DELETE CASCADE,
    article_id      INTEGER NOT NULL REFERENCES raw_articles(id),
    is_primary      BOOLEAN DEFAULT 0,
    source_name     TEXT,
    contribution    TEXT,
    UNIQUE(event_id, article_id)
);

CREATE INDEX IF NOT EXISTS idx_mes_event ON master_event_sources(event_id);
"""

_DROP_SQL = """
DROP TABLE IF EXISTS master_event_sources;
DROP TABLE IF EXISTS master_events;
DROP TABLE IF EXISTS consolidated_articles;
DROP TABLE IF EXISTS extracted_entities;
DROP TABLE IF EXISTS raw_articles;
"""


def init_database(fresh: bool = True) -> None:
    """
    Initialize the SQLite database.

    Args:
        fresh: If True, DROP all tables before creating (clean slate each run).
    """
    db_path = get_db_path()

    # Ensure data directory exists
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        cursor = conn.cursor()

        if fresh:
            logger.info(f"Dropping all tables for fresh start (DB: {db_path})")
            cursor.executescript(_DROP_SQL)

        logger.info(f"Creating schema (5 tables) in {db_path}")
        cursor.executescript(_SCHEMA_SQL)
        conn.commit()

    logger.info("Database initialization complete")
