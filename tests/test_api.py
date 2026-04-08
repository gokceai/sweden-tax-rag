from fastapi.testclient import TestClient

from src.api.main import app


class FakeRagEngine:
    def ingest_document(self, document_text, source_name):
        return 2

    def retrieve_context(self, query, top_k):
        return ["context a", "context b"]

    def reconcile_indexes(self):
        return {
            "total_chroma_ids": 2,
            "total_dynamo_ids": 2,
            "only_in_chroma": [],
            "only_in_dynamo": [],
            "is_consistent": True,
        }


class FakeAnswerGenerator:
    def generate_answer(self, query, contexts):
        return "grounded answer"


def test_ingest_endpoint(monkeypatch):
    monkeypatch.setattr("src.api.main.get_rag_engine", lambda: FakeRagEngine())
    client = TestClient(app)

    response = client.post(
        "/api/v1/ingest",
        json={"document_text": "x" * 20, "source_name": "source.txt"},
    )

    assert response.status_code == 200
    assert response.json()["chunks_processed"] == 2


def test_retrieve_endpoint(monkeypatch):
    monkeypatch.setattr("src.api.main.get_rag_engine", lambda: FakeRagEngine())
    monkeypatch.setattr("src.api.main.get_answer_generator", lambda: FakeAnswerGenerator())
    client = TestClient(app)

    response = client.post("/api/v1/retrieve", json={"query": "vat rate", "top_k": 2})

    assert response.status_code == 200
    assert response.json()["answer"] == "grounded answer"


def test_reconcile_endpoint(monkeypatch):
    monkeypatch.setattr("src.api.main.get_rag_engine", lambda: FakeRagEngine())
    client = TestClient(app)

    response = client.get("/api/v1/reconcile")

    assert response.status_code == 200
    assert response.json()["is_consistent"] is True
