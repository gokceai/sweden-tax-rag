import chromadb
from chromadb.utils import embedding_functions
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VectorDBManager:
    def __init__(self):
        # 1.We are connecting to ChromaDB in Docker using HttpClient (we issued an 8001 in docker-compose).
        self.client = chromadb.HttpClient(host='localhost', port=8001)
        
        # 2. Our Embedding Model (Local, fast and closed to the outside)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        self.collection_name = "swedish_tax_vectors"
        self.collection = self._init_collection()

    def _init_collection(self):
        """It creates the collection or links to it if it already exists."""
        try:
            # hnsw:space -> cosine similarity (The heart of semantic searching)
            collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_fn,
                metadata={"hnsw:space": "cosine"} 
            )
            logger.info(f" ChromaDB Collection '{self.collection_name}' ready.")
            return collection
        except Exception as e:
            logger.error(f" ChromaDB Connection Error: {e}")
            raise e

    def add_vector(self, chunk_id: str, text_for_embedding: str):
        """
        We are not intentionally saving the original text ('documents')!
        We are only saving the calculated vector and its corresponding DynamoDB ID (chunk_id).
        """
        try:
            # Convert text to vector (e.g., a 384-dimensional number sequence)
            embeddings = self.embedding_fn([text_for_embedding])
            
            self.collection.add(
                ids=[chunk_id],
                embeddings=embeddings,
                metadatas=[{"status": "secured_in_dynamo"}] # Just harmless metadata
            )
            logger.info(f"Vector successfully added.: {chunk_id}")
            return True
        except Exception as e:
            logger.error(f"Vector insertion error: {e}")
            return False

    def search_similar_ids(self, query_text: str, n_results: int = 2):
        """It finds the IDs of the vectors that are closest to the user's query."""
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            # Return the list of found IDs.
            return results['ids'][0] if results['ids'] else []
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

# instance to be used throughout the project
chroma_db = VectorDBManager()