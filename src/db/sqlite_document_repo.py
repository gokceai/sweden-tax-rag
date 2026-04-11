"""
SQLiteDocumentRepository — drop-in replacement for DynamoDB-backed DocumentRepository.

Design decisions:
- Interface is intentionally identical to DocumentRepository so no other layer needs
  to know which backend is active.
- Fernet encryption/decryption happens here, same as the DynamoDB version.
- Thread safety: a per-instance Lock guards every sqlite3 call. Connections are opened
  per-operation (safest pattern for multi-threaded use without a connection pool).
- Schema uses INSERT OR REPLACE (UPSERT) so ingest remains idempotent.
"""

import json
import logging
import sqlite3
import threading

from src.core.exceptions import InfrastructureError

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id       TEXT PRIMARY KEY,
    encrypted_text TEXT NOT NULL,
    source         TEXT DEFAULT 'unknown',
    chunk_index    INTEGER DEFAULT 0,
    extra_metadata TEXT DEFAULT '{}'
)
"""


class SQLiteDocumentRepository:
    def __init__(self, db_path: str, encryption_manager):
        self.db_path = db_path
        self.encryption_manager = encryption_manager
        self._lock = threading.Lock()
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                conn.execute(_SCHEMA)
                conn.commit()
            logger.info("SQLite document store ready at '%s'.", self.db_path)
        except Exception as e:
            raise InfrastructureError(f"SQLite initialization failed: {e}") from e

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Public interface (mirrors DocumentRepository)
    # ------------------------------------------------------------------

    def save_document_chunk(self, chunk_id: str, original_text: str, metadata: dict) -> bool:
        """Encrypt and upsert chunk payload into SQLite."""
        try:
            encrypted_text = self.encryption_manager.encrypt_data(original_text)
            source = metadata.get("source", "unknown")
            chunk_index = metadata.get("chunk_index", 0)
            extra = {
                k: v
                for k, v in metadata.items()
                if k not in {
                    "chunk_id", "source", "chunk_index",
                    "encrypted_text", "decrypted_text", "text",
                }
                and v is not None
            }
            with self._lock, self._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO document_chunks
                        (chunk_id, encrypted_text, source, chunk_index, extra_metadata)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(chunk_id) DO UPDATE SET
                        encrypted_text = excluded.encrypted_text,
                        source         = excluded.source,
                        chunk_index    = excluded.chunk_index,
                        extra_metadata = excluded.extra_metadata
                    """,
                    (chunk_id, encrypted_text, source, chunk_index, json.dumps(extra)),
                )
                conn.commit()
            logger.info("Chunk '%s' encrypted and saved.", chunk_id)
            return True
        except Exception as e:
            logger.error("Chunk save failed (%s): %s", chunk_id, e)
            return False

    def get_document_chunk(self, chunk_id: str) -> dict | None:
        """Read and decrypt chunk from SQLite."""
        try:
            with self._lock, self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM document_chunks WHERE chunk_id = ?", (chunk_id,)
                ).fetchone()
            if row is None:
                logger.warning("Chunk '%s' not found.", chunk_id)
                return None
            result = dict(row)
            result["decrypted_text"] = self.encryption_manager.decrypt_data(
                result.pop("encrypted_text")
            )
            extra = json.loads(result.pop("extra_metadata", "{}"))
            result.update(extra)
            return result
        except Exception as e:
            logger.error("Chunk read failed (%s): %s", chunk_id, e)
            raise InfrastructureError(f"SQLite read failed for {chunk_id}: {e}") from e

    def has_document_chunk(self, chunk_id: str) -> bool:
        try:
            with self._lock, self._conn() as conn:
                row = conn.execute(
                    "SELECT 1 FROM document_chunks WHERE chunk_id = ? LIMIT 1", (chunk_id,)
                ).fetchone()
            return row is not None
        except Exception as e:
            logger.error("Chunk existence check failed (%s): %s", chunk_id, e)
            return False

    def delete_document_chunk(self, chunk_id: str) -> None:
        try:
            with self._lock, self._conn() as conn:
                conn.execute(
                    "DELETE FROM document_chunks WHERE chunk_id = ?", (chunk_id,)
                )
                conn.commit()
        except Exception as e:
            raise InfrastructureError(f"SQLite delete failed for {chunk_id}: {e}") from e

    def list_chunk_ids(self) -> set[str]:
        try:
            with self._lock, self._conn() as conn:
                rows = conn.execute(
                    "SELECT chunk_id FROM document_chunks"
                ).fetchall()
            return {row[0] for row in rows}
        except Exception as e:
            raise InfrastructureError(f"SQLite list IDs failed: {e}") from e

    def ping(self) -> bool:
        """Lightweight liveness check — verifies the DB file is accessible and schema exists."""
        try:
            with self._lock, self._conn() as conn:
                conn.execute("SELECT 1 FROM document_chunks LIMIT 1")
            return True
        except Exception as e:
            logger.error("SQLite ping failed: %s", e)
            return False
