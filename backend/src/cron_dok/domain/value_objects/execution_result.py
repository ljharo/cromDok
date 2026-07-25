"""Result of a finished job execution, as reported by a JobExecutor."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome of running a runner's script inside a container."""

    exit_code: int
    duration_ms: int
    timed_out: bool = False

    def __post_init__(self) -> None:
        if self.duration_ms < 0:
            raise ValueError(f"duration_ms must be >= 0, got {self.duration_ms}")

    @property
    def succeeded(self) -> bool:
        """An execution succeeded iff it finished in time with exit code 0."""
        return self.exit_code == 0 and not self.timed_out
