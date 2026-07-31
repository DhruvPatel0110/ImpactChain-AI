"""
ImpactChain AI — Phase 2.3: ChromaDB Vector Store

Responsible for:
  - Initialising ChromaDB in persistent mode at data/chroma_db/
  - Creating / loading the 'supply_chain_articles' collection with cosine space
  - get_existing_ids()     → Set of already-embedded article IDs (skip logic)
  - add_article()          → Single-article upsert
  - batch_add_articles()   → Batch upsert (50 articles per ChromaDB call)
  - query()                → Semantic similarity search (used in Phase 3)

Design notes:
  - Cosine distance is mandatory: similarity is angle-based not magnitude-based,
    which is more accurate for text semantics.
  - Metadata must be flat scalars (str / int / float / bool). No nested dicts
    or lists — ChromaDB will reject them. Arrays are embedded in the compound
    string so they remain semantically searchable despite not being in metadata.
  - ChromaDB PersistentClient flushes to disk automatically; no manual save.
  - Errors on individual articles are logged and skipped; the batch continues.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ChromaDB path — resolved relative to this file's location (backend/)
# data/chroma_db/ sits alongside data/master.db
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).resolve().parent
_CHROMA_PATH = str(_BACKEND_DIR / "data" / "chroma_db")
_COLLECTION_NAME = "supply_chain_articles"
_BATCH_SIZE = 50  # Max documents per ChromaDB add() call


class VectorStore:
    """
    ChromaDB wrapper for supply-chain article embeddings.

    Lifecycle:
        vs = VectorStore()               # initialises client + collection
        vs.batch_add_articles(batch)     # insert articles
        results = vs.query(embedding)    # similarity search

    The underlying ChromaDB PersistentClient persists to disk automatically
    on every write. No manual save or flush is required.
    """

    def __init__(self, chroma_path: Optional[str] = None):
        """
        Initialise ChromaDB persistent client and get-or-create collection.

        Args:
            chroma_path: Override the default data/chroma_db/ path.
                         Mainly used in tests to point at a temp directory.
        """
        self._path = chroma_path or _CHROMA_PATH

        # Ensure the directory exists (ChromaDB will also create it, but being
        # explicit is safer across different OS environments)
        Path(self._path).mkdir(parents=True, exist_ok=True)

        try:
            import chromadb

            self._client = chromadb.PersistentClient(path=self._path)
            self._collection = self._client.get_or_create_collection(
                name=_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                f"ChromaDB initialised at '{self._path}' — "
                f"collection '{_COLLECTION_NAME}' has "
                f"{self._collection.count()} existing documents."
            )
        except Exception as e:
            logger.error(f"Failed to initialise ChromaDB: {e}", exc_info=True)
            raise

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_existing_ids(self) -> set[str]:
        """
        Return the set of all article_ids currently stored in the collection.

        Used by Phase 2.1 to skip articles that are already embedded,
        ensuring idempotent re-runs (no duplicate embeddings on restart).

        Returns:
            Set of article_id strings. Empty set if collection is empty.
        """
        try:
            result = self._collection.get(include=[])
            ids: list[str] = result.get("ids", [])
            logger.debug(f"ChromaDB has {len(ids)} existing article IDs.")
            return set(ids)
        except Exception as e:
            logger.error(f"Failed to fetch existing IDs from ChromaDB: {e}", exc_info=True)
            return set()

    # ------------------------------------------------------------------
    # Write — single article
    # ------------------------------------------------------------------

    def add_article(
        self,
        article_id: str,
        compound_string: str,
        embedding_vector: list[float],
        article_metadata: dict,
    ) -> bool:
        """
        Add a single article embedding to ChromaDB.

        Args:
            article_id:       SHA-256 hash of the article URL (PK in master.db).
            compound_string:  Dense semantic string used to generate the embedding.
                              Stored as ChromaDB 'document' for inspection.
            embedding_vector: 384-float list from sentence-transformers.
            article_metadata: Flat dict (str/int/float/bool values only).

        Returns:
            True on success, False on failure (error is logged, not raised).
        """
        try:
            self._collection.add(
                ids=[article_id],
                embeddings=[embedding_vector],
                documents=[compound_string],
                metadatas=[article_metadata],
            )
            logger.debug(f"Added article {article_id} to ChromaDB.")
            return True
        except Exception as e:
            logger.error(
                f"Failed to add article {article_id} to ChromaDB: {e}",
                exc_info=True,
            )
            return False

    # ------------------------------------------------------------------
    # Write — batch
    # ------------------------------------------------------------------

    def batch_add_articles(
        self,
        articles_data: list[tuple[str, str, list[float], dict]],
    ) -> int:
        """
        Add multiple article embeddings to ChromaDB in batched calls.

        Each element in articles_data is a 4-tuple:
            (article_id, compound_string, embedding_vector, metadata)

        The batch is split into chunks of _BATCH_SIZE (50) to stay within
        ChromaDB's recommended per-call limits. All chunks are committed
        before this method returns.

        Args:
            articles_data: List of (article_id, compound_str, embedding, meta)
                           tuples. See add_article() for field details.

        Returns:
            Number of articles successfully added across all batches.
        """
        if not articles_data:
            logger.debug("batch_add_articles called with empty list — nothing to do.")
            return 0

        total_added = 0
        total_batches = (len(articles_data) + _BATCH_SIZE - 1) // _BATCH_SIZE

        for batch_idx in range(total_batches):
            start = batch_idx * _BATCH_SIZE
            end = start + _BATCH_SIZE
            chunk = articles_data[start:end]

            ids = []
            embeddings = []
            documents = []
            metadatas = []

            for article_id, compound_string, embedding_vector, metadata in chunk:
                ids.append(article_id)
                embeddings.append(embedding_vector)
                documents.append(compound_string)
                metadatas.append(metadata)

            try:
                self._collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas,
                )
                total_added += len(chunk)
                logger.info(
                    f"ChromaDB batch {batch_idx + 1}/{total_batches}: "
                    f"added {len(chunk)} articles "
                    f"(total so far: {total_added}/{len(articles_data)})."
                )
            except Exception as e:
                logger.error(
                    f"ChromaDB batch {batch_idx + 1}/{total_batches} failed: {e}. "
                    f"Falling back to individual adds for this chunk.",
                    exc_info=True,
                )
                # Graceful fallback: try each article individually so a single
                # bad document doesn't block the rest of the batch
                for art_id, doc, emb, meta in zip(ids, documents, embeddings, metadatas):
                    if self.add_article(art_id, doc, emb, meta):
                        total_added += 1

        logger.info(
            f"batch_add_articles complete: {total_added}/{len(articles_data)} articles added."
        )
        return total_added

    # ------------------------------------------------------------------
    # Query (Phase 3)
    # ------------------------------------------------------------------

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: Optional[dict] = None,
    ) -> dict:
        """
        Retrieve the top-k most semantically similar articles.

        Uses cosine similarity (configured at collection creation). Returned
        distances are cosine distances in [0, 2]:
          0.0  → identical vectors
          1.0  → orthogonal (unrelated)
          2.0  → opposite direction (extremely dissimilar)

        In practice, supply-chain articles with distance < 0.5 are strongly
        related to the query.

        Args:
            query_embedding: 384-float list from the same sentence-transformers
                             model used during ingestion. MUST be the same model.
            top_k:           Number of results to return (default 10).
            filters:         Optional ChromaDB 'where' clause dict for metadata
                             filtering. Example:
                               {"event_category": "geopolitical"}
                               {"published_at": {"$gte": 1700000000}}

        Returns:
            Raw ChromaDB query result dict with keys:
              - ids:       list[list[str]]   — article IDs, inner list = one query
              - distances: list[list[float]] — cosine distances (lower = better)
              - metadatas: list[list[dict]]  — stored metadata per result
              - documents: list[list[str]]   — compound strings per result
        """
        try:
            query_kwargs: dict = {
                "query_embeddings": [query_embedding],
                "n_results": top_k,
                "include": ["distances", "metadatas", "documents"],
            }
            if filters:
                query_kwargs["where"] = filters

            results = self._collection.query(**query_kwargs)
            logger.debug(
                f"ChromaDB query returned {len(results.get('ids', [[]])[0])} results "
                f"(top_k={top_k}, filters={filters})."
            )
            return results

        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}", exc_info=True)
            # Return empty result structure so callers can handle gracefully
            return {"ids": [[]], "distances": [[]], "metadatas": [[]], "documents": [[]]}

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return the number of documents currently in the collection."""
        try:
            return self._collection.count()
        except Exception as e:
            logger.error(f"Failed to get ChromaDB count: {e}")
            return 0
