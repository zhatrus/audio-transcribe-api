"""Optional API-key authentication.

If ``API_KEY`` is set, every protected endpoint requires a matching
``X-API-Key`` header. If it is empty, authentication is disabled (useful for
local development on a closed network).
"""
from fastapi import Header, HTTPException, status

from .config import get_settings


async def require_api_key(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    api_key = get_settings().api_key
    if not api_key:
        return
    bearer = authorization[7:] if authorization and authorization.startswith("Bearer ") else None
    if x_api_key == api_key or bearer == api_key:
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
    )
