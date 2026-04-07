import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine.llm_engine import answer_generator

def run_test():
    print("--- Llama 3.2 Generative AI Test ---")
    
    # The decrypted context that we assume our RAG engine found and retrieved.
    mock_contexts = [
        "A reduced VAT rate of 12% applies to foodstuffs, non-alcoholic beverages, hotel accommodations, and minor repair services.",
        "The standard corporate tax rate in Sweden is strictly 20.6 percent on the annual taxable profit."
    ]
    
    query = "If I stay in a hotel and eat food there, what VAT rate applies?"
    
    print(f"\n Question: '{query}'")
    print("The response is being generated (This process may take 10-30 seconds depending on the speed of your computer)...\n")
    
    # Generate the answer
    final_answer = answer_generator.generate_answer(query, mock_contexts)
    
    print("Llama 3.2 Answer:")
    print("-" * 40)
    print(final_answer)
    print("-" * 40)

if __name__ == "__main__":
    run_test()
