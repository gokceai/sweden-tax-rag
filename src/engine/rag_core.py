import logging

logger = logging.getLogger(__name__)


class RAGEngine:
    def __init__(self, vector_db, document_repo, settings):
        self.vector_db = vector_db
        self.document_repo = document_repo
        self.settings = settings

    def retrieve_context(self, query: str, top_k: int | None = None) -> list[str]:
        top_k = top_k or self.settings.RETRIEVAL_TOP_K

        candidates = self.vector_db.search_similar(
            query,
            n_results=self.settings.RETRIEVAL_FETCH_K,
        )
        if not candidates:
            return []

        filtered = [
            item
            for item in candidates
            if item["distance"] is not None
            and item["distance"] <= self.settings.RETRIEVAL_MAX_DISTANCE
        ]
        if not filtered:
            return []

        selected = filtered[:top_k]
        chunk_ids = [item["chunk_id"] for item in selected]
        items = self.document_repo.get_document_chunks(chunk_ids)

        contexts: list[str] = []
        total_chars = 0
        for item in items:
            text = item.get("decrypted_text", "").strip()
            if not text:
                continue
            if len(contexts) >= self.settings.MAX_CONTEXT_CHUNKS:
                break
            if total_chars + len(text) > self.settings.MAX_CONTEXT_CHARS:
                break
            contexts.append(text)
            total_chars += len(text)

        return contexts