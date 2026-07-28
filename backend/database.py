"""
ImpactChain AI — Phase 1 Database Layer (Step 1.5)

MasterDB class handles:
  - SQLite connection lifecycle with context managers
  - Schema initialization (6 tables)
  - Article insertion with entity/relationship tracking
  - Low-confidence queue and failed-extraction storage
  - Deduplication checks
"""

import json
import sqlite3
import uuid
import logging
import re
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

from config import DATABASE_PATH

logger = logging.getLogger(__name__)

# ============================================================================
# Schema DDL
# ============================================================================

_SCHEMA_SQL = """
-- ============================================================
-- TABLE 1: articles
-- ============================================================
CREATE TABLE IF NOT EXISTS articles (
    article_id      TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    source_name     TEXT,
    source_type     TEXT,
    published_at    TEXT,
    ingested_at     TEXT,
    event_category  TEXT,
    is_relevant     BOOLEAN,
    confidence      REAL,
    url             TEXT,
    full_json       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_article_relevance ON articles(is_relevant, confidence);
CREATE INDEX IF NOT EXISTS idx_article_event_category ON articles(event_category);

-- ============================================================
-- TABLE 2: entities
-- ============================================================
CREATE TABLE IF NOT EXISTS entities (
    entity_id       TEXT PRIMARY KEY,
    entity_name     TEXT NOT NULL,
    entity_type     TEXT,
    first_seen_at   TEXT,
    article_count   INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_entity_type ON entities(entity_type);

-- ============================================================
-- TABLE 3: relationships
-- ============================================================
CREATE TABLE IF NOT EXISTS relationships (
    relationship_id     TEXT PRIMARY KEY,
    source_entity_id    TEXT NOT NULL,
    relationship_type   TEXT NOT NULL,
    target_entity_id    TEXT NOT NULL,
    first_seen_at       TEXT,
    occurrence_count    INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_relationship_entities ON relationships(source_entity_id, target_entity_id);

-- ============================================================
-- TABLE 4: economic_chains
-- ============================================================
CREATE TABLE IF NOT EXISTS economic_chains (
    chain_id            TEXT PRIMARY KEY,
    article_id          TEXT NOT NULL REFERENCES articles(article_id),
    chain_steps_json    TEXT NOT NULL,
    primary_commodity   TEXT,
    created_at          TEXT
);

-- ============================================================
-- TABLE 5: low_confidence_queue
-- ============================================================
CREATE TABLE IF NOT EXISTS low_confidence_queue (
    article_id          TEXT PRIMARY KEY,
    title               TEXT,
    confidence          REAL,
    raw_groq_response   TEXT,
    created_at          TEXT
);

-- ============================================================
-- TABLE 6: failed_extractions
-- ============================================================
CREATE TABLE IF NOT EXISTS failed_extractions (
    article_id          TEXT PRIMARY KEY,
    title               TEXT,
    error_message       TEXT,
    raw_groq_response   TEXT,
    created_at          TEXT
);
"""


def _slugify(text: str) -> str:
    """Convert entity name to a slug suitable for entity_id."""
    slug = text.strip().lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "_", slug)
    return slug


class MasterDB:
    """
    SQLite database manager for the Phase 1 master database.

    Usage:
        db = MasterDB()
        db.insert_article(normalized_record)
        db.close()

    Or as a context manager:
        with MasterDB() as db:
            db.insert_article(record)
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or DATABASE_PATH
        # Resolve relative paths from the backend directory
        if not Path(self.db_path).is_absolute():
            self.db_path = str(Path(__file__).resolve().parent / self.db_path)

        # Ensure data directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn: sqlite3.Connection | None = None
        self._connect()
        self._init_schema()

    def _connect(self):
        """Open SQLite connection with optimized settings."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        logger.debug(f"Connected to database at {self.db_path}")

    def _init_schema(self):
        """Create all tables if they don't exist."""
        cursor = self.conn.cursor()
        cursor.executescript(_SCHEMA_SQL)
        self.conn.commit()
        logger.info(f"Database schema initialized at {self.db_path}")

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("Database connection closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def article_exists(self, article_id: str) -> bool:
        """Check if an article_id already exists in the articles table."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM articles WHERE article_id = ? LIMIT 1",
            (article_id,),
        )
        return cursor.fetchone() is not None

    # ------------------------------------------------------------------
    # Main insert
    # ------------------------------------------------------------------

    def insert_article(self, normalized_record: dict | None) -> bool:
        """
        Insert a fully normalized record into the master database.

        Handles:
        - None records (no-op)
        - Low-confidence records → low_confidence_queue
        - Full records → articles + entities + relationships + economic_chains

        Returns True on success, False on failure.
        """
        if normalized_record is None:
            return False

        now = datetime.now(timezone.utc).isoformat()
        article_id = normalized_record.get("article_id", "")

        try:
            # Route low-confidence records
            is_relevant = normalized_record.get("is_relevant", False)
            confidence = normalized_record.get("confidence", 0.0)

            if not is_relevant and confidence < 0.40:
                return self._insert_low_confidence(normalized_record, now)

            # Full insert in a single transaction
            cursor = self.conn.cursor()

            # 1. Insert into articles table
            full_json = json.dumps(normalized_record, ensure_ascii=False)
            cursor.execute(
                """
                INSERT OR IGNORE INTO articles
                    (article_id, title, source_name, source_type, published_at,
                     ingested_at, event_category, is_relevant, confidence, url, full_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article_id,
                    normalized_record.get("title", ""),
                    normalized_record.get("source_name", ""),
                    normalized_record.get("source_type", ""),
                    normalized_record.get("published_at", ""),
                    normalized_record.get("ingested_at", now),
                    normalized_record.get("event_category", ""),
                    is_relevant,
                    confidence,
                    normalized_record.get("url", ""),
                    full_json,
                ),
            )
            logger.info(f"Inserted article {article_id} into articles table")

            # 2. Extract and upsert entities
            all_entities = normalized_record.get("all_entities", {})
            self._upsert_entities(cursor, all_entities, now)

            # 3. Extract and upsert relationships
            relationships = normalized_record.get("relationships", [])
            self._upsert_relationships(cursor, relationships, now)

            # 4. Insert economic chain
            economic_chain = normalized_record.get("economic_impact_chain", [])
            if economic_chain:
                primary_commodity = ""
                commodities = normalized_record.get("primary_commodities", [])
                if commodities:
                    primary_commodity = commodities[0]

                chain_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO economic_chains
                        (chain_id, article_id, chain_steps_json, primary_commodity, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        chain_id,
                        article_id,
                        json.dumps(economic_chain, ensure_ascii=False),
                        primary_commodity,
                        now,
                    ),
                )
                logger.debug(f"Inserted economic chain for article {article_id}")

            self.conn.commit()
            logger.info(f"Successfully committed all data for article {article_id}")
            return True

        except sqlite3.IntegrityError as e:
            # Duplicate article_id — expected on re-runs
            logger.warning(f"Integrity error for article {article_id} (likely duplicate): {e}")
            self.conn.rollback()
            return False
        except Exception as e:
            logger.error(f"Database error inserting article {article_id}: {e}", exc_info=True)
            self.conn.rollback()
            return False

    # ------------------------------------------------------------------
    # Entity upsert
    # ------------------------------------------------------------------

    def _upsert_entities(self, cursor: sqlite3.Cursor, all_entities: dict, now: str):
        """Insert or increment entity counts from the all_entities scaffold."""
        # Map scaffold keys to entity types
        type_map = {
            "organizations": "organization",
            "locations": "location",
            "products_mentioned": "commodity",
            "events_mentioned": "event",
            "norp_mentioned": "organization",  # political/national groups → org
        }

        for key, entity_type in type_map.items():
            entities = all_entities.get(key, [])
            for name in entities:
                if not name:
                    continue
                entity_id = _slugify(name)
                self._upsert_single_entity(cursor, entity_id, name, entity_type, now)

        # Also upsert entities from entity_roles (may include entities not in spaCy scaffold)
        entity_roles = all_entities.get("entity_roles", {})
        for name, role in entity_roles.items():
            if not name:
                continue
            entity_id = _slugify(name)
            # Determine type from role
            role_type_map = {
                "supplier": "organization",
                "consumer": "organization",
                "logistics_node": "location",
                "regulatory_body": "organization",
                "disruption_cause": "organization",
                "price_influencer": "organization",
            }
            entity_type = role_type_map.get(role, "organization")
            self._upsert_single_entity(cursor, entity_id, name, entity_type, now)

    def _upsert_single_entity(
        self, cursor: sqlite3.Cursor, entity_id: str, name: str,
        entity_type: str, now: str
    ):
        """Insert a new entity or increment its article_count."""
        cursor.execute(
            "SELECT article_count FROM entities WHERE entity_id = ?",
            (entity_id,),
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE entities SET article_count = article_count + 1 WHERE entity_id = ?",
                (entity_id,),
            )
            logger.debug(f"Incremented entity '{name}' count to {row['article_count'] + 1}")
        else:
            cursor.execute(
                """
                INSERT INTO entities (entity_id, entity_name, entity_type, first_seen_at, article_count)
                VALUES (?, ?, ?, ?, 1)
                """,
                (entity_id, name.lower(), entity_type, now),
            )
            logger.debug(f"Inserted new entity '{name}' (type={entity_type})")

    # ------------------------------------------------------------------
    # Relationship upsert
    # ------------------------------------------------------------------

    def _upsert_relationships(self, cursor: sqlite3.Cursor, relationships: list, now: str):
        """Insert or increment relationship occurrence counts."""
        for triple in relationships:
            if not isinstance(triple, (list, tuple)) or len(triple) != 3:
                logger.warning(f"Skipping malformed relationship triple: {triple}")
                continue

            source, rel_type, target = triple
            source = str(source).lower()
            target = str(target).lower()
            rel_type = str(rel_type).lower()

            source_id = _slugify(source)
            target_id = _slugify(target)
            relationship_id = f"{source_id}::{rel_type}::{target_id}"

            cursor.execute(
                "SELECT occurrence_count FROM relationships WHERE relationship_id = ?",
                (relationship_id,),
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE relationships SET occurrence_count = occurrence_count + 1 WHERE relationship_id = ?",
                    (relationship_id,),
                )
                logger.debug(
                    f"Incremented relationship '{source} {rel_type} {target}' "
                    f"count to {row['occurrence_count'] + 1}"
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO relationships
                        (relationship_id, source_entity_id, relationship_type,
                         target_entity_id, first_seen_at, occurrence_count)
                    VALUES (?, ?, ?, ?, ?, 1)
                    """,
                    (relationship_id, source_id, rel_type, target_id, now),
                )
                logger.debug(f"Inserted new relationship: {source} {rel_type} {target}")

    # ------------------------------------------------------------------
    # Low confidence queue
    # ------------------------------------------------------------------

    def _insert_low_confidence(self, record: dict, now: str) -> bool:
        """Insert a low-confidence article into the queue table."""
        try:
            cursor = self.conn.cursor()

            # Still insert into articles table for dedup tracking
            full_json = json.dumps(record, ensure_ascii=False)
            cursor.execute(
                """
                INSERT OR IGNORE INTO articles
                    (article_id, title, source_name, source_type, published_at,
                     ingested_at, event_category, is_relevant, confidence, url, full_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("article_id", ""),
                    record.get("title", ""),
                    record.get("source_name", ""),
                    record.get("source_type", ""),
                    record.get("published_at", ""),
                    record.get("ingested_at", now),
                    record.get("event_category", ""),
                    False,
                    record.get("confidence", 0.0),
                    record.get("url", ""),
                    full_json,
                ),
            )

            # Insert into low_confidence_queue
            cursor.execute(
                """
                INSERT OR IGNORE INTO low_confidence_queue
                    (article_id, title, confidence, raw_groq_response, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.get("article_id", ""),
                    record.get("title", ""),
                    record.get("confidence", 0.0),
                    full_json,  # store the full record for debugging
                    now,
                ),
            )
            self.conn.commit()
            logger.info(
                f"Low-confidence article {record.get('article_id', '')} "
                f"(confidence={record.get('confidence', 0):.2f}) → low_confidence_queue"
            )
            return True
        except Exception as e:
            logger.error(f"Error inserting low-confidence article: {e}", exc_info=True)
            self.conn.rollback()
            return False

    # ------------------------------------------------------------------
    # Failed extractions
    # ------------------------------------------------------------------

    def insert_failed_extraction(
        self, article: dict, error_message: str, raw_groq_response: str | None = None
    ) -> bool:
        """Store a failed extraction for debugging."""
        now = datetime.now(timezone.utc).isoformat()
        article_id = article.get("article_id", "")
        try:
            cursor = self.conn.cursor()

            # Insert into articles table first so dedup works on re-runs
            cursor.execute(
                """
                INSERT OR IGNORE INTO articles
                    (article_id, title, source_name, source_type, published_at,
                     ingested_at, event_category, is_relevant, confidence, url, full_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article_id,
                    article.get("title", ""),
                    article.get("source_name", ""),
                    article.get("source_type", ""),
                    article.get("published_at", ""),
                    now,
                    "",
                    False,
                    0.0,
                    article.get("url", ""),
                    json.dumps(article, ensure_ascii=False),
                ),
            )

            cursor.execute(
                """
                INSERT OR IGNORE INTO failed_extractions
                    (article_id, title, error_message, raw_groq_response, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    article_id,
                    article.get("title", ""),
                    error_message,
                    raw_groq_response or "",
                    now,
                ),
            )
            self.conn.commit()
            logger.info(f"Stored failed extraction for article {article_id}: {error_message}")
            return True
        except Exception as e:
            logger.error(f"Error storing failed extraction: {e}", exc_info=True)
            self.conn.rollback()
            return False
