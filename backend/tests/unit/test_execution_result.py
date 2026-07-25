import pytest

from cron_dok.domain.value_objects.execution_result import ExecutionResult


def test_succeeded_when_exit_zero_and_not_timed_out() -> None:
    assert ExecutionResult(exit_code=0, duration_ms=120).succeeded is True


def test_not_succeeded_on_non_zero_exit() -> None:
    assert ExecutionResult(exit_code=1, duration_ms=120).succeeded is False


def test_not_succeeded_on_timeout_even_with_exit_zero() -> None:
    assert ExecutionResult(exit_code=0, duration_ms=120, timed_out=True).succeeded is False


def test_negative_duration_rejected() -> None:
    with pytest.raises(ValueError, match="duration_ms"):
        ExecutionResult(exit_code=0, duration_ms=-1)
