"""Unit tests for ProjectService over in-memory fakes (no database)."""

import pytest

from cron_dok.services.errors import DuplicateNameError, ProjectNotFoundError


async def test_create_assigns_id_and_persists(project_service) -> None:
    project = await project_service.create(name="etl", description="pipelines")

    assert project.id is not None
    stored = await project_service.get(project.id)
    assert stored.name == "etl"
    assert stored.description == "pipelines"


async def test_create_duplicate_name_raises(project_service) -> None:
    await project_service.create(name="etl")

    with pytest.raises(DuplicateNameError, match="project"):
        await project_service.create(name="etl")


async def test_get_missing_raises(project_service) -> None:
    with pytest.raises(ProjectNotFoundError):
        await project_service.get(999)


async def test_list_returns_all_projects(project_service) -> None:
    await project_service.create(name="a")
    await project_service.create(name="b")

    assert [p.name for p in await project_service.list()] == ["a", "b"]


async def test_update_changes_name_and_description(project_service) -> None:
    project = await project_service.create(name="old", description="x")

    updated = await project_service.update(project.id, name="new", description="y")

    assert updated.id == project.id
    assert updated.name == "new"
    assert updated.description == "y"
    assert updated.created_at == project.created_at


async def test_update_with_none_fields_leaves_them_unchanged(project_service) -> None:
    project = await project_service.create(name="etl", description="keep")

    updated = await project_service.update(project.id)

    assert updated.name == "etl"
    assert updated.description == "keep"


async def test_update_missing_raises(project_service) -> None:
    with pytest.raises(ProjectNotFoundError):
        await project_service.update(999, name="new")


async def test_update_to_taken_name_raises(project_service) -> None:
    await project_service.create(name="a")
    project_b = await project_service.create(name="b")

    with pytest.raises(DuplicateNameError):
        await project_service.update(project_b.id, name="a")


async def test_update_to_same_name_is_allowed(project_service) -> None:
    project = await project_service.create(name="etl")

    updated = await project_service.update(project.id, name="etl", description="d")

    assert updated.name == "etl"


async def test_create_with_empty_name_raises(project_service) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        await project_service.create(name="  ")


async def test_delete_removes_project(project_service) -> None:
    project = await project_service.create(name="etl")

    await project_service.delete(project.id)

    assert await project_service.list() == []


async def test_delete_missing_raises(project_service) -> None:
    with pytest.raises(ProjectNotFoundError):
        await project_service.delete(999)
