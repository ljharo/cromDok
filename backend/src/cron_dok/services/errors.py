"""Application-layer exceptions.

Pure Python errors with no HTTP semantics; the HTTP adapter maps them to
status codes (404/409/422) in its exception handlers.
"""


class ApplicationError(Exception):
    """Base class for every error raised by application services."""


class ProjectNotFoundError(ApplicationError):
    """Raised when a project id does not exist.

    Attributes:
        project_id: the id that was looked up.
    """

    def __init__(self, project_id: int) -> None:
        self.project_id = project_id
        super().__init__(f"Project not found: id={project_id}")


class RunnerNotFoundError(ApplicationError):
    """Raised when a runner id does not exist.

    Attributes:
        runner_id: the id that was looked up.
    """

    def __init__(self, runner_id: int) -> None:
        self.runner_id = runner_id
        super().__init__(f"Runner not found: id={runner_id}")


class EnvVarNotFoundError(ApplicationError):
    """Raised when an env var id does not exist.

    Attributes:
        env_var_id: the id that was looked up.
    """

    def __init__(self, env_var_id: int) -> None:
        self.env_var_id = env_var_id
        super().__init__(f"Env var not found: id={env_var_id}")


class ApiKeyNotFoundError(ApplicationError):
    """Raised when an API key id does not exist.

    Attributes:
        api_key_id: the id that was looked up.
    """

    def __init__(self, api_key_id: int) -> None:
        self.api_key_id = api_key_id
        super().__init__(f"API key not found: id={api_key_id}")


class InvalidCredentialsError(ApplicationError):
    """Raised when a login fails.

    The message is deliberately generic so callers cannot distinguish an
    unknown username from a wrong password or an inactive account.
    """

    def __init__(self) -> None:
        super().__init__("Invalid username or password")


class InsufficientRoleError(ApplicationError):
    """Raised when a user's role does not meet the required minimum.

    Attributes:
        required: the minimum role the operation needs.
        actual: the role the user has.
    """

    def __init__(self, required: str, actual: str) -> None:
        self.required = required
        self.actual = actual
        super().__init__(f"Role {actual!r} is insufficient; requires at least {required!r}")


class DuplicateNameError(ApplicationError):
    """Raised when a create/rename would collide with an existing name.

    Attributes:
        entity: kind of entity that collided (``"project"`` or ``"runner"``).
        name: the duplicated name.
    """

    def __init__(self, entity: str, name: str) -> None:
        self.entity = entity
        self.name = name
        super().__init__(f"Duplicate {entity} name: {name!r}")
