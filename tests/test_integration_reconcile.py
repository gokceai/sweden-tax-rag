import uuid

import pytest
from cryptography.fernet import Fernet

from src.core.config import settings
from src.core.security import EncryptionManager
from src.db.chroma_client import VectorDBManager
from src.db.sqlite_document_repo import SQLiteDocumentRepository
from src.engine.rag_core import RAGEngine


@pytest.mark.integration
def test_reconcile_and_repair_with_real_stores(monkeypatch, tmp_path):
    class FakeEmbeddingFunction:
        def __init__(self, model_name, device="cpu"):
            self.model_name = model_name
            self.device = device

        def __call__(self, input):
            return [[0.1, 0.2, 0.3] for _ in input]

        def name(self):
            return "default"

        def is_legacy(self):
            return True

    monkeypatch.setattr(
        "src.db.chroma_client.embedding_functions.SentenceTransformerEmbeddingFunction",
        FakeEmbeddingFunction,
    )
    monkeypatch.setattr("src.core.config.settings.CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))

    vector_db = VectorDBManager()
    encryption_key = settings.MASTER_ENCRYPTION_KEY or Fernet.generate_key().decode("utf-8")
    document_repo = SQLiteDocumentRepository(
        db_path=str(tmp_path / "documents.db"),
        encryption_manager=EncryptionManager(encryption_key),
    )
    engine = RAGEngine(vector_db=vector_db, document_repo=document_repo, settings=settings)

    only_in_chroma_id = f"it_only_in_chroma_{uuid.uuid4().hex[:10]}"
    only_in_document_store_id = f"it_only_in_document_store_{uuid.uuid4().hex[:10]}"

    try:
        assert vector_db.add_or_update_vector(only_in_chroma_id, "Temporary orphan vector")
        assert document_repo.save_document_chunk(
            only_in_document_store_id,
            "Temporary orphan document",
            {"source": "integration_test", "chunk_index": 0},
        )

        before = engine.reconcile_indexes()
        assert only_in_chroma_id in before["only_in_chroma"]
        assert only_in_document_store_id in before["only_in_document_store"]

        repaired = engine.repair_indexes(
            only_in_chroma_action="delete",
            only_in_document_store_action="rehydrate",
        )
        after = repaired["post_reconcile"]

        assert only_in_chroma_id not in after["only_in_chroma"]
        assert only_in_document_store_id not in after["only_in_document_store"]
        assert vector_db.has_vector(only_in_document_store_id) is True
        assert document_repo.has_document_chunk(only_in_document_store_id) is True
    finally:
        vector_db.delete_vector(only_in_chroma_id)
        vector_db.delete_vector(only_in_document_store_id)
        document_repo.delete_document_chunk(only_in_chroma_id)
        document_repo.delete_document_chunk(only_in_document_store_id)
