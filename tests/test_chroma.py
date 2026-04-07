import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db.chroma_client import chroma_db

def run_test():
    print("--- ChromaDB Vektör & Semantik Arama Testi ---")
    
    chunk_id = "tax_doc_001_chunk_1"
    # Our document contains Swedish/English terms.
    secret_text = "Skatteverket (Swedish Tax Agency) defines the corporate tax rate for companies at 20.6% for the year 2026."
    
    print("\n1. The text is converted into a mathematical vector and saved (without text) to ChromaDB..")
    chroma_db.add_vector(chunk_id, secret_text)
    
    print("\n2. A Semantic Search Test is being conducted....")
    # Our question doesn't contain "Skatteverket" or "%20.6". The system needs to figure out the meaning.
    query = "How much tax do businesses pay in Sweden?"
    print(f"Soru: '{query}'")
    
    found_ids = chroma_db.search_similar_ids(query, n_results=1)
    
    if found_ids and chunk_id in found_ids:
        print(f"\nSUCCESSFUL: Semantic search is working! An ID matching the question was found.: {found_ids[0]}")
    else:
        print("\nERROR: Expected ID not found.")

if __name__ == "__main__":
    run_test()