import logging

from src.core.exceptions import InfrastructureError

logger = logging.getLogger(__name__)


class DocumentRepository:
    def __init__(self, table, encryption_manager):
        self.table = table
        self.encryption_manager = encryption_manager

    def save_document_chunk(self, chunk_id: str, original_text: str, metadata: dict):
        """Encrypt and store chunk payload in DynamoDB."""
        try:
            encrypted_text = self.encryption_manager.encrypt_data(original_text)
            item = {
                "chunk_id": chunk_id,
                "encrypted_text": encrypted_text,
                "source": metadata.get("source", "unknown"),
                "chunk_index": metadata.get("chunk_index", 0),
            }
            for key, value in metadata.items():
                if key in {"chunk_id", "encrypted_text", "decrypted_text", "text"}:
                    continue
                if key in item:
                    continue
                if value is None:
                    continue
                item[key] = value
            self.table.put_item(Item=item)
            logger.info("Chunk '%s' encrypted and saved.", chunk_id)
            return True
        except Exception as e:
            logger.error("Chunk save failed (%s): %s", chunk_id, e)
            return False

    def get_document_chunk(self, chunk_id: str):
        """Read encrypted chunk from DynamoDB and decrypt in-memory."""
        try:
            response = self.table.get_item(Key={"chunk_id": chunk_id})
            if "Item" not in response:
                logger.warning("Chunk '%s' not found.", chunk_id)
                return None

            item = response["Item"]
            decrypted_text = self.encryption_manager.decrypt_data(item["encrypted_text"])
            item["decrypted_text"] = decrypted_text
            del item["encrypted_text"]
            return item
        except Exception as e:
            logger.error("Chunk read failed (%s): %s", chunk_id, e)
            return None

    def has_document_chunk(self, chunk_id: str) -> bool:
        try:
            response = self.table.get_item(Key={"chunk_id": chunk_id}, ProjectionExpression="chunk_id")
            return "Item" in response
        except Exception as e:
            logger.error("Chunk existence check failed (%s): %s", chunk_id, e)
            return False

    def delete_document_chunk(self, chunk_id: str) -> None:
        try:
            self.table.delete_item(Key={"chunk_id": chunk_id})
        except Exception as e:
            raise InfrastructureError(f"DynamoDB delete failed for {chunk_id}: {e}") from e

    def list_chunk_ids(self) -> set[str]:
        try:
            ids: set[str] = set()
            response = self.table.scan(ProjectionExpression="chunk_id")
            for item in response.get("Items", []):
                ids.add(item["chunk_id"])
            while "LastEvaluatedKey" in response:
                response = self.table.scan(
                    ProjectionExpression="chunk_id",
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                for item in response.get("Items", []):
                    ids.add(item["chunk_id"])
            return ids
        except Exception as e:
            raise InfrastructureError(f"DynamoDB list IDs failed: {e}") from e
