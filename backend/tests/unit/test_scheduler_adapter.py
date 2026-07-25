"""Unit tests for the APScheduler adapter.

The wrapped ``AsyncIOScheduler`` is never started: jobs are only inspected
through the scheduler API, so no real firing happens in unit tests.
"""

from datetime import UTC, datetime

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from cron_dok.adapters.input.scheduler.scheduler_adapter import (
    APSchedulerAdapter,
    build_trigger,
    job_id_for,
)
from cron_dok.domain.entities.runner import Runner
from cron_dok.domain.value_objects.cron_expression import CronExpression


def make_runner(runner_id: int | None = 1, cron: str = "0 3 * * *") -> Runner:
    return Runner(
        id=runner_id,
        project_id=1,
        name="nightly",
        script_content="echo hi",
        language="bash",
        cron_expression=CronExpression(cron),
    )


async def noop_callback(runner_id: int) -> None:
    pass


@pytest.fixture
def adapter() -> APSchedulerAdapter:
    return APSchedulerAdapter(AsyncIOScheduler())


def test_job_id_is_deterministic() -> None:
    assert job_id_for(42) == "runner-42"


def test_build_trigger_five_field_cron_fires_at_expected_time() -> None:
    trigger = build_trigger(CronExpression("30 9 * * *"))

    now = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
    next_fire = trigger.get_next_fire_time(None, now)

    # Times are in the trigger's timezone (local); only clock fields and
    # ordering are asserted so the test is timezone-independent.
    assert next_fire is not None
    assert (next_fire.hour, next_fire.minute, next_fire.second) == (9, 30, 0)
    assert next_fire > now


def test_build_trigger_six_field_cron_uses_seconds_field() -> None:
    trigger = build_trigger(CronExpression("*/10 * * * * *"))

    next_fire = trigger.get_next_fire_time(None, datetime(2026, 7, 25, 12, 0, 3, tzinfo=UTC))

    assert next_fire is not None
    assert next_fire.second == 10


def test_build_trigger_converts_cron_sunday_to_apscheduler() -> None:
    # Cron numbers Sunday as 0; APScheduler numbers Monday as 0. The adapter
    # must translate, or "0 0 * * 0" would fire on Mondays.
    trigger = build_trigger(CronExpression("0 0 * * 0"))

    # 2026-07-25 is a Saturday: next fire must be a Sunday at midnight.
    next_fire = trigger.get_next_fire_time(None, datetime(2026, 7, 25, 12, 0, tzinfo=UTC))

    assert next_fire is not None
    assert next_fire.weekday() == 6  # Sunday
    assert (next_fire.hour, next_fire.minute, next_fire.second) == (0, 0, 0)


def test_build_trigger_converts_weekday_ranges_and_lists() -> None:
    trigger = build_trigger(CronExpression("0 9 * * 1-5"))

    # From a Saturday, the next fire must be a weekday (Monday) at 09:00.
    next_fire = trigger.get_next_fire_time(None, datetime(2026, 7, 25, 12, 0, tzinfo=UTC))

    assert next_fire is not None
    assert next_fire.weekday() == 0  # Monday
    assert (next_fire.hour, next_fire.minute, next_fire.second) == (9, 0, 0)


def test_add_job_registers_with_deterministic_id_and_spec_options(
    adapter: APSchedulerAdapter,
) -> None:
    adapter.add_job(make_runner(), noop_callback)

    job = adapter.get_job(1)
    assert job is not None
    assert job.id == "runner-1"
    assert job.max_instances == 1
    assert job.coalesce is True


def test_add_job_replaces_existing_job(adapter: APSchedulerAdapter) -> None:
    adapter.add_job(make_runner(cron="0 3 * * *"), noop_callback)
    adapter.add_job(make_runner(cron="15 4 * * *"), noop_callback)

    job = adapter.get_job(1)
    assert job is not None
    assert "hour='4'" in str(job.trigger)
    assert "minute='15'" in str(job.trigger)


def test_add_job_without_runner_id_raises(adapter: APSchedulerAdapter) -> None:
    with pytest.raises(ValueError, match="without id"):
        adapter.add_job(make_runner(runner_id=None), noop_callback)


def test_remove_job(adapter: APSchedulerAdapter) -> None:
    adapter.add_job(make_runner(), noop_callback)

    adapter.remove_job(1)

    assert adapter.get_job(1) is None


def test_remove_unknown_job_is_noop(adapter: APSchedulerAdapter) -> None:
    adapter.remove_job(999)


def test_shutdown_without_start_is_noop(adapter: APSchedulerAdapter) -> None:
    adapter.shutdown()
