"""Unit tests for the Fernet EncryptionService (no filesystem, no database)."""

import pytest
from cryptography.fernet import Fernet, InvalidToken

from cron_dok.adapters.output.security.encryption_service import EncryptionService


@pytest.fixture
def service() -> EncryptionService:
    return EncryptionService(Fernet.generate_key())


def test_roundtrip_returns_plaintext(service) -> None:
    token = service.encrypt("super-secret-value")

    assert service.decrypt(token) == "super-secret-value"


def test_encrypt_produces_ciphertext_not_plaintext(service) -> None:
    token = service.encrypt("super-secret-value")

    assert token != "super-secret-value"
    assert "super-secret-value" not in token


def test_encrypt_handles_empty_and_unicode(service) -> None:
    assert service.decrypt(service.encrypt("")) == ""
    assert service.decrypt(service.encrypt("contraseña-áéí-🔑")) == "contraseña-áéí-🔑"


def test_decrypt_with_another_key_raises(service) -> None:
    other = EncryptionService(Fernet.generate_key())

    with pytest.raises(InvalidToken):
        other.decrypt(service.encrypt("secret"))


def test_decrypt_garbage_raises(service) -> None:
    with pytest.raises(InvalidToken):
        service.decrypt("not-a-fernet-token")


def test_invalid_key_raises() -> None:
    with pytest.raises(ValueError):
        EncryptionService("not-a-valid-fernet-key")
