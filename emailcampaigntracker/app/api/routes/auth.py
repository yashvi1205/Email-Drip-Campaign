from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
    refresh_access_token,
)
from app.schemas.auth import LoginRequest, MeResponse, RefreshRequest, TokenResponse

router = APIRouter(tags=["Authentication"])


@router.post(
    "/api/auth/login",
    summary="User Login",
    description="Authenticate user with username and password and issue JWT tokens",
    response_description="JWT access and refresh tokens"
)
def login(payload: LoginRequest):
    """Authenticate user credentials and issue JWT tokens"""
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
        token_type="bearer",
    )


@router.post(
    "/api/auth/refresh",
    summary="Refresh Access Token",
    description="Use an unexpired refresh token to obtain a new access token",
    response_description="New JWT access token"
)
def refresh_token(payload: RefreshRequest):
    """Get new access token from refresh token"""
    return TokenResponse(**refresh_access_token(payload.refresh_token))


@router.get(
    "/api/auth/me",
    summary="Get Current User",
    description="Retrieve information about the currently authenticated user",
    response_description="Current user details"
)
def me(current_user=Depends(get_current_user)):
    """Get current user profile information"""
    return MeResponse(username=current_user.username, role=current_user.role)

