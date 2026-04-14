import logging

logger = logging.getLogger(__name__)


class RAGEngine:
    def __init__(self, vector_db, document_repo, settings):
        self.vector_db = vector_db
        self.document_repo = document_repo
        self.settings = settings

    def retrieve_context(self, query: str, top_k: int | None = None) -> list:
        top_k = top_k or self.settings.RETRIEVAL_TOP_K
        found_ids = self.vector_db.search_similar_ids(query, n_results=top_k)
        if not found_ids:
            return []

        items = self.document_repo.get_document_chunks(found_ids)
        return [
            item["decrypted_text"]
            for item in items
            if item and "decrypted_text" in item
        ]