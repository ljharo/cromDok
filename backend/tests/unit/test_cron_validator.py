from datetime import UTC, datetime

import pytest

from cron_dok.domain.services import cron_validator
from cron_dok.domain.value_objects.cron_expression import (
    CronExpression,
    InvalidCronExpressionError,
)


def test_is_valid_true_for_valid_expression() -> None:
    assert cron_validator.is_valid("*/5 * * * *") is True


def test_is_valid_false_for_invalid_expression() -> None:
    assert cron_validator.is_valid("definitely not cron") is False


def test_validate_returns_cron_expression() -> None:
    assert cron_validator.validate("0 * * * *") == CronExpression("0 * * * *")


def test_validate_raises_on_invalid() -> None:
    with pytest.raises(InvalidCronExpressionError):
        cron_validator.validate("99 * * * *")


def test_next_occurrence_is_in_the_future() -> None:
    base = datetime(2026, 7, 25, 12, 0, 0, tzinfo=UTC)
    nxt = cron_validator.next_occurrence("*/15 * * * *", from_time=base)
    assert nxt == datetime(2026, 7, 25, 12, 15, 0, tzinfo=UTC)


def test_next_occurrence_defaults_to_now() -> None:
    nxt = cron_validator.next_occurrence("* * * * *")
    assert nxt > datetime.now(UTC).replace(second=0, microsecond=0)


def test_next_occurrence_raises_on_invalid() -> None:
    with pytest.raises(InvalidCronExpressionError):
        cron_validator.next_occurrence("bad expression")
