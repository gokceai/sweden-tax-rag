import logging

logger = logging.getLogger(__name__)


class RAGEngine:
    def __init__(self, vector_db, document_repo, settings):
        self.vector_db = vector_db
        self.document_repo = document_repo
        self.settings = settings

    def retrieve_context(self, query: str, top_k: int | None = None) -> list[str]:
        """
        Retrieval flow:
        1. Fetch more candidates than final top_k
        2. Filter by distance threshold
        3. Read only surviving chunk IDs from SQLite
        4. Apply context-count and context-size budget
        """
        top_k = top_k or self.settings.RETRIEVAL_TOP_K

        candidates = self.vector_db.search_similar(
            query,
            n_results=self.settings.RETRIEVAL_FETCH_K,
        )
        if not candidates:
            logger.info("No retrieval candidates for query=%r", query)
            return []

        filtered = [
            item
            for item in candidates
            if item["distance"] is not None
            and item["distance"] <= self.settings.RETRIEVAL_MAX_DISTANCE
        ]

        if not filtered:
            logger.info(
                "All retrieval candidates were filtered out by distance threshold. "
                "query=%r threshold=%s",
                query,
                self.settings.RETRIEVAL_MAX_DISTANCE,
            )
            return []

        selected = filtered[:top_k]
        chunk_ids = [item["chunk_id"] for item in selected]

        items = self.document_repo.get_document_chunks(chunk_ids)
        if not items:
            logger.info("No SQLite rows found for selected chunk IDs. query=%r", query)
            return []

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

        logger.info(
            "Retrieval final context count=%s total_chars=%s query=%r",
            len(contexts),
            total_chars,
            query[:120],
        )
        return contexts