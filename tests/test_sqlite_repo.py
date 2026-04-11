import sqlite3

import pytest
from cryptography.fernet import Fernet

from src.core.exceptions import InfrastructureError
from src.core.security import EncryptionManager
from src.db.sqlite_document_repo import SQLiteDocumentRepository


def _build_repo(tmp_path, key: str | None = None) -> SQLiteDocumentRepository:
    fernet_key = key or Fernet.generate_key().decode("utf-8")
    db_path = tmp_path / "documents.db"
    return SQLiteDocumentRepository(
        db_path=str(db_path),
        encryption_manager=EncryptionManager(fernet_key),
    )


def test_save_get_delete_and_has_document_chunk(tmp_path):
    repo = _build_repo(tmp_path)

    assert repo.save_document_chunk(
        "chunk-1",
        "secret text",
        {"source": "unit", "chunk_index": 7, "topic": "vat"},
    )
    assert repo.has_document_chunk("chunk-1") is True

    item = repo.get_document_chunk("chunk-1")
    assert item is not None
    assert item["chunk_id"] == "chunk-1"
    assert item["source"] == "unit"
    assert item["chunk_index"] == 7
    assert item["topic"] == "vat"
    assert item["decrypted_text"] == "secret text"

    repo.delete_document_chunk("chunk-1")
    assert repo.has_document_chunk("chunk-1") is False
    assert repo.get_document_chunk("chunk-1") is None


def test_list_chunk_ids_and_ping(tmp_path):
    repo = _build_repo(tmp_path)
    assert repo.ping() is True

    repo.save_document_chunk("chunk-a", "text a", {"source": "s", "chunk_index": 1})
    repo.save_document_chunk("chunk-b", "text b", {"source": "s", "chunk_index": 2})

    assert repo.list_chunk_ids() == {"chunk-a", "chunk-b"}


def test_save_document_chunk_is_idempotent_upsert(tmp_path):
    repo = _build_repo(tmp_path)

    assert repo.save_document_chunk("chunk-dup", "first", {"source": "v1", "chunk_index": 0})
    assert repo.save_document_chunk("chunk-dup", "second", {"source": "v2", "chunk_index": 1})

    with sqlite3.connect(repo.db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM document_chunks WHERE chunk_id = ?",
            ("chunk-dup",),
        ).fetchone()[0]
    assert count == 1

    item = repo.get_document_chunk("chunk-dup")
    assert item is not None
    assert item["decrypted_text"] == "second"
    assert item["source"] == "v2"
    assert item["chunk_index"] == 1


def test_get_document_chunk_raises_on_wrong_key(tmp_path):
    key_a = Fernet.generate_key().decode("utf-8")
    key_b = Fernet.generate_key().decode("utf-8")
    db_path = tmp_path / "documents.db"

    writer_repo = SQLiteDocumentRepository(
        db_path=str(db_path),
        encryption_manager=EncryptionManager(key_a),
    )
    assert writer_repo.save_document_chunk("chunk-1", "sensitive", {"source": "x", "chunk_index": 0})

    reader_repo = SQLiteDocumentRepository(
        db_path=str(db_path),
        encryption_manager=EncryptionManager(key_b),
    )

    with pytest.raises(InfrastructureError):
        reader_repo.get_document_chunk("chunk-1")
