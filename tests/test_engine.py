import pytest

from src.core.config import settings
from src.core.exceptions import DataIntegrityError
from src.engine.rag_core import RAGEngine


class FakeVectorDB:
    def __init__(self, add_result=True):
        self.add_result = add_result
        self.deleted_ids = []
        self.search_result = ["id_1"]

    def add_or_update_vector(self, chunk_id, text):
        return self.add_result

    def delete_vector(self, chunk_id):
        self.deleted_ids.append(chunk_id)

    def search_similar_ids(self, query_text, n_results=2):
        return self.search_result[:n_results]

    def list_ids(self):
        return {"chunk-1", "chunk-2"}


class FakeDocumentRepo:
    def __init__(self, save_result=True):
        self.save_result = save_result
        self.deleted_ids = []

    def save_document_chunk(self, chunk_id, original_text, metadata):
        return self.save_result

    def delete_document_chunk(self, chunk_id):
        self.deleted_ids.append(chunk_id)

    def get_document_chunk(self, chunk_id):
        return {"decrypted_text": "retrieved context"}

    def list_chunk_ids(self):
        return {"chunk-2", "chunk-3"}


def test_ingest_success_counts_chunks():
    vector_db = FakeVectorDB(add_result=True)
    repo = FakeDocumentRepo(save_result=True)
    engine = RAGEngine(vector_db=vector_db, document_repo=repo, settings=settings)

    count = engine.ingest_document("a" * 1000, "source")

    assert count > 0


def test_ingest_rolls_back_when_dynamo_write_fails():
    vector_db = FakeVectorDB(add_result=True)
    repo = FakeDocumentRepo(save_result=False)
    engine = RAGEngine(vector_db=vector_db, document_repo=repo, settings=settings)

    with pytest.raises(DataIntegrityError):
        engine.ingest_document("b" * 800, "source")

    assert len(vector_db.deleted_ids) == 1


def test_ingest_rolls_back_when_vector_write_fails():
    vector_db = FakeVectorDB(add_result=False)
    repo = FakeDocumentRepo(save_result=True)
    engine = RAGEngine(vector_db=vector_db, document_repo=repo, settings=settings)

    with pytest.raises(DataIntegrityError):
        engine.ingest_document("c" * 800, "source")

    assert len(repo.deleted_ids) == 1


def test_retrieve_context_returns_decrypted_texts():
    vector_db = FakeVectorDB(add_result=True)
    repo = FakeDocumentRepo(save_result=True)
    engine = RAGEngine(vector_db=vector_db, document_repo=repo, settings=settings)

    contexts = engine.retrieve_context("vat", top_k=1)

    assert contexts == ["retrieved context"]


def test_ingest_is_idempotent_for_same_input():
    vector_db = FakeVectorDB(add_result=True)
    repo = FakeDocumentRepo(save_result=True)
    engine = RAGEngine(vector_db=vector_db, document_repo=repo, settings=settings)

    first = engine._build_chunk_id("source", 0, "same chunk")
    second = engine._build_chunk_id("source", 0, "same chunk")

    assert first == second


def test_reconcile_indexes_reports_orphans():
    vector_db = FakeVectorDB(add_result=True)
    repo = FakeDocumentRepo(save_result=True)
    engine = RAGEngine(vector_db=vector_db, document_repo=repo, settings=settings)

    result = engine.reconcile_indexes()

    assert result["is_consistent"] is False
    assert result["only_in_chroma"] == ["chunk-1"]
    assert result["only_in_dynamo"] == ["chunk-3"]


def test_repair_indexes_delete_and_rehydrate():
    vector_db = FakeVectorDB(add_result=True)
    repo = FakeDocumentRepo(save_result=True)
    engine = RAGEngine(vector_db=vector_db, document_repo=repo, settings=settings)

    result = engine.repair_indexes(
        only_in_chroma_action="delete",
        only_in_dynamo_action="rehydrate",
    )

    assert result["actions"]["only_in_chroma_action"] == "delete"
    assert result["actions"]["only_in_dynamo_action"] == "rehydrate"
    assert result["repaired"]["only_in_chroma"] == ["chunk-1"]
    assert result["repaired"]["only_in_dynamo"] == ["chunk-3"]
