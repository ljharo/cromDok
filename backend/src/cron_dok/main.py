"""FastAPI application factory: lifespan wiring and exception mapping.

The lifespan builds the whole object graph (spec 8.4: services receive their
dependencies by constructor; only this adapter knows FastAPI):

1. Settings, engine and Unit of Work factory.
2. EncryptionService (master key bootstrap, spec 9.1) and FileLogStore.
3. JobExecutor: the real DockerExecutor when ``CRONDOK_EXECUTOR_ENABLED``
   is true and the daemon answers; otherwise a documented fallback that
   fails executions cleanly, so the API still boots without Docker.
4. ExecutionQueue (started) and SchedulerService (rehydrated + started,
   spec 7).
5. First-boot admin bootstrap: the generated password is logged exactly
   once (spec 9.4.1, Gitea/Portainer pattern).

Shutdown is ordered: scheduler first (no new triggers), then the queue
(in-flight executions are cancelled and marked ``killed``), then the engine.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from cron_dok.adapters.input.http.rate_limit import SlidingWindowRateLimiter
from cron_dok.adapters.input.http.routers import (
    api_keys,
    auth,
    env_vars,
    executions,
    health,
    projects,
    runners,
    triggers,
    users,
)
from cron_dok.adapters.input.http.routers.auth import LoginRateLimiter
from cron_dok.adapters.input.scheduler.scheduler_adapter import APSchedulerAdapter
from cron_dok.adapters.output.executor.docker_executor import DockerExecutor
from cron_dok.adapters.output.logs.file_log_store import FileLogStore
from cron_dok.adapters.output.persistence.database import (
    create_session_factory,
    create_sqlite_engine,
)
from cron_dok.adapters.output.persistence.models import Base
from cron_dok.adapters.output.persistence.unit_of_work import UnitOfWork
from cron_dok.adapters.output.security.encryption_service import (
    create_encryption_service,
)
from cron_dok.adapters.output.security.password_service import PasswordService
from cron_dok.config import Settings, get_settings
from cron_dok.domain.entities.runner import Runner
from cron_dok.domain.value_objects.cron_expression import InvalidCronExpressionError
from cron_dok.domain.value_objects.execution_result import ExecutionResult
from cron_dok.ports.executors.job_executor import JobExecutor
from cron_dok.ports.logs.log_store import LogSink
from cron_dok.services.api_key_service import ApiKeyService
from cron_dok.services.auth_service import AuthService
from cron_dok.services.env_var_service import EnvVarService
from cron_dok.services.errors import (
    ApiKeyNotFoundError,
    DuplicateNameError,
    EnvVarNotFoundError,
    InsufficientRoleError,
    InvalidCredentialsError,
    ProjectNotFoundError,
    RunnerNotFoundError,
)
from cron_dok.services.execution_queue import ExecutionQueue
from cron_dok.services.notification_service import NotificationService
from cron_dok.services.project_service import ProjectService
from cron_dok.services.retention_service import RetentionService
from cron_dok.services.runner_service import RunnerService
from cron_dok.services.scheduler_service import JobScheduler, SchedulerService

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"


class UnavailableExecutor(JobExecutor):
    """Fallback executor used when Docker is not usable at startup.

    Selected when ``CRONDOK_EXECUTOR_ENABLED`` is false or the daemon does
    not answer at boot: the API, scheduler and queue keep working and every
    execution is marked ``failed`` with an explanatory log line, instead of
    the process refusing to start.
    """

    async def execute(
        self, runner: Runner, env_vars: dict[str, str], log_sink: LogSink
    ) -> ExecutionResult:
        """Fail the execution: no executor backend is available."""
        await log_sink.write(
            "CronDok started without a Docker executor "
            "(CRONDOK_EXECUTOR_ENABLED=false or daemon unreachable); "
            "this execution cannot run.\n"
        )
        raise RuntimeError("Docker executor is unavailable")


def _register_exception_handlers(app: FastAPI) -> None:
    """Map application/domain exceptions to HTTP status codes (spec 9.4)."""

    @app.exception_handler(ProjectNotFoundError)
    async def project_not_found_handler(
        _request: Request, exc: ProjectNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(RunnerNotFoundError)
    async def runner_not_found_handler(_request: Request, exc: RunnerNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(EnvVarNotFoundError)
    async def env_var_not_found_handler(
        _request: Request, exc: EnvVarNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(ApiKeyNotFoundError)
    async def api_key_not_found_handler(
        _request: Request, exc: ApiKeyNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(DuplicateNameError)
    async def duplicate_name_handler(_request: Request, exc: DuplicateNameError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @app.exception_handler(InvalidCronExpressionError)
    async def invalid_cron_handler(
        _request: Request, exc: InvalidCronExpressionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ValueError)
    async def domain_value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
        # Domain validations (empty names, weak passwords, invalid env var
        # keys, bad resource limits...) surface as ValueError.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )

    @app.exception_handler(InvalidCredentialsError)
    async def invalid_credentials_handler(
        _request: Request, exc: InvalidCredentialsError
    ) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": str(exc)})

    @app.exception_handler(InsufficientRoleError)
    async def insufficient_role_handler(
        _request: Request, exc: InsufficientRoleError
    ) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})


def create_app(
    settings: Settings | None = None,
    *,
    executor: JobExecutor | None = None,
    scheduler_backend: JobScheduler | None = None,
) -> FastAPI:
    """Build the FastAPI application.

    Args:
        settings: application settings; defaults to ``get_settings()``.
        executor: executor override (tests inject fakes); when None the
            lifespan builds the Docker executor or its documented fallback.
        scheduler_backend: scheduler backend override (tests inject fakes);
            when None the APScheduler adapter is used.

    Returns:
        The configured app; the lifespan wires and starts the services.
    """
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_sqlite_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = create_session_factory(engine)

        def uow_factory() -> UnitOfWork:
            return UnitOfWork(session_factory)

        encryption = create_encryption_service(settings)
        log_store = FileLogStore(settings.log_dir)
        resolved_executor = (
            executor if executor is not None else await _build_executor_async(settings)
        )

        password_service = PasswordService()
        auth_service = AuthService(uow_factory, password_service)
        api_key_service = ApiKeyService(uow_factory)
        project_service = ProjectService(uow_factory)
        env_var_service = EnvVarService(uow_factory, encryption)

        async def env_resolver(runner: Runner) -> dict[str, str]:
            assert runner.id is not None  # enqueued runners are persisted
            return await env_var_service.resolve_for_runner(runner.id)

        queue = ExecutionQueue(
            uow_factory,
            resolved_executor,
            log_store,
            max_concurrent_jobs=settings.max_concurrent_jobs,
            env_resolver=env_resolver,
            notifier=NotificationService(settings.webhook_url, timeout=settings.webhook_timeout),
        )
        scheduler_service = SchedulerService(
            uow_factory, queue, scheduler_backend or APSchedulerAdapter()
        )
        runner_service = RunnerService(uow_factory, scheduler_service)
        retention_service = RetentionService(uow_factory, log_store, settings.log_retention_days)

        app.state.settings = settings
        app.state.uow_factory = uow_factory
        app.state.password_service = password_service
        app.state.auth_service = auth_service
        app.state.project_service = project_service
        app.state.runner_service = runner_service
        app.state.env_var_service = env_var_service
        app.state.api_key_service = api_key_service
        app.state.execution_queue = queue
        app.state.scheduler_service = scheduler_service
        app.state.log_store = log_store
        app.state.retention_service = retention_service

        queue.start()
        await scheduler_service.rehydrate()
        # System job (spec 6.4): daily purge of old executions and their
        # logs. Registered directly in the scheduler — it is not a user
        # runner, so it bypasses the ExecutionQueue and creates no Execution.
        scheduler_service.register_system_job(
            "retention-purge", retention_service.purge_safely, hour=4, minute=17
        )
        scheduler_service.start()
        bootstrap_password = await auth_service.bootstrap_admin()
        if bootstrap_password is not None:
            logger.warning(
                "First boot: created admin user %r with password %r "
                "(shown once; change it on first login)",
                "admin",
                bootstrap_password,
            )
        try:
            yield
        finally:
            # Order matters: stop producing triggers before draining work.
            scheduler_service.shutdown()
            await queue.stop()
            await engine.dispose()

    app = FastAPI(title="CronDok", version="0.1.0", lifespan=lifespan)
    app.state.login_rate_limiter = LoginRateLimiter()
    app.state.trigger_rate_limiter = SlidingWindowRateLimiter(settings.rate_limit_triggers)
    _register_exception_handlers(app)
    for module in (
        health,
        auth,
        users,
        api_keys,
        projects,
        runners,
        executions,
        env_vars,
        triggers,
    ):
        app.include_router(module.router, prefix=API_PREFIX)

    if settings.static_dir is not None and Path(settings.static_dir).is_dir():
        static_dir = Path(settings.static_dir)
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            """Serve the SPA shell for any client-side route (spec 1.3).

            Lets React Router own deep links (e.g. ``/projects/5``) without a
            404 on refresh; only paths outside ``/api`` fall through here,
            since API routers are matched first.
            """
            if full_path.startswith("api/"):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return FileResponse(static_dir / "index.html")

    return app


def _build_executor(settings: Settings) -> JobExecutor:
    """Build the production executor, falling back when Docker is unusable.

    Blocking (docker-py I/O); call it via :func:`_build_executor_async`.
    """
    if not settings.executor_enabled:
        logger.warning(
            "CRONDOK_EXECUTOR_ENABLED=false: executions will fail until Docker is enabled"
        )
        return UnavailableExecutor()

    import docker

    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        logger.exception(
            "Docker daemon unreachable at startup; falling back to UnavailableExecutor"
        )
        return UnavailableExecutor()
    return DockerExecutor(settings, client)


async def _build_executor_async(settings: Settings) -> JobExecutor:
    """Build the executor without blocking the event loop (spec 8.4)."""
    return await asyncio.to_thread(_build_executor, settings)


app = create_app()
