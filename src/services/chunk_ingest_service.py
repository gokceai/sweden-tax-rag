from dataclasses import dataclass


@dataclass
class IngestResult:
    chunk_id: str
    document_store_written: bool
    chroma_written: bool
    updated_existing: bool = False


class ChunkIngestService:
    def __init__(self, document_repo, vector_db):
        self.document_repo = document_repo
        self.vector_db = vector_db

    def ingest_chunk(self, chunk_id: str, text: str, metadata: dict) -> IngestResult:
        exists_before = (
            self.document_repo.has_document_chunk(chunk_id)
            or self.vector_db.has_vector(chunk_id)
        )

        document_store_ok = self.document_repo.save_document_chunk(chunk_id, text, metadata)
        if not document_store_ok:
            return IngestResult(
                chunk_id=chunk_id,
                document_store_written=False,
                chroma_written=False,
                updated_existing=exists_before,
            )

        chroma_ok = self.vector_db.add_or_update_vector(chunk_id, text, metadata=metadata)
        if not chroma_ok:
            try:
                self.document_repo.delete_document_chunk(chunk_id)
            except Exception:
                pass
            return IngestResult(
                chunk_id=chunk_id,
                document_store_written=True,
                chroma_written=False,
                updated_existing=exists_before,
            )

        return IngestResult(
            chunk_id=chunk_id,
            document_store_written=True,
            chroma_written=True,
            updated_existing=exists_before,
        )