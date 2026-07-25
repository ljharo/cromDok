"""API key management router (spec 9.4.2).

Every endpoint requires an admin **with a user session**: an API key can
never manage API keys, not even with the ``admin`` scope — a leaked key
must not be able to mint more credentials.
"""

from fastapi import APIRouter, status

from cron_dok.adapters.input.http.dependencies import (
    ApiKeyServiceDep,
    SessionAdminUser,
)
from cron_dok.adapters.input.http.schemas.api_keys import (
    ApiKeyCreate,
    ApiKeyCreatedResponse,
    ApiKeyResponse,
)

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.get("")
async def list_api_keys(
    _admin: SessionAdminUser, service: ApiKeyServiceDep
) -> list[ApiKeyResponse]:
    """List every API key (session admin only); hashes/tokens are never exposed."""
    api_keys = await service.list()
    return [ApiKeyResponse.from_entity(api_key) for api_key in api_keys]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreate,
    admin: SessionAdminUser,
    service: ApiKeyServiceDep,
) -> ApiKeyCreatedResponse:
    """Issue an API key (session admin only).

    The plaintext token is returned exactly once in this response; only its
    SHA-256 is persisted.

    Raises:
        HTTPException: 422 (via the ``ValueError`` handler) if the name is
            empty or a scope is invalid.
    """
    created = await service.create(name=body.name, scopes=body.scopes, user=admin)
    return ApiKeyCreatedResponse(
        **ApiKeyResponse.from_entity(created.api_key).model_dump(),
        token=created.token,
    )


@router.delete("/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    api_key_id: int, _admin: SessionAdminUser, service: ApiKeyServiceDep
) -> None:
    """Revoke an API key immediately (session admin only).

    Raises:
        HTTPException: 404 (via the ``ApiKeyNotFoundError`` handler) if the
            key does not exist.
    """
    await service.revoke(api_key_id)
