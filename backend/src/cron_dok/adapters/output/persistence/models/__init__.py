"""ORM models. Importing this package registers every table on Base.metadata."""

from cron_dok.adapters.output.persistence.models.base import Base
from cron_dok.adapters.output.persistence.models.env_var import EnvVarModel
from cron_dok.adapters.output.persistence.models.execution import ExecutionModel
from cron_dok.adapters.output.persistence.models.project import ProjectModel
from cron_dok.adapters.output.persistence.models.runner import RunnerModel

__all__ = [
    "Base",
    "EnvVarModel",
    "ExecutionModel",
    "ProjectModel",
    "RunnerModel",
]
