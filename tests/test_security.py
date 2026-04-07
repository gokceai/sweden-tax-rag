import sys
import os

# We add the src folder to the Python path to avoid import errors.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.security import encryption_engine

def run_test():
    print("--- Security Layer Test ---")
    
    # Real-world scenario: Swedish tax number and company information.
    secret_tax_data = "Skatteverket (Swedish Tax Agency) Document #8899: Company X has a corporate tax rate of 20.6%."
    print(f"1. Original Text:\n{secret_tax_data}\n")

    # Encryption (For the Database Version)
    encrypted_data = encryption_engine.encrypt_data(secret_tax_data)
    print(f"2. Encrypted Text (as seen by DynamoDB)):\n{encrypted_data}\n")

    # Solving (What the LLM Will See)
    decrypted_data = encryption_engine.decrypt_data(encrypted_data)
    print(f"3. Decoded Text (for LLM students to read):\n{decrypted_data}\n")

    if secret_tax_data == decrypted_data:
        print(" SUCCESSFUL: The encryption/decryption engine works flawlessly.!")
    else:
        print(" ERROR: Data integrity compromised.")

if __name__ == "__main__":
    run_test()