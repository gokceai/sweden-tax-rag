import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine.rag_core import rag_engine

def run_test():
    print("--- RAG Engine End-to-End Test ---")
    
    # A short document describing the Swedish tax system (Two paragraphs = Two chunks)
    swedish_tax_doc = """
    The Swedish Tax Agency (Skatteverket) requires all businesses registered in Sweden to pay corporate tax. As of the current regulation, the corporate tax rate is strictly 20.6 percent on the annual taxable profit.

    Value Added Tax (VAT), known as 'Moms' in Sweden, generally has a standard rate of 25 percent. However, reduced rates of 12 percent apply to food and hotel stays, and 6 percent applies to books and passenger transport.
    """
    
    print("\n 1.The document is being uploaded to the system. (Chunking -> Vectorization -> Encryption -> DB Storage)...")
    rag_engine.ingest_document(swedish_tax_doc, source_name="skatteverket_guide_2026")
    
    print("\n 2.A question is asked and context is retrieved...")
    # We don't use specific words like 'Moms' or 12% in the question so that we can measure the system's semantic intelligence.
    query = "What is the tax rate for staying in a hotel?"
    contexts = rag_engine.retrieve_context(query, top_k=1)
    
    if contexts:
        print("SUCCESS! Context found to send to LLM.:")
        print(f"   -> {contexts[0]}")
    else:
        print("ERROR: Context could not be retrieved..")

if __name__ == "__main__":
    run_test()