import logging
from src.db.dynamo_client import dynamo_db
from src.core.security import encryption_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentRepository:
    def __init__(self):
        # We make sure the table is ready before we proceed with any transactions.
        self.table = dynamo_db.create_table_if_not_exists()

    def save_document_chunk(self, chunk_id: str, original_text: str, metadata: dict):
        """It writes the text, along with its encryption and metadata, to DynamoDB."""
        try:
            # 1. Encrypt Text
            encrypted_text = encryption_engine.encrypt_data(original_text)
            
            # 2. Prepare the JSON format (Item) to be sent to DynamoDB.
            item = {
                'chunk_id': chunk_id,
                'encrypted_text': encrypted_text,
                'source': metadata.get('source', 'unknown'),
                'page_number': metadata.get('page_number', 0)
            }
            
            # 3.Write to the database
            self.table.put_item(Item=item)
            logger.info(f"Chunk '{chunk_id}' It has been successfully encrypted and saved.")
            return True
        except Exception as e:
            logger.error(f"Recording error ({chunk_id}): {e}")
            return False

    def get_document_chunk(self, chunk_id: str):
        """It retrieves the encrypted data from DynamoDB and converts it into plain text usable by the LLM."""
        try:
            response = self.table.get_item(Key={'chunk_id': chunk_id})
            
            if 'Item' not in response:
                logger.warning(f"Chunk '{chunk_id}' not found.")
                return None
            
            item = response['Item']
            
            # Decrypt the code
            decrypted_text = encryption_engine.decrypt_data(item['encrypted_text'])
            
            # Add the decrypted text to the dictionary, and remove the encrypted text from memory.
            item['decrypted_text'] = decrypted_text
            del item['encrypted_text'] 
            
            return item
        except Exception as e:
            logger.error(f"Reading error({chunk_id}): {e}")
            return None

# instance to be used throughout the project
doc_repo = DocumentRepository()