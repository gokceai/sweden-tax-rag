from src.core.config import settings
from src.db.chroma_client import VectorDBManager


class FakeCollection:
    def upsert(self, ids, embeddings, metadatas):
        return None

    def query(self, query_texts, n_results):
        return {"ids": [["chunk-1"]]}

    def delete(self, ids):
        return None

    def get(self, ids=None, include=None):
        if ids:
            return {"ids": ids}
        return {"ids": ["chunk-1", "chunk-2"]}


class FakeClient:
    def get_or_create_collection(self, name, embedding_function, metadata):
        return FakeCollection()


def test_chroma_manager_uses_settings(monkeypatch):
    captured = {}

    def fake_persistent_client(path):
        captured["persist_dir"] = path
        return FakeClient()

    class FakeEmbeddingFunction:
        def __init__(self, model_name, device="cpu"):
            captured["embedding_model"] = model_name
            captured["embedding_device"] = device

        def __call__(self, texts):
            return [[0.1, 0.2, 0.3] for _ in texts]

    monkeypatch.setattr("src.db.chroma_client.chromadb.PersistentClient", fake_persistent_client)
    monkeypatch.setattr(
        "src.db.chroma_client.embedding_functions.SentenceTransformerEmbeddingFunction",
        FakeEmbeddingFunction,
    )

    manager = VectorDBManager()

    assert manager.collection_name == settings.CHROMA_COLLECTION_NAME
    assert captured["persist_dir"] == settings.CHROMA_PERSIST_DIR
    assert captured["embedding_model"] == settings.EMBEDDING_MODEL
    assert captured["embedding_device"] in {"cpu", "cuda"}

    assert manager.search_similar_ids("vat", 1) == ["chunk-1"]
    assert manager.has_vector("chunk-1") is True
    assert manager.list_ids() == {"chunk-1", "chunk-2"}
