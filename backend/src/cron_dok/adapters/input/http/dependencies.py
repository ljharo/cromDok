"""FastAPI dependency wiring (spec 8.4: ``Depends`` lives only in this layer).

Services are application singletons built once in the lifespan and stored in
``app.state``; the dependencies below simply extract them per request. The
Unit of Work is exposed as a factory so each consumer decides its own
transaction scope (spec 6.2).

Identity chain (spec 9.4.2): :func:`resolve_identity` tries the
``crondok_session`` cookie first, then an ``Authorization: Bearer
crondok_...`` API key, and wraps the result in the unified
:class:`~cron_dok.services.identity.Identity` so ``require_role`` /
``require_write`` work unchanged for both credential kinds. The
``Authorization`` header is never logged. An API key can NEVER manage users
or API keys — even with the ``admin`` scope that requires a user session
(:func:`require_session_admin`).
"""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status

from cron_dok.domain.entities.user import User, UserRole
from cron_dok.ports.logs.log_store import LogStore
from cron_dok.ports.unit_of_work import AbstractUnitOfWork
from cron_dok.services import rbac
from cron_dok.services.api_key_service import TOKEN_PREFIX, ApiKeyService
from cron_dok.services.auth_service import AuthService
from cron_dok.services.env_var_service import EnvVarService
from cron_dok.services.errors import InsufficientRoleError
from cron_dok.services.execution_queue import ExecutionQueue
from cron_dok.services.identity import Identity
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


def get_api_key_service(request: Request) -> ApiKeyService:
    """Return the application ApiKeyService singleton."""
    service: ApiKeyService = request.app.state.api_key_service
    return service


def get_execution_queue(request: Request) -> ExecutionQueue:
    """Return the application ExecutionQueue singleton."""
    queue: ExecutionQueue = request.app.state.execution_queue
    return queue


def get_log_store(request: Request) -> LogStore:
    """Return the application LogStore singleton."""
    log_store: LogStore = request.app.state.log_store
    return log_store


async def resolve_identity(request: Request) -> Identity | None:
    """Resolve the caller identity as a chain of credential sources.

    1. ``crondok_session`` HttpOnly cookie (spec 9.4.1) → session user.
    2. ``Authorization: Bearer crondok_...`` header (spec 9.4.2) → API key.

    The Bearer credential is only attempted when it carries the API key
    prefix, and it is never logged. Returns None when no source yields a
    valid credential.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        auth_service: AuthService = request.app.state.auth_service
        user = await auth_service.resolve_session(token)
        if user is not None:
            return Identity(user=user)
    authorization = request.headers.get("Authorization")
    if authorization:
        scheme, _, credential = authorization.partition(" ")
        if scheme.lower() == "bearer" and credential.startswith(TOKEN_PREFIX):
            api_key_service: ApiKeyService = request.app.state.api_key_service
            api_key = await api_key_service.resolve(credential)
            if api_key is not None:
                return Identity(api_key=api_key)
    return None


async def get_current_identity(request: Request) -> Identity:
    """Return the authenticated identity (user or API key) or raise 401.

    Every protected endpoint depends on this (directly or through a role
    dependency); only ``POST /auth/login`` and ``GET /health`` are public
    (spec 9.4.3).
    """
    identity = await resolve_identity(request)
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return identity


CurrentUser = Annotated[Identity, Depends(get_current_identity)]
"""Any authenticated identity: session user or API key (viewers/read included)."""


def require_role(role: UserRole) -> Callable[[Identity], Coroutine[Any, Any, Identity]]:
    """Build a dependency enforcing a minimum role (spec 9.4.1 and 9.4.2).

    Works for both credential kinds: a session user contributes its role and
    an API key contributes its scope-mapped role.

    Args:
        role: minimum role; ``viewer`` < ``operator`` < ``admin``.

    Returns:
        A dependency returning the authenticated identity, raising
        ``InsufficientRoleError`` (mapped to 403) when the role is too low.
    """

    async def _checker(identity: CurrentUser) -> Identity:
        rbac.require_role(identity, role)
        return identity

    return _checker


async def get_session_user(identity: CurrentUser) -> User:
    """Return the session user behind the identity or raise 403.

    For endpoints that only make sense with a user session (e.g.
    ``GET /auth/me``); API key callers are rejected.
    """
    if identity.user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires a user session",
        )
    return identity.user


async def require_session_admin(identity: CurrentUser) -> User:
    """Require an admin role held by a user session, not an API key.

    An API key can NEVER manage users or API keys — not even with the
    ``admin`` scope (spec 9.4.2; a leaked key must not be able to mint more
    credentials). Session admins pass; everything else gets 403.

    Raises:
        InsufficientRoleError: mapped to 403 by the HTTP adapter.
    """
    rbac.require_role(identity, "admin")
    if identity.user is None:
        raise InsufficientRoleError(required="admin (user session)", actual="api-key")
    return identity.user


require_write = require_role("operator")
"""Dependency: operators and admins (every mutation endpoint); keys need ``runners:execute``."""

require_admin = require_role("admin")
"""Dependency: admin role (session admins, or keys with the ``admin`` scope)."""

WriteUser = Annotated[Identity, Depends(require_write)]
AdminUser = Annotated[Identity, Depends(require_admin)]

SessionUser = Annotated[User, Depends(get_session_user)]
"""Session users only (API keys are rejected with 403)."""

SessionAdminUser = Annotated[User, Depends(require_session_admin)]
"""Session admins only: user and API key management (keys never allowed)."""

UowFactoryDep = Annotated[UowFactory, Depends(get_uow_factory)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
RunnerServiceDep = Annotated[RunnerService, Depends(get_runner_service)]
EnvVarServiceDep = Annotated[EnvVarService, Depends(get_env_var_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
ApiKeyServiceDep = Annotated[ApiKeyService, Depends(get_api_key_service)]
ExecutionQueueDep = Annotated[ExecutionQueue, Depends(get_execution_queue)]
LogStoreDep = Annotated[LogStore, Depends(get_log_store)]
