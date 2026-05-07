from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
    refresh_access_token,
)
from app.schemas.auth import LoginRequest, MeResponse, RefreshRequest, TokenResponse

router = APIRouter(tags=["Auth"])


@router.post("/api/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
        token_type="bearer",
    )


@router.post("/api/auth/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshRequest):
    return TokenResponse(**refresh_access_token(payload.refresh_token))


@router.get("/api/auth/me", response_model=MeResponse)
def me(current_user=Depends(get_current_user)):
    return MeResponse(username=current_user.username, role=current_user.role)

