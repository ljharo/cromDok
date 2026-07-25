"""Resource limits applied to the Docker container of a job execution."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceLimits:
    """Hardware limits for a runner container.

    Defaults follow the spec (section 9.2): network disabled unless the user
    explicitly enables it per runner.
    """

    memory_mb: int = 256
    cpu_quota: float = 1.0
    pids_limit: int = 100
    network_enabled: bool = False

    def __post_init__(self) -> None:
        if self.memory_mb <= 0:
            raise ValueError(f"memory_mb must be positive, got {self.memory_mb}")
        if self.cpu_quota <= 0:
            raise ValueError(f"cpu_quota must be positive, got {self.cpu_quota}")
        if self.pids_limit <= 0:
            raise ValueError(f"pids_limit must be positive, got {self.pids_limit}")
