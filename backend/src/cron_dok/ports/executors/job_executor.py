"""Job executor port (spec 4.2.2).

MVP implementation runs scripts in ephemeral local Docker containers;
future implementations may target Swarm or Kubernetes without touching the
rest of the system.
"""

from abc import ABC, abstractmethod

from cron_dok.domain.entities.runner import Runner
from cron_dok.domain.value_objects.execution_result import ExecutionResult
from cron_dok.ports.logs.log_store import LogSink


class JobExecutor(ABC):
    """Runs a runner's script in an isolated environment."""

    @abstractmethod
    async def execute(
        self, runner: Runner, env_vars: dict[str, str], log_sink: LogSink
    ) -> ExecutionResult:
        """Execute ``runner`` injecting ``env_vars``, streaming output to ``log_sink``."""
