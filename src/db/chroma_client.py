import logging

import chromadb
from chromadb.utils import embedding_functions

from src.core.config import settings
from src.core.exceptions import InfrastructureError

logger = logging.getLogger(__name__)


class VectorDBManager:
    def __init__(self):
        try:
            self.client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        except Exception as e:
            raise InfrastructureError(f"ChromaDB initialization failed: {e}") from e

        embedding_device = settings.resolve_device(settings.EMBEDDING_DEVICE)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.EMBEDDING_MODEL,
            device=embedding_device,
        )
        logger.info(
            "Embedding model '%s' initialized on device=%s",
            settings.EMBEDDING_MODEL,
            embedding_device,
        )

        self.collection_name = settings.CHROMA_COLLECTION_NAME
        self.collection = self._init_collection()

    def _init_collection(self):
        """Create or load the target collection."""
        try:
            collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_fn,
                metadata={"hnsw:space": settings.CHROMA_DISTANCE},
            )
            logger.info("ChromaDB collection '%s' ready.", self.collection_name)
            return collection
        except Exception as e:
            raise InfrastructureError(f"ChromaDB initialization failed: {e}") from e

    def add_or_update_vector(
        self,
        chunk_id: str,
        text_for_embedding: str,
        metadata: dict | None = None,
    ) -> bool:
        """Idempotent write: upsert embedding and metadata without raw text."""
        try:
            embeddings = self.embedding_fn([text_for_embedding])
            vector_metadata = {"status": "secured_in_sqlite"}

            if metadata:
                for key, value in metadata.items():
                    if key in {"text", "encrypted_text", "decrypted_text"}:
                        continue
                    if value is None:
                        continue
                    if isinstance(value, (str, int, float, bool)):
                        vector_metadata[key] = value

            self.collection.upsert(
                ids=[chunk_id],
                embeddings=embeddings,
                metadatas=[vector_metadata],
            )
            logger.info("Vector upserted: %s", chunk_id)
            return True
        except Exception as e:
            logger.error("Vector insertion error for %s: %s", chunk_id, e)
            return False

    def has_vector(self, chunk_id: str) -> bool:
        try:
            result = self.collection.get(ids=[chunk_id], include=[])
            return bool(result.get("ids"))
        except Exception as e:
            logger.error("Vector existence check failed for %s: %s", chunk_id, e)
            return False

    def search_similar(self, query_text: str, n_results: int = 3) -> list[dict]:
        """
        Return retrieval candidates with distances and metadatas.

        Output shape:
        [
            {
                "chunk_id": "...",
                "distance": 0.42,
                "metadata": {...},
            },
            ...
        ]
        """
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                include=["distances", "metadatas"],
            )

            ids = results.get("ids", [[]])[0]
            distances = results.get("distances", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            items: list[dict] = []
            for idx, chunk_id in enumerate(ids):
                items.append(
                    {
                        "chunk_id": chunk_id,
                        "distance": distances[idx] if idx < len(distances) else None,
                        "metadata": metadatas[idx] if idx < len(metadatas) else {},
                    }
                )

            logger.info(
                "Vector search returned %s candidates for query=%r",
                len(items),
                query_text[:120],
            )
            return items
        except Exception as e:
            logger.error("Vector search error: %s", e)
            return []

    def search_similar_ids(self, query_text: str, n_results: int = 2) -> list[str]:
        """
        Compatibility wrapper returning only chunk IDs.
        Keep this so existing callers do not break.
        """
        results = self.search_similar(query_text, n_results=n_results)
        return [item["chunk_id"] for item in results]

    def delete_vector(self, chunk_id: str) -> None:
        try:
            self.collection.delete(ids=[chunk_id])
        except Exception as e:
            raise InfrastructureError(f"Chroma delete failed for {chunk_id}: {e}") from e

    def delete_vectors(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        try:
            self.collection.delete(ids=chunk_ids)
        except Exception as e:
            raise InfrastructureError(f"Chroma bulk delete failed: {e}") from e

    def list_ids(self) -> set[str]:
        try:
            result = self.collection.get(include=[])
            return set(result.get("ids", []))
        except Exception as e:
            raise InfrastructureError(f"Chroma list IDs failed: {e}") from e