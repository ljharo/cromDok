"""FastAPI dependency wiring (spec 8.4: ``Depends`` lives only in this layer).

Services are application singletons built once in the lifespan and stored in
``app.state``; the dependencies below simply extract them per request. The
Unit of Work is exposed as a factory so each consumer decides its own
transaction scope (spec 6.2).
"""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status

from cron_dok.domain.entities.user import User, UserRole
from cron_dok.ports.logs.log_store import LogStore
from cron_dok.ports.unit_of_work import AbstractUnitOfWork
from cron_dok.services import rbac
from cron_dok.services.auth_service import AuthService
from cron_dok.services.env_var_service import EnvVarService
from cron_dok.services.execution_queue import ExecutionQueue
from cron_dok.services.project_service import ProjectService
from cron_dok.services.runner_service import RunnerService

SESSION_COOKIE_NAME = "crondok_session"
"""Name of the HttpOnly cookie carrying the opaque session token."""

UowFactory = Callable[[], AbstractUnitOfWork]


def get_uow_factory(request: Request) -> UowFactory:
    """Return the Unit of Work factory built in the lifespan."""
    factory: UowFactory = request.app.state.uow_factory
    return factory


def get_project_service(request: Request) -> ProjectService:
    """Return the application ProjectService singleton."""
    service: ProjectService = request.app.state.project_service
    return service


def get_runner_service(request: Request) -> RunnerService:
    """Return the application RunnerService singleton."""
    service: RunnerService = request.app.state.runner_service
    return service


def get_env_var_service(request: Request) -> EnvVarService:
    """Return the application EnvVarService singleton."""
    service: EnvVarService = request.app.state.env_var_service
    return service


def get_auth_service(request: Request) -> AuthService:
    """Return the application AuthService singleton."""
    service: AuthService = request.app.state.auth_service
    return service


def get_execution_queue(request: Request) -> ExecutionQueue:
    """Return the application ExecutionQueue singleton."""
    queue: ExecutionQueue = request.app.state.execution_queue
    return queue


def get_log_store(request: Request) -> LogStore:
    """Return the application LogStore singleton."""
    log_store: LogStore = request.app.state.log_store
    return log_store


async def resolve_identity(request: Request) -> User | None:
    """Resolve the caller identity as a chain of credential sources.

    Currently the only source is the ``crondok_session`` HttpOnly cookie
    (spec 9.4.1). **Extension point (Fase 3, spec 9.4.2):** when the cookie
    is absent, an ``Authorization: Bearer crondok_...`` API key will be
    resolved here and mapped to the same authorization context — routers and
    RBAC dependencies will not change.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    auth_service: AuthService = request.app.state.auth_service
    return await auth_service.resolve_session(token)


async def get_current_user(request: Request) -> User:
    """Return the authenticated user or raise 401.

    Every protected endpoint depends on this (directly or through a role
    dependency); only ``POST /auth/login`` and ``GET /health`` are public
    (spec 9.4.3).
    """
    user = await resolve_identity(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def require_role(role: UserRole) -> Callable[[User], Coroutine[Any, Any, User]]:
    """Build a dependency enforcing a minimum role (spec 9.4.1).

    Args:
        role: minimum role; ``viewer`` < ``operator`` < ``admin``.

    Returns:
        A dependency returning the authenticated user, raising
        ``InsufficientRoleError`` (mapped to 403) when the role is too low.
    """

    async def _checker(user: CurrentUser) -> User:
        rbac.require_role(user, role)
        return user

    return _checker


CurrentUser = Annotated[User, Depends(get_current_user)]
"""Any authenticated user (viewers included: read-only)."""

require_write = require_role("operator")
"""Dependency: operators and admins (every mutation endpoint)."""

require_admin = require_role("admin")
"""Dependency: admins only (user management, spec 9.4.1)."""

WriteUser = Annotated[User, Depends(require_write)]
AdminUser = Annotated[User, Depends(require_admin)]

UowFactoryDep = Annotated[UowFactory, Depends(get_uow_factory)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
RunnerServiceDep = Annotated[RunnerService, Depends(get_runner_service)]
EnvVarServiceDep = Annotated[EnvVarService, Depends(get_env_var_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
ExecutionQueueDep = Annotated[ExecutionQueue, Depends(get_execution_queue)]
LogStoreDep = Annotated[LogStore, Depends(get_log_store)]
