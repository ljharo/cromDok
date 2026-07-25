"""Integration tests for the master key bootstrap (real filesystem, tmp_path)."""

import logging
import stat
from pathlib import Path

from cryptography.fernet import Fernet

from cron_dok.adapters.output.security.encryption_service import (
    MASTER_KEY_FILENAME,
    create_encryption_service,
)
from cron_dok.config import Settings


def _settings(data_dir: Path, master_key: str | None = None) -> Settings:
    return Settings(data_dir=str(data_dir), master_key=master_key)


def test_bootstrap_generates_key_file_with_600_permissions(tmp_path) -> None:
    service = create_encryption_service(_settings(tmp_path))

    key_path = tmp_path / MASTER_KEY_FILENAME
    assert key_path.exists()
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
    # The persisted key is a valid Fernet key and the service works.
    assert Fernet(key_path.read_bytes().strip())
    assert service.decrypt(service.encrypt("secret")) == "secret"


def test_bootstrap_logs_a_warning_when_generating(tmp_path, caplog) -> None:
    with caplog.at_level(logging.WARNING):
        create_encryption_service(_settings(tmp_path))

    assert any("CRONDOK_MASTER_KEY" in record.message for record in caplog.records)


def test_second_instance_reuses_the_persisted_key(tmp_path) -> None:
    first = create_encryption_service(_settings(tmp_path))
    token = first.encrypt("secret")
    key_before = (tmp_path / MASTER_KEY_FILENAME).read_bytes()

    second = create_encryption_service(_settings(tmp_path))

    assert second.decrypt(token) == "secret"
    assert (tmp_path / MASTER_KEY_FILENAME).read_bytes() == key_before


def test_master_key_setting_takes_precedence_and_writes_no_file(tmp_path) -> None:
    key = Fernet.generate_key().decode("ascii")

    service = create_encryption_service(_settings(tmp_path, master_key=key))

    assert service.decrypt(service.encrypt("secret")) == "secret"
    assert not (tmp_path / MASTER_KEY_FILENAME).exists()
