"""User management router (admin with a user session only, spec 9.4.1/9.4.2).

An API key can never manage users — not even with the ``admin`` scope.
There is no UserService yet (user CRUD beyond auth was not part of step
1.9), so this router works directly on the Unit of Work plus the
PasswordService — the same building blocks a future service would use.
"""

from dataclasses import replace

from fastapi import APIRouter, HTTPException, Request, status

from cron_dok.adapters.input.http.dependencies import SessionAdminUser, UowFactoryDep
from cron_dok.adapters.input.http.schemas.users import (
    PasswordReset,
    UserCreate,
    UserResponse,
)
from cron_dok.adapters.output.security.password_service import PasswordService
from cron_dok.domain.entities.user import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
async def list_users(_admin: SessionAdminUser, uow_factory: UowFactoryDep) -> list[UserResponse]:
    """List every user (admin only)."""
    async with uow_factory() as uow:
        users = await uow.users.list_all()
    return [UserResponse.from_entity(user) for user in users]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    _admin: SessionAdminUser,
    uow_factory: UowFactoryDep,
    request: Request,
) -> UserResponse:
    """Create a user (admin only).

    Raises:
        HTTPException: 409 if the username is taken; 422 (via the
            ``WeakPasswordError`` handler) if the password is too weak.
    """
    password_service: PasswordService = request.app.state.password_service
    password_hash = password_service.hash(body.password)
    async with uow_factory() as uow:
        if await uow.users.get_by_username(body.username) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate username: {body.username!r}",
            )
        user = await uow.users.save(
            User(username=body.username, password_hash=password_hash, role=body.role)
        )
    return UserResponse.from_entity(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, _admin: SessionAdminUser, uow_factory: UowFactoryDep) -> None:
    """Delete a user and their sessions (FK cascade); admin only.

    Raises:
        HTTPException: 404 if the user does not exist.
    """
    async with uow_factory() as uow:
        if await uow.users.get_by_id(user_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found: id={user_id}",
            )
        await uow.users.delete(user_id)


@router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    user_id: int,
    body: PasswordReset,
    _admin: SessionAdminUser,
    uow_factory: UowFactoryDep,
    request: Request,
) -> None:
    """Reset a user's password (admin only).

    Existing sessions are left untouched; the user keeps working until
    their session expires or they log out.

    Raises:
        HTTPException: 404 if the user does not exist; 422 (via the
            ``WeakPasswordError`` handler) if the password is too weak.
    """
    password_service: PasswordService = request.app.state.password_service
    password_hash = password_service.hash(body.password)
    async with uow_factory() as uow:
        user = await uow.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found: id={user_id}",
            )
        await uow.users.save(replace(user, password_hash=password_hash, must_change_password=False))
