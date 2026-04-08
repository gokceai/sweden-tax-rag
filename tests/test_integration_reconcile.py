import socket
import uuid

import pytest

from src.core.config import settings
from src.core.security import EncryptionManager
from src.db.chroma_client import VectorDBManager
from src.db.document_repo import DocumentRepository
from src.db.dynamo_client import DynamoDBManager
from src.engine.rag_core import RAGEngine


def _service_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


@pytest.mark.integration
def test_reconcile_and_repair_with_real_stores(monkeypatch):
    if settings.MASTER_ENCRYPTION_KEY is None:
        pytest.skip("MASTER_ENCRYPTION_KEY is required for integration test.")
    if not _service_reachable(settings.CHROMA_HOST, settings.CHROMA_PORT):
        pytest.skip("ChromaDB is not reachable.")
    if "localhost" in settings.DYNAMO_ENDPOINT and not _service_reachable("localhost", 8000):
        pytest.skip("DynamoDB local endpoint is not reachable.")

    class FakeEmbeddingFunction:
        def __init__(self, model_name):
            self.model_name = model_name

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

    vector_db = VectorDBManager()
    table = DynamoDBManager().create_table_if_not_exists()
    document_repo = DocumentRepository(table=table, encryption_manager=EncryptionManager(settings.MASTER_ENCRYPTION_KEY))
    engine = RAGEngine(vector_db=vector_db, document_repo=document_repo, settings=settings)

    only_in_chroma_id = f"it_only_in_chroma_{uuid.uuid4().hex[:10]}"
    only_in_dynamo_id = f"it_only_in_dynamo_{uuid.uuid4().hex[:10]}"

    try:
        assert vector_db.add_or_update_vector(only_in_chroma_id, "Temporary orphan vector")
        assert document_repo.save_document_chunk(
            only_in_dynamo_id,
            "Temporary orphan document",
            {"source": "integration_test", "chunk_index": 0},
        )

        before = engine.reconcile_indexes()
        assert only_in_chroma_id in before["only_in_chroma"]
        assert only_in_dynamo_id in before["only_in_dynamo"]

        repaired = engine.repair_indexes(
            only_in_chroma_action="delete",
            only_in_dynamo_action="rehydrate",
        )
        after = repaired["post_reconcile"]

        assert only_in_chroma_id not in after["only_in_chroma"]
        assert only_in_dynamo_id not in after["only_in_dynamo"]
        assert vector_db.has_vector(only_in_dynamo_id) is True
        assert document_repo.has_document_chunk(only_in_dynamo_id) is True
    finally:
        vector_db.delete_vector(only_in_chroma_id)
        vector_db.delete_vector(only_in_dynamo_id)
        document_repo.delete_document_chunk(only_in_chroma_id)
        document_repo.delete_document_chunk(only_in_dynamo_id)
