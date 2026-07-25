import dataclasses

import pytest

from cron_dok.domain.value_objects.cron_expression import (
    CronExpression,
    InvalidCronExpressionError,
)


def test_valid_five_field_expression() -> None:
    expr = CronExpression("*/5 * * * *")
    assert expr.value == "*/5 * * * *"
    assert str(expr) == "*/5 * * * *"


def test_valid_six_field_expression_with_seconds() -> None:
    assert CronExpression("0 */10 * * * *").value == "0 */10 * * * *"


@pytest.mark.parametrize(
    "expression",
    ["not a cron", "61 * * * *", "* * *", "", "0 0 32 * *"],
)
def test_invalid_expressions_raise(expression: str) -> None:
    with pytest.raises(InvalidCronExpressionError):
        CronExpression(expression)


def test_invalid_cron_expression_error_is_value_error() -> None:
    with pytest.raises(ValueError):
        CronExpression("bogus")


def test_is_frozen() -> None:
    expr = CronExpression("* * * * *")
    with pytest.raises(dataclasses.FrozenInstanceError):
        expr.value = "0 * * * *"  # type: ignore[misc]
