from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from schemas import (
    LoginRequest,
    LoginResponse,
    UserResponse,
)
from services import (
    authenticate_user,
    create_access_token,
    get_user_by_id,
    verify_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)

TOKEN_COOKIE = "repopress_token"


async def _resolve_token(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        repopress_token: Optional[str] = Cookie(default=None),
) -> Optional[str]:
    """Read the JWT from the Authorization header, falling back to the auth cookie."""
    if credentials is not None and credentials.credentials:
        return credentials.credentials
    return repopress_token


async def check_auth(token: Optional[str] = Depends(_resolve_token)) -> UserResponse:
    """Validate the JWT (from header or cookie) and return the current user.

    Used by nginx `auth_request` for the static documentation site, where only
    the cookie is available (no Authorization header).
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = await get_user_by_id(UUID(payload.get("sub")))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    return UserResponse.model_validate(user)


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserResponse:
    """Dependency to get the current authenticated user."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = UUID(payload.get("sub"))
    user = await get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    return UserResponse.model_validate(user)


async def require_admin(user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """Dependency that ensures the current user is an administrator."""
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def require_editor(user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """Dependency that ensures the current user can edit documentation."""
    if user.role != "editor" and not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editor access required",
        )
    return user


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, response: Response):
    """Authenticate a user, return a JWT, and set it as an HttpOnly cookie."""
    user = await authenticate_user(body.username, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    access_token = create_access_token(user)
    response.set_cookie(
        key=TOKEN_COOKIE,
        value=access_token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/logout")
async def logout(response: Response):
    """Logout: clear the auth cookie.

    Client-side token invalidation. The frontend should discard the token.
    """
    response.delete_cookie(key=TOKEN_COOKIE, path="/")
    return {"message": "Logged out successfully"}


@router.get("/user", response_model=UserResponse)
async def get_user(user: UserResponse = Depends(get_current_user)):
    """Get current authenticated user info."""
    return user


@router.get("/check-auth", response_model=UserResponse)
async def check_auth_status(user: UserResponse = Depends(check_auth)):
    """Auth endpoint for nginx `auth_request` (returns 200 when authenticated)."""
    return user


# Alias so nginx `auth_request` configs that call `/api/check-auth` also work.
alias_router = APIRouter(prefix="/api", tags=["auth"])


@alias_router.get("/check-auth", response_model=UserResponse)
async def check_auth_alias(user: UserResponse = Depends(check_auth)):
    """Alias for `/api/auth/check-auth`."""
    return user
