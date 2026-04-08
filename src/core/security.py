import os
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

class EncryptionManager:
    def __init__(self, encryption_key: str | None = None):
        env_key = encryption_key or os.getenv("MASTER_ENCRYPTION_KEY")
        if not env_key:
            raise ValueError("MASTER_ENCRYPTION_KEY is required.")
        self.key = env_key.encode("utf-8")
        self.cipher_suite = Fernet(self.key)

    def encrypt_data(self, plain_text: str) -> str:
        if isinstance(plain_text, str):
            plain_text = plain_text.encode("utf-8")
        cipher_bytes = self.cipher_suite.encrypt(plain_text)
        return cipher_bytes.decode("utf-8")

    def decrypt_data(self, cipher_text: str) -> str:
        try:
            cipher_bytes = cipher_text.encode("utf-8")
            plain_bytes = self.cipher_suite.decrypt(cipher_bytes)
            return plain_bytes.decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption failed! There may be a key mismatch. Details: {e}")
            raise
