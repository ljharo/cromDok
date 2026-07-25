"""Fernet encryption adapter for secrets at rest (spec 9.1).

The master key comes from ``CRONDOK_MASTER_KEY``; when it is not defined,
one is generated and persisted in ``<data_dir>/.master_key`` with mode
0600 and a warning in the logs, so restarts keep decrypting the secrets
stored in the database.
"""

import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet

from cron_dok.config import Settings

logger = logging.getLogger(__name__)

MASTER_KEY_FILENAME = ".master_key"


class EncryptionService:
    """Symmetric encryption of env var values (Fernet: AES-128 CBC + HMAC)."""

    def __init__(self, key: str | bytes) -> None:
        """Initialize the service with a Fernet key.

        Args:
            key: a URL-safe base64-encoded 32-byte key, as produced by
                ``Fernet.generate_key()``.

        Raises:
            ValueError: if ``key`` is not a valid Fernet key.
        """
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt ``plaintext``; return the Fernet token as text."""
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        """Decrypt a Fernet ``token`` back to its plaintext.

        Raises:
            cryptography.fernet.InvalidToken: if ``token`` is not valid for
                this key (tampered, expired or encrypted with another key).
        """
        return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")


def create_encryption_service(settings: Settings) -> EncryptionService:
    """Build the encryption service, bootstrapping the master key if needed.

    Resolution order (spec 9.1):

    1. ``settings.master_key`` (env var ``CRONDOK_MASTER_KEY``).
    2. An existing ``<data_dir>/.master_key`` file.
    3. A freshly generated key, persisted to that file with mode 0600
       (a warning is logged, since losing the file loses every secret).

    Args:
        settings: application settings.

    Returns:
        An :class:`EncryptionService` bound to the resolved master key.
    """
    if settings.master_key:
        return EncryptionService(settings.master_key)

    key_path = Path(settings.data_dir) / MASTER_KEY_FILENAME
    if key_path.exists():
        return EncryptionService(key_path.read_text(encoding="utf-8").strip())

    key = Fernet.generate_key()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    # O_EXCL + mode 0600: the file is born with restrictive permissions,
    # never world-readable even transiently.
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(key)
    logger.warning(
        "CRONDOK_MASTER_KEY not set: generated a new master key at %s "
        "(back it up; losing it makes every stored secret unrecoverable)",
        key_path,
    )
    return EncryptionService(key)
