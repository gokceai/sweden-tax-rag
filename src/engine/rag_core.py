import logging
import hashlib
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.core.exceptions import DataIntegrityError, InfrastructureError

logger = logging.getLogger(__name__)


class RAGEngine:
    def __init__(self, vector_db, document_repo, settings):
        self.vector_db = vector_db
        self.document_repo = document_repo
        self.settings = settings
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
            is_separator_regex=False,
        )

    def ingest_document(self, document_text: str, source_name: str) -> int:
        """Split, embed, encrypt, and persist document chunks."""
        chunks = self.text_splitter.split_text(document_text)
        if not chunks:
            return 0

        success_count = 0
        for i, chunk_text in enumerate(chunks):
            chunk_id = self._build_chunk_id(source_name, i, chunk_text)
            vector_ok = self.vector_db.add_or_update_vector(chunk_id, chunk_text)
            db_ok = self.document_repo.save_document_chunk(chunk_id, chunk_text, {"source": source_name, "chunk_index": i})

            if vector_ok and db_ok:
                success_count += 1
                continue

            self._rollback_chunk(chunk_id, vector_success=vector_ok, db_success=db_ok)
            raise DataIntegrityError(f"Ingest failed for chunk '{chunk_id}'. Rolled back partial writes.")

        logger.info("Ingest completed for '%s': %s/%s chunks", source_name, success_count, len(chunks))
        return success_count

    def retrieve_context(self, query: str, top_k: int = 2) -> list:
        """Retrieve top-k decrypted chunks for the query."""
        found_ids = self.vector_db.search_similar_ids(query, n_results=top_k)
        if not found_ids:
            return []
        contexts = []
        for c_id in found_ids:
            item = self.document_repo.get_document_chunk(c_id)
            if item and "decrypted_text" in item:
                contexts.append(item["decrypted_text"])
        return contexts

    def _rollback_chunk(self, chunk_id: str, *, vector_success: bool, db_success: bool) -> None:
        if vector_success and not db_success:
            try:
                self.vector_db.delete_vector(chunk_id)
            except InfrastructureError as e:
                logger.error("Rollback failed for vector %s: %s", chunk_id, e)
        if db_success and not vector_success:
            try:
                self.document_repo.delete_document_chunk(chunk_id)
            except InfrastructureError as e:
                logger.error("Rollback failed for document %s: %s", chunk_id, e)

    def _build_chunk_id(self, source_name: str, chunk_index: int, chunk_text: str) -> str:
        digest = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:16]
        return f"{source_name}_chunk_{chunk_index}_{digest}"
