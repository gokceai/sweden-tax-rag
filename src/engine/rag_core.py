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

    def ingest_document(self, document_text: str, source_name: str):
        """Split, embed, encrypt, and persist document chunks."""
        logger.info("Ingest started for source '%s'", source_name)
        chunks = self.text_splitter.split_text(document_text)
        if not chunks:
            return 0

        success_count = 0
        for i, chunk_text in enumerate(chunks):
            chunk_id = self._build_chunk_id(source_name, i, chunk_text)

            vector_success = self.vector_db.add_or_update_vector(chunk_id, chunk_text)
            metadata = {"source": source_name, "chunk_index": i}
            db_success = self.document_repo.save_document_chunk(chunk_id, chunk_text, metadata)

            if vector_success and db_success:
                success_count += 1
                continue

            self._rollback_chunk(chunk_id, vector_success=vector_success, db_success=db_success)
            raise DataIntegrityError(
                f"Ingest failed for chunk '{chunk_id}'. Rolled back partial writes."
            )

        logger.info("Ingest completed for '%s': %s/%s chunks", source_name, success_count, len(chunks))
        return success_count

    def reconcile_indexes(self) -> dict:
        """Find cross-store inconsistencies between Chroma and SQLite."""
        chroma_ids = self.vector_db.list_ids()
        document_store_ids = self.document_repo.list_chunk_ids()
        only_in_chroma = sorted(chroma_ids - document_store_ids)
        only_in_document_store = sorted(document_store_ids - chroma_ids)
        return {
            "total_chroma_ids": len(chroma_ids),
            "total_document_store_ids": len(document_store_ids),
            "only_in_chroma": only_in_chroma,
            "only_in_document_store": only_in_document_store,
            "is_consistent": not only_in_chroma and not only_in_document_store,
        }

    def repair_indexes(
        self,
        *,
        only_in_chroma_action: str = "mark_for_review",
        only_in_document_store_action: str = "mark_for_review",
    ) -> dict:
        """Optionally repair inconsistencies after a reconciliation pass."""
        pre_report = self.reconcile_indexes()
        repair_result = {
            "pre_reconcile": pre_report,
            "actions": {
                "only_in_chroma_action": only_in_chroma_action,
                "only_in_document_store_action": only_in_document_store_action,
            },
            "repaired": {
                "only_in_chroma": [],
                "only_in_document_store": [],
            },
            "marked_for_review": {
                "only_in_chroma": [],
                "only_in_document_store": [],
            },
            "failed": {
                "only_in_chroma": [],
                "only_in_document_store": [],
            },
        }

        for chunk_id in pre_report["only_in_chroma"]:
            if only_in_chroma_action == "delete":
                try:
                    self.vector_db.delete_vector(chunk_id)
                    repair_result["repaired"]["only_in_chroma"].append(chunk_id)
                except InfrastructureError:
                    repair_result["failed"]["only_in_chroma"].append(chunk_id)
            else:
                repair_result["marked_for_review"]["only_in_chroma"].append(chunk_id)

        for chunk_id in pre_report["only_in_document_store"]:
            if only_in_document_store_action == "delete":
                try:
                    self.document_repo.delete_document_chunk(chunk_id)
                    repair_result["repaired"]["only_in_document_store"].append(chunk_id)
                except InfrastructureError:
                    repair_result["failed"]["only_in_document_store"].append(chunk_id)
            elif only_in_document_store_action == "rehydrate":
                chunk = self.document_repo.get_document_chunk(chunk_id)
                chunk_text = chunk.get("decrypted_text") if chunk else None
                if not chunk_text:
                    repair_result["failed"]["only_in_document_store"].append(chunk_id)
                    continue
                upserted = self.vector_db.add_or_update_vector(chunk_id, chunk_text)
                if upserted:
                    repair_result["repaired"]["only_in_document_store"].append(chunk_id)
                else:
                    repair_result["failed"]["only_in_document_store"].append(chunk_id)
            else:
                repair_result["marked_for_review"]["only_in_document_store"].append(chunk_id)

        repair_result["post_reconcile"] = self.reconcile_indexes()
        return repair_result

    def retrieve_context(self, query: str, top_k: int = 2) -> list:
        """Retrieve top-k decrypted chunks for the query."""
        logger.info("Retrieving context for query '%s'", query)
        found_ids = self.vector_db.search_similar_ids(query, n_results=top_k)
        if not found_ids:
            logger.warning("No matching vectors found for query.")
            return []

        contexts = []
        for c_id in found_ids:
            item = self.document_repo.get_document_chunk(c_id)
            if item and "decrypted_text" in item:
                contexts.append(item["decrypted_text"])
        return contexts

    def _rollback_chunk(self, chunk_id: str, *, vector_success: bool, db_success: bool) -> None:
        """Compensate partial writes to keep Chroma and SQLite in sync."""
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
        """Generate deterministic chunk IDs for idempotent ingest."""
        digest = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:16]
        return f"{source_name}_chunk_{chunk_index}_{digest}"
