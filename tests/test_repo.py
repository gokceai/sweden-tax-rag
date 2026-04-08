from src.db.document_repo import DocumentRepository
from src.core.security import EncryptionManager


class FakeTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item):
        self.items[Item["chunk_id"]] = Item

    def get_item(self, Key):
        item = self.items.get(Key["chunk_id"])
        return {"Item": item} if item else {}

    def delete_item(self, Key):
        self.items.pop(Key["chunk_id"], None)


def test_document_repository_encrypts_and_decrypts():
    key = "x2FSEjvKQQNsN9adDsIc6vVXwx_W1fVrcp4pfWyU-XU="
    repo = DocumentRepository(table=FakeTable(), encryption_manager=EncryptionManager(key))

    ok = repo.save_document_chunk("chunk-1", "secret text", {"source": "doc", "chunk_index": 3})
    assert ok is True

    item = repo.get_document_chunk("chunk-1")
    assert item["decrypted_text"] == "secret text"
    assert item["chunk_index"] == 3
