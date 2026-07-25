"""Health router: the only public endpoint besides login (spec 9.4.3)."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe; public by design (no session required)."""
    return {"status": "ok"}
