"""Unit tests for PasswordService (Argon2id via pwdlib)."""

import pytest

from cron_dok.adapters.output.security.password_service import (
    MIN_PASSWORD_LENGTH,
    PasswordService,
    WeakPasswordError,
)


@pytest.fixture(scope="module")
def passwords() -> PasswordService:
    return PasswordService()


def test_hash_verify_roundtrip(passwords: PasswordService) -> None:
    password = "correct horse battery"
    password_hash = passwords.hash(password)
    assert password_hash.startswith("$argon2id$")
    assert password not in password_hash
    assert passwords.verify(password, password_hash) is True


def test_verify_rejects_wrong_password(passwords: PasswordService) -> None:
    password_hash = passwords.hash("correct horse battery")
    assert passwords.verify("wrong password!", password_hash) is False


def test_hash_rejects_short_passwords(passwords: PasswordService) -> None:
    with pytest.raises(WeakPasswordError):
        passwords.hash("x" * (MIN_PASSWORD_LENGTH - 1))
    # Boundary: exactly the minimum length is accepted.
    assert passwords.verify("x" * MIN_PASSWORD_LENGTH, passwords.hash("x" * MIN_PASSWORD_LENGTH))
