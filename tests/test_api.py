import pytest
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


@pytest.fixture(autouse=True)
def reset_runtime_flags(monkeypatch):
    monkeypatch.setattr("src.core.config.settings.ENFORCE_ADMIN_AUTH", False)
    monkeypatch.setattr("src.core.config.settings.ADMIN_API_KEY", "")
    monkeypatch.setattr("src.core.config.settings.RETURN_CONTEXTS_IN_RESPONSE", False)
    monkeypatch.setattr("src.core.config.settings.CONTEXT_RESPONSE_MODE", "none")


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


def test_admin_auth_requires_key_for_ingest(monkeypatch):
    monkeypatch.setattr("src.api.main.get_rag_engine", lambda: FakeRagEngine())
    monkeypatch.setattr("src.core.config.settings.ENFORCE_ADMIN_AUTH", True)
    monkeypatch.setattr("src.core.config.settings.ADMIN_API_KEY", "secret-key")
    client = TestClient(app)

    response = client.post(
        "/api/v1/ingest",
        json={"document_text": "x" * 20, "source_name": "source.txt"},
        headers={"X-Request-ID": "rid-auth-1"},
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["error_category"] == "auth_error"
    assert detail["request_id"] == "rid-auth-1"


def test_admin_auth_accepts_valid_key_for_ingest(monkeypatch):
    monkeypatch.setattr("src.api.main.get_rag_engine", lambda: FakeRagEngine())
    monkeypatch.setattr("src.core.config.settings.ENFORCE_ADMIN_AUTH", True)
    monkeypatch.setattr("src.core.config.settings.ADMIN_API_KEY", "secret-key")
    client = TestClient(app)

    response = client.post(
        "/api/v1/ingest",
        json={"document_text": "x" * 20, "source_name": "source.txt"},
        headers={"X-Admin-Key": "secret-key"},
    )

    assert response.status_code == 200
    assert response.json()["chunks_processed"] == 2


def test_retrieve_remains_public_when_admin_auth_enabled(monkeypatch):
    monkeypatch.setattr("src.api.main.get_rag_engine", lambda: FakeRagEngine())
    monkeypatch.setattr("src.api.main.get_answer_generator", lambda: FakeAnswerGenerator())
    monkeypatch.setattr("src.core.config.settings.ENFORCE_ADMIN_AUTH", True)
    monkeypatch.setattr("src.core.config.settings.ADMIN_API_KEY", "secret-key")
    client = TestClient(app)

    response = client.post("/api/v1/retrieve", json={"query": "vat rate", "top_k": 2})

    assert response.status_code == 200
    assert response.json()["answer"] == "grounded answer"


def test_request_id_header_is_propagated():
    client = TestClient(app)

    response = client.get("/", headers={"X-Request-ID": "req-123"})

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "req-123"


def test_metrics_endpoint_available():
    client = TestClient(app)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "http_requests_total" in response.text


def test_health_live_endpoint():
    client = TestClient(app)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["mode"] == "live"


def test_health_ready_endpoint(monkeypatch):
    class FakeVector:
        collection_name = "ok"

    class FakeDocRepo:
        def ping(self):
            return True

    monkeypatch.setattr("src.api.main.get_vector_db_manager", lambda: FakeVector())
    monkeypatch.setattr("src.api.main.get_document_repository", lambda: FakeDocRepo())
    client = TestClient(app)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "document_store" in response.json()["checks"]


def test_health_deep_endpoint(monkeypatch):
    class FakeVector:
        def search_similar_ids(self, query_text, n_results=1):
            return []

    class FakeDocRepo:
        def list_chunk_ids(self):
            return set()

    monkeypatch.setattr("src.api.main.get_vector_db_manager", lambda: FakeVector())
    monkeypatch.setattr("src.api.main.get_document_repository", lambda: FakeDocRepo())
    client = TestClient(app)

    response = client.get("/health/deep")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "document_store_scan" in response.json()["checks"]


def test_retrieve_unexpected_error_has_structured_detail(monkeypatch):
    class BrokenRagEngine:
        def retrieve_context(self, query, top_k):
            raise RuntimeError("boom")

    monkeypatch.setattr("src.api.main.get_rag_engine", lambda: BrokenRagEngine())
    monkeypatch.setattr("src.api.main.get_answer_generator", lambda: FakeAnswerGenerator())
    client = TestClient(app)

    response = client.post(
        "/api/v1/retrieve",
        json={"query": "vat rate", "top_k": 2},
        headers={"X-Request-ID": "rid-err-1"},
    )

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["error_code"] == "retrieve_unexpected_error"
    assert detail["error_category"] == "server_error"
    assert detail["request_id"] == "rid-err-1"


def test_retrieve_redacted_context_mode(monkeypatch):
    monkeypatch.setattr("src.api.main.get_rag_engine", lambda: FakeRagEngine())
    monkeypatch.setattr("src.api.main.get_answer_generator", lambda: FakeAnswerGenerator())
    monkeypatch.setattr("src.core.config.settings.RETURN_CONTEXTS_IN_RESPONSE", True)
    monkeypatch.setattr("src.core.config.settings.CONTEXT_RESPONSE_MODE", "redacted")
    client = TestClient(app)

    response = client.post("/api/v1/retrieve", json={"query": "vat rate", "top_k": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["contexts"] == [{"index": 1, "char_count": 9}, {"index": 2, "char_count": 9}]


def test_retrieve_full_context_requires_admin_key_when_enforced(monkeypatch):
    monkeypatch.setattr("src.api.main.get_rag_engine", lambda: FakeRagEngine())
    monkeypatch.setattr("src.api.main.get_answer_generator", lambda: FakeAnswerGenerator())
    monkeypatch.setattr("src.core.config.settings.RETURN_CONTEXTS_IN_RESPONSE", True)
    monkeypatch.setattr("src.core.config.settings.CONTEXT_RESPONSE_MODE", "full")
    monkeypatch.setattr("src.core.config.settings.ENFORCE_ADMIN_AUTH", True)
    monkeypatch.setattr("src.core.config.settings.ADMIN_API_KEY", "secret-key")
    client = TestClient(app)

    unauthorized = client.post("/api/v1/retrieve", json={"query": "vat rate", "top_k": 2})
    authorized = client.post(
        "/api/v1/retrieve",
        json={"query": "vat rate", "top_k": 2},
        headers={"X-Admin-Key": "secret-key"},
    )

    assert unauthorized.status_code == 200
    assert unauthorized.json()["contexts"] is None
    assert authorized.status_code == 200
    assert authorized.json()["contexts"] == ["context a", "context b"]


def test_context_none_mode_always_null(monkeypatch):
    monkeypatch.setattr("src.api.main.get_rag_engine", lambda: FakeRagEngine())
    monkeypatch.setattr("src.api.main.get_answer_generator", lambda: FakeAnswerGenerator())
    monkeypatch.setattr("src.core.config.settings.RETURN_CONTEXTS_IN_RESPONSE", True)
    monkeypatch.setattr("src.core.config.settings.CONTEXT_RESPONSE_MODE", "none")
    monkeypatch.setattr("src.core.config.settings.ENFORCE_ADMIN_AUTH", False)
    client = TestClient(app)

    response = client.post("/api/v1/retrieve", json={"query": "vat rate", "top_k": 2})

    assert response.status_code == 200
    assert response.json()["contexts"] is None


def test_context_full_no_auth_enforcement(monkeypatch):
    monkeypatch.setattr("src.api.main.get_rag_engine", lambda: FakeRagEngine())
    monkeypatch.setattr("src.api.main.get_answer_generator", lambda: FakeAnswerGenerator())
    monkeypatch.setattr("src.core.config.settings.RETURN_CONTEXTS_IN_RESPONSE", True)
    monkeypatch.setattr("src.core.config.settings.CONTEXT_RESPONSE_MODE", "full")
    monkeypatch.setattr("src.core.config.settings.ENFORCE_ADMIN_AUTH", False)
    client = TestClient(app)

    response = client.post("/api/v1/retrieve", json={"query": "vat rate", "top_k": 2})

    assert response.status_code == 200
    assert response.json()["contexts"] == ["context a", "context b"]


def test_context_full_wrong_key_returns_null(monkeypatch):
    monkeypatch.setattr("src.api.main.get_rag_engine", lambda: FakeRagEngine())
    monkeypatch.setattr("src.api.main.get_answer_generator", lambda: FakeAnswerGenerator())
    monkeypatch.setattr("src.core.config.settings.RETURN_CONTEXTS_IN_RESPONSE", True)
    monkeypatch.setattr("src.core.config.settings.CONTEXT_RESPONSE_MODE", "full")
    monkeypatch.setattr("src.core.config.settings.ENFORCE_ADMIN_AUTH", True)
    monkeypatch.setattr("src.core.config.settings.ADMIN_API_KEY", "secret-key")
    client = TestClient(app)

    response = client.post(
        "/api/v1/retrieve",
        json={"query": "vat rate", "top_k": 2},
        headers={"X-Admin-Key": "wrong-key"},
    )

    assert response.status_code == 200
    assert response.json()["contexts"] is None


def test_context_redacted_with_auth_enforced_non_admin(monkeypatch):
    monkeypatch.setattr("src.api.main.get_rag_engine", lambda: FakeRagEngine())
    monkeypatch.setattr("src.api.main.get_answer_generator", lambda: FakeAnswerGenerator())
    monkeypatch.setattr("src.core.config.settings.RETURN_CONTEXTS_IN_RESPONSE", True)
    monkeypatch.setattr("src.core.config.settings.CONTEXT_RESPONSE_MODE", "redacted")
    monkeypatch.setattr("src.core.config.settings.ENFORCE_ADMIN_AUTH", True)
    monkeypatch.setattr("src.core.config.settings.ADMIN_API_KEY", "secret-key")
    client = TestClient(app)

    response = client.post("/api/v1/retrieve", json={"query": "vat rate", "top_k": 2})

    assert response.status_code == 200
    assert response.json()["contexts"] == [{"index": 1, "char_count": 9}, {"index": 2, "char_count": 9}]


def test_context_disabled_returns_null_regardless_of_mode(monkeypatch):
    monkeypatch.setattr("src.api.main.get_rag_engine", lambda: FakeRagEngine())
    monkeypatch.setattr("src.api.main.get_answer_generator", lambda: FakeAnswerGenerator())
    monkeypatch.setattr("src.core.config.settings.RETURN_CONTEXTS_IN_RESPONSE", False)
    monkeypatch.setattr("src.core.config.settings.CONTEXT_RESPONSE_MODE", "full")
    monkeypatch.setattr("src.core.config.settings.ENFORCE_ADMIN_AUTH", False)
    client = TestClient(app)

    response = client.post("/api/v1/retrieve", json={"query": "vat rate", "top_k": 2})

    assert response.status_code == 200
    assert response.json()["contexts"] is None
