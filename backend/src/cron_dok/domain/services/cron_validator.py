"""Pure cron validation rules (no I/O).

Thin domain-level wrapper around :class:`CronExpression` so application
services can validate/normalize cron input without constructing entities.
"""

from datetime import UTC, datetime

from croniter import croniter

from cron_dok.domain.value_objects.cron_expression import (
    CronExpression,
    InvalidCronExpressionError,
)

__all__ = ["InvalidCronExpressionError", "is_valid", "next_occurrence", "validate"]


def is_valid(expression: str) -> bool:
    """Return True if ``expression`` is a syntactically valid cron expression."""
    return bool(croniter.is_valid(expression))


def validate(expression: str) -> CronExpression:
    """Validate ``expression`` and return it as a CronExpression value object.

    Raises:
        InvalidCronExpressionError: if the expression cannot be parsed.
    """
    return CronExpression(expression)


def next_occurrence(expression: str, *, from_time: datetime | None = None) -> datetime:
    """Compute the next fire time of ``expression`` after ``from_time`` (UTC now by default).

    Raises:
        InvalidCronExpressionError: if the expression cannot be parsed.
    """
    cron = validate(expression)
    base = from_time if from_time is not None else datetime.now(UTC)
    next_run: datetime = croniter(cron.value, base).get_next(datetime)
    return next_run
