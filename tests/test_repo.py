import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db.document_repo import doc_repo

def run_test():
    print("--- DynamoDB CRUD & Encryption Integration Testing ---")
    
    # Our Test Data
    chunk_id = "tax_doc_001_chunk_1"
    secret_text = "Article 42 of the Skatteverket Law: Corporate tax is set at 20.6%."
    metadata = {"source": "skatteverket_2026.pdf", "page_number": 12}
    
    # 1. The Writing Process
    print("\n1. The data is encrypted and written to DynamoDB....")
    doc_repo.save_document_chunk(chunk_id, secret_text, metadata)
    
    # 2. Reading Process
    print("\n2. It is being read from the database and decrypted....")
    retrieved_item = doc_repo.get_document_chunk(chunk_id)
    
    if retrieved_item:
        print(f"\nThe record found: {retrieved_item}")
        # Verification Check
        if retrieved_item['decrypted_text'] == secret_text:
            print("\n SUCCESSFUL: The end-to-end writing, reading, and decryption chain works flawlessly.!")
        else:
            print("\n ERROR: The decoded text does not match the original..")
    else:
        print("\n ERROR: No record found.")

if __name__ == "__main__":
    run_test()