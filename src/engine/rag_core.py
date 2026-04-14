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

        logger.info(
            "retrieval.start query=%r fetch_k=%s top_k=%s threshold=%s candidates=%s",
            query[:200],
            self.settings.RETRIEVAL_FETCH_K,
            top_k,
            self.settings.RETRIEVAL_MAX_DISTANCE,
            len(candidates),
        )

        if candidates:
            logger.info(
                "retrieval.candidates %s",
                [
                    {
                        "chunk_id": item.get("chunk_id"),
                        "distance": item.get("distance"),
                        "section_heading": (item.get("metadata") or {}).get("section_heading"),
                        "topic": (item.get("metadata") or {}).get("topic"),
                    }
                    for item in candidates
                ],
            )

        if not candidates:
            logger.info("retrieval.empty query=%r", query[:200])
            return []

        filtered = [
            item
            for item in candidates
            if item["distance"] is not None
            and item["distance"] <= self.settings.RETRIEVAL_MAX_DISTANCE
        ]

        logger.info(
            "retrieval.filtered kept=%s dropped=%s kept_ids=%s",
            len(filtered),
            len(candidates) - len(filtered),
            [
                {
                    "chunk_id": item.get("chunk_id"),
                    "distance": item.get("distance"),
                }
                for item in filtered
            ],
        )

        if not filtered:
            logger.info(
                "retrieval.none_passed_threshold query=%r threshold=%s",
                query[:200],
                self.settings.RETRIEVAL_MAX_DISTANCE,
            )
            return []

        selected = filtered[:top_k]
        chunk_ids = [item["chunk_id"] for item in selected]

        logger.info("retrieval.selected chunk_ids=%s", chunk_ids)

        items = self.document_repo.get_document_chunks(chunk_ids)
        if not items:
            logger.info("retrieval.sqlite_empty chunk_ids=%s query=%r", chunk_ids, query[:200])
            return []

        contexts: list[str] = []
        total_chars = 0

        for item in items:
            text = item.get("decrypted_text", "").strip()
            if not text:
                continue

            if len(contexts) >= self.settings.MAX_CONTEXT_CHUNKS:
                logger.info(
                    "retrieval.context_limit_reached max_chunks=%s",
                    self.settings.MAX_CONTEXT_CHUNKS,
                )
                break

            if total_chars + len(text) > self.settings.MAX_CONTEXT_CHARS:
                logger.info(
                    "retrieval.char_budget_reached total_chars=%s next_chunk_chars=%s max_chars=%s",
                    total_chars,
                    len(text),
                    self.settings.MAX_CONTEXT_CHARS,
                )
                break

            contexts.append(text)
            total_chars += len(text)

        logger.info(
            "retrieval.final contexts=%s total_chars=%s query=%r",
            len(contexts),
            total_chars,
            query[:200],
        )

        return contexts