"""Cron expression value object.

Validated with ``croniter`` at construction time; invalid expressions are
rejected immediately (fail fast at the domain boundary).
"""

from dataclasses import dataclass

from croniter import croniter


class InvalidCronExpressionError(ValueError):
    """Raised when a cron expression cannot be parsed."""


@dataclass(frozen=True)
class CronExpression:
    """An immutable, validated cron expression (5 or 6 fields)."""

    value: str

    def __post_init__(self) -> None:
        if not croniter.is_valid(self.value):
            raise InvalidCronExpressionError(f"Invalid cron expression: {self.value!r}")

    def __str__(self) -> str:
        return self.value
