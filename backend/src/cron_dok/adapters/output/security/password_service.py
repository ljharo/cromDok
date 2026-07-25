"""Password hashing with Argon2id via pwdlib (spec 9.4.1).

Plaintext passwords never leave this module: ``hash`` produces the Argon2id
string stored in ``users.password_hash`` and ``verify`` compares without
reversible operations. Minimum length is 12 characters.
"""

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

MIN_PASSWORD_LENGTH = 12


class WeakPasswordError(ValueError):
    """Raised when a password does not meet the minimum length policy."""

    def __init__(self) -> None:
        super().__init__(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long")


class PasswordService:
    """Hash and verify passwords with Argon2id."""

    def __init__(self) -> None:
        self._hasher: PasswordHash = PasswordHash((Argon2Hasher(),))

    def hash(self, password: str) -> str:
        """Return the Argon2id hash of ``password``.

        Raises:
            WeakPasswordError: if ``password`` is shorter than 12 characters.
        """
        self.validate_strength(password)
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        """Return True if ``password`` matches the stored Argon2id hash."""
        return self._hasher.verify(password, password_hash)

    @staticmethod
    def validate_strength(password: str) -> None:
        """Enforce the minimum length policy.

        Raises:
            WeakPasswordError: if ``password`` is shorter than 12 characters.
        """
        if len(password) < MIN_PASSWORD_LENGTH:
            raise WeakPasswordError()
