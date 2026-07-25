"""Shared fixtures for service unit tests: fakes, no database."""

import pytest

from cron_dok.services.project_service import ProjectService
from cron_dok.services.runner_service import RunnerService
from tests.unit.fakes import FakeUnitOfWork


@pytest.fixture
def fake_uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def project_service(fake_uow: FakeUnitOfWork) -> ProjectService:
    return ProjectService(lambda: fake_uow)


@pytest.fixture
def runner_service(fake_uow: FakeUnitOfWork) -> RunnerService:
    return RunnerService(lambda: fake_uow)
