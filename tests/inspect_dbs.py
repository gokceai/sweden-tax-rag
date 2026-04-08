from src.core.dependencies import get_document_repository, get_dynamo_manager, get_vector_db_manager


def inspect_dynamodb():
    print("\n" + "=" * 60)
    print("DYNAMODB Content")
    print("=" * 60)
    try:
        table = get_dynamo_manager().create_table_if_not_exists()
        response = table.scan()
        items = response.get("Items", [])

        if not items:
            print("DynamoDB table is empty.")
            return

        repo = get_document_repository()
        print(f"Total {len(items)} records found:\n")
        for idx, item in enumerate(items, start=1):
            print(f"--- Record {idx} ---")
            print(f"Chunk ID: {item.get('chunk_id')}")
            decrypted = repo.get_document_chunk(item.get("chunk_id"))
            if decrypted:
                text = decrypted.get("decrypted_text", "")
                print(f"Decrypted text: {text[:80]}...")
            print("-" * 40)
    except Exception as e:
        print(f"DynamoDB read error: {e}")


def inspect_chromadb():
    print("\n" + "=" * 60)
    print("CHROMADB CONTENT")
    print("=" * 60)
    try:
        chroma_db = get_vector_db_manager()
        results = chroma_db.collection.get(include=["embeddings", "metadatas", "documents"])

        ids = results.get("ids", [])
        embeddings = results.get("embeddings")
        metadatas = results.get("metadatas", [])

        if not ids:
            print("ChromaDB collection is empty.")
            return

        print(f"Total {len(ids)} vectors found:\n")
        for i in range(len(ids)):
            print(f"--- Vector {i + 1} ---")
            print(f"Chunk ID: {ids[i]}")
            print(f"Metadata: {metadatas[i]}")
            if embeddings is not None and len(embeddings) > i:
                vec = embeddings[i]
                print(f"Vector size: {len(vec)}")
            print("-" * 40)
    except Exception as e:
        print(f"ChromaDB read error: {e}")


if __name__ == "__main__":
    inspect_dynamodb()
    inspect_chromadb()
