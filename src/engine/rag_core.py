import uuid
import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.db.document_repo import doc_repo
from src.db.chroma_client import chroma_db
from src.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RAGEngine:
    def __init__(self):
        # Production-Grade Text Splitter
        # chunk_size: The maximum number of characters a vector can represent. 
        # chunk_overlap: The number of characters left common to maintain connection between chunks.
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
            is_separator_regex=False,
        )

    def ingest_document(self, document_text: str, source_name: str):
        """
        The document is split using an advanced LangChain Text Splitter. 
        It is transferred to a vector database without context loss and then 
        encrypted and transferred to DynamoDB.
        """
        logger.info(f"'{source_name}' The document is being shredded using LangChain...")
        
        # Smart splitting.
        chunks = self.text_splitter.split_text(document_text)
        
        success_count = 0
        for i, chunk_text in enumerate(chunks):
            # Create a unique and traceable ID
            chunk_id = f"{source_name}_chunk_{i}_{uuid.uuid4().hex[:6]}"
            
            # 1. Add the vector to ChromaDB (without text)
            vector_success = chroma_db.add_vector(chunk_id, chunk_text)
            
            # 2. Add the Encrypted Text to DynamoDB
            metadata = {"source": source_name, "chunk_index": i}
            db_success = doc_repo.save_document_chunk(chunk_id, chunk_text, metadata)
            
            if vector_success and db_success:
                success_count += 1
                
        logger.info(f"Document processed: {success_count}/{len(chunks)} Smart part (chunk) successfully registered..")
        return success_count

    def retrieve_context(self, query: str, top_k: int = 2) -> list:
        """
        It retrieves the most suitable decrypted text (context) for the question.
        """
        logger.info(f" Looking for context for the question: '{query}'")
        
        # 1. Find similar IDs from ChromaDB
        found_ids = chroma_db.search_similar_ids(query, n_results=top_k)
        
        if not found_ids:
            logger.warning("ChromaDB found no matching vectors..")
            return []
            
        logger.info(f"IDs found: {found_ids}")
        
        # 2. Retrieve the found IDs from DynamoDB and decrypt them.
        contexts = []
        for c_id in found_ids:
            item = doc_repo.get_document_chunk(c_id)
            if item and 'decrypted_text' in item:
                contexts.append(item['decrypted_text'])
                
        return contexts

# Engine to be used throughout the project
rag_engine = RAGEngine()