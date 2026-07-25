"""End-to-end check: `alembic upgrade head` on a temp DB yields the WAL schema."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_alembic_upgrade_head_creates_wal_schema(tmp_path) -> None:
    db_path = tmp_path / "crondok.db"
    env = {
        **os.environ,
        "CRONDOK_DATABASE_URL": f"sqlite+aiosqlite:///{db_path}",
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr

    conn = sqlite3.connect(db_path)
    try:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert journal_mode == "wal"

        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {
            "projects",
            "runners",
            "executions",
            "env_vars",
            "users",
            "sessions",
            "alembic_version",
        } <= tables
    finally:
        conn.close()
