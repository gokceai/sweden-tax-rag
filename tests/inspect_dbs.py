import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db.dynamo_client import dynamo_db
from src.db.chroma_client import chroma_db
from src.core.security import encryption_engine

def inspect_dynamodb():
    print("\n" + "="*60)
    print("DYNAMODB Content (NoSQL & Encrypted data)")
    print("="*60)
    try:
        table = dynamo_db.create_table_if_not_exists()
        response = table.scan()
        items = response.get('Items', [])
        
        if not items:
            print("DynamoDB table is empty.")
            return

        print(f"Total {len(items)} record found:\n")
        for idx, item in enumerate(items):
            print(f"--- Record {idx + 1} ---")
            print(f"Chunk ID: {item.get('chunk_id')}")
            print(f"Resource: {item.get('source')}")
            
            encrypted_text = item.get('encrypted_text', '')
            print(f"Encrypted text: {encrypted_text[:60]}... (shortened)")
            
            #Isolating the decryption process so that if old records are overwritten, it doesn't bring the system to a standstill.
            try:
                decrypted_text = encryption_engine.decrypt_data(encrypted_text)
                print(f"Decryted Text: {decrypted_text[:80]}... (shortened)")
            except Exception:
                print("[ERROR]: The code could not be decrypted (likely encrypted with a temporary key left over from previous tests).")
            print("-" * 40)

    except Exception as e:
        print(f"DynamoDB read error: {e}")

def inspect_chromadb():
    print("\n" + "="*60)
    print("CHROMADB CONTENT (Vector Space)")
    print("="*60)
    try:
        results = chroma_db.collection.get(include=["embeddings", "metadatas", "documents"])
        
        ids = results.get("ids", [])
        embeddings = results.get("embeddings") # NumPy array or list
        metadatas = results.get("metadatas", [])
        
        if not ids:
            print("ChromaDB collection is EMPTY.")
            return

        print(f"Total {len(ids)} vector record found:\n")
        for i in range(len(ids)):
            print(f"--- Vector {i + 1} ---")
            print(f"Matching Chunk ID: {ids[i]}")
            print(f"Metadata: {metadatas[i]}")
            
            # NumPy Ambiguity error resolve
            if embeddings is not None and len(embeddings) > i:
                vec = embeddings[i]
                print(f" Vector Size: {len(vec)} dimensional number array")
                print(f" Vector Data: [{vec[0]:.4f}, {vec[1]:.4f}, {vec[2]:.4f}, ...] (only first 3 number)")
            print("-" * 40)

    except Exception as e:
        print(f"ChromaDB reading error: {e}")

if __name__ == "__main__":
    print(" System Scanner is starting...\n")
    inspect_dynamodb()
    inspect_chromadb()