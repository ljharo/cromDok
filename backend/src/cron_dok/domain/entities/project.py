"""Project entity: logical container of runners and environment variables."""

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(kw_only=True)
class Project:
    """A project groups runners, env vars and permissions."""

    id: int | None = None
    name: str
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Project name must not be empty")
