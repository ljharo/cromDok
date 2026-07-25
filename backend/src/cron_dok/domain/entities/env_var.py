"""EnvVar entity: an environment variable stored encrypted at rest.

The domain never sees plaintext values; ``encrypted_value`` is produced by
the encryption adapter. Key validation (format + system blacklist) is a
domain rule (spec section 9.1).
"""

import re
from dataclasses import dataclass

_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Keys that must never be injected: they would override container/system vars.
BLACKLISTED_KEYS: frozenset[str] = frozenset({"PATH", "LD_PRELOAD", "HOME"})


class InvalidEnvVarKeyError(ValueError):
    """Raised when an env var key has an invalid format or is blacklisted."""


@dataclass(kw_only=True)
class EnvVar:
    """An env var scoped to a project, or to a single runner (runner_id set)."""

    id: int | None = None
    project_id: int
    key: str
    encrypted_value: str
    runner_id: int | None = None

    def __post_init__(self) -> None:
        if not _KEY_PATTERN.match(self.key):
            raise InvalidEnvVarKeyError(f"Invalid env var key: {self.key!r}")
        if self.key in BLACKLISTED_KEYS:
            raise InvalidEnvVarKeyError(f"Env var key {self.key!r} is blacklisted")
