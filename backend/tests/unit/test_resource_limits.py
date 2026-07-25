import dataclasses

import pytest

from cron_dok.domain.value_objects.resource_limits import ResourceLimits


def test_defaults_match_spec() -> None:
    limits = ResourceLimits()
    assert limits.memory_mb == 256
    assert limits.cpu_quota == 1.0
    assert limits.pids_limit == 100
    assert limits.network_enabled is False


@pytest.mark.parametrize("memory_mb", [0, -1, -256])
def test_non_positive_memory_rejected(memory_mb: int) -> None:
    with pytest.raises(ValueError, match="memory_mb"):
        ResourceLimits(memory_mb=memory_mb)


@pytest.mark.parametrize("cpu_quota", [0.0, -0.5])
def test_non_positive_cpu_quota_rejected(cpu_quota: float) -> None:
    with pytest.raises(ValueError, match="cpu_quota"):
        ResourceLimits(cpu_quota=cpu_quota)


@pytest.mark.parametrize("pids_limit", [0, -10])
def test_non_positive_pids_limit_rejected(pids_limit: int) -> None:
    with pytest.raises(ValueError, match="pids_limit"):
        ResourceLimits(pids_limit=pids_limit)


def test_is_frozen() -> None:
    limits = ResourceLimits()
    with pytest.raises(dataclasses.FrozenInstanceError):
        limits.memory_mb = 512  # type: ignore[misc]
