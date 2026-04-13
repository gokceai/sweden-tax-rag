from functools import lru_cache

from src.core.config import settings
from src.core.exceptions import ConfigurationError, InfrastructureError
from src.core.security import EncryptionManager
from src.db.chroma_client import VectorDBManager
from src.db.sqlite_document_repo import SQLiteDocumentRepository
from src.engine.llm_engine import AnswerGenerator
from src.engine.rag_core import RAGEngine


@lru_cache
def get_encryption_manager() -> EncryptionManager:
    if not settings.MASTER_ENCRYPTION_KEY:
        raise ConfigurationError("MASTER_ENCRYPTION_KEY is not configured.")
    return EncryptionManager(settings.MASTER_ENCRYPTION_KEY)


@lru_cache
def get_vector_db_manager() -> VectorDBManager:
    try:
        return VectorDBManager()
    except Exception as e:
        raise InfrastructureError(f"Vector DB init failed: {e}") from e


@lru_cache
def get_document_repository() -> SQLiteDocumentRepository:
    try:
        return SQLiteDocumentRepository(
            db_path=settings.SQLITE_DB_PATH,
            encryption_manager=get_encryption_manager(),
        )
    except Exception as e:
        raise InfrastructureError(f"Document repository init failed: {e}") from e


@lru_cache
def get_rag_engine() -> RAGEngine:
    return RAGEngine(
        vector_db=get_vector_db_manager(),
        document_repo=get_document_repository(),
        settings=settings,
    )


@lru_cache
def get_answer_generator() -> AnswerGenerator:
    return AnswerGenerator(settings=settings)
