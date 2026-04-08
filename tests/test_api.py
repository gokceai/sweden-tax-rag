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

    def repair_indexes(self, only_in_chroma_action, only_in_dynamo_action):
        return {
            "pre_reconcile": {
                "total_chroma_ids": 2,
                "total_dynamo_ids": 2,
                "only_in_chroma": ["c1"],
                "only_in_dynamo": ["d1"],
                "is_consistent": False,
            },
            "actions": {
                "only_in_chroma_action": only_in_chroma_action,
                "only_in_dynamo_action": only_in_dynamo_action,
            },
            "repaired": {"only_in_chroma": ["c1"], "only_in_dynamo": ["d1"]},
            "marked_for_review": {"only_in_chroma": [], "only_in_dynamo": []},
            "failed": {"only_in_chroma": [], "only_in_dynamo": []},
            "post_reconcile": {
                "total_chroma_ids": 2,
                "total_dynamo_ids": 2,
                "only_in_chroma": [],
                "only_in_dynamo": [],
                "is_consistent": True,
            },
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


def test_repair_endpoint(monkeypatch):
    monkeypatch.setattr("src.api.main.get_rag_engine", lambda: FakeRagEngine())
    client = TestClient(app)

    response = client.post(
        "/api/v1/reconcile/repair",
        json={
            "only_in_chroma_action": "delete",
            "only_in_dynamo_action": "rehydrate",
        },
    )

    assert response.status_code == 200
    assert response.json()["actions"]["only_in_chroma_action"] == "delete"
    assert response.json()["post_reconcile"]["is_consistent"] is True


def test_last_reconcile_endpoint(monkeypatch):
    monkeypatch.setattr("src.api.main.get_rag_engine", lambda: FakeRagEngine())
    client = TestClient(app)

    client.get("/api/v1/reconcile")
    response = client.get("/api/v1/reconcile/last")

    assert response.status_code == 200
    assert response.json()["report"]["is_consistent"] is True
