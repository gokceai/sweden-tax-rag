import pytest

from src.core.security import EncryptionManager


def test_encrypt_decrypt_roundtrip():
    key = "x2FSEjvKQQNsN9adDsIc6vVXwx_W1fVrcp4pfWyU-XU="
    manager = EncryptionManager(key)

    plain = "Swedish corporate tax rate is 20.6 percent."
    encrypted = manager.encrypt_data(plain)

    assert encrypted != plain
    assert manager.decrypt_data(encrypted) == plain


def test_missing_key_raises_value_error(monkeypatch):
    monkeypatch.delenv("MASTER_ENCRYPTION_KEY", raising=False)
    with pytest.raises(ValueError):
        EncryptionManager(None)
