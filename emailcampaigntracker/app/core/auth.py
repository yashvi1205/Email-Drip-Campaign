import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.settings import get_settings

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    username: str
    role: str


def _load_users() -> List[Dict[str, Any]]:
    settings = get_settings()
    data = json.loads(settings.auth_users_json)
    users: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        username = str(item.get("username", "")).strip()
        password = str(item.get("password", "")).strip()
        role = str(item.get("role", "user")).strip() or "user"
        if username and password:
            users.append({"username": username, "password": password, "role": role})
    return users


def authenticate_user(username: str, password: str) -> Optional[AuthUser]:
    for user in _load_users():
        if user["username"] == username and user["password"] == password:
            return AuthUser(username=user["username"], role=user["role"])
    return None


def _create_token(payload: Dict[str, Any], secret: str, expires_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expires_minutes)
    to_encode = {**payload, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    settings = get_settings()
    return jwt.encode(to_encode, secret, algorithm=settings.jwt_algorithm)


def create_access_token(user: AuthUser) -> str:
    settings = get_settings()
    return _create_token(
        {"sub": user.username, "role": user.role, "typ": "access"},
        settings.jwt_secret_key,
        settings.jwt_access_token_exp_minutes,
    )


def create_refresh_token(user: AuthUser) -> str:
    settings = get_settings()
    return _create_token(
        {"sub": user.username, "role": user.role, "typ": "refresh"},
        settings.jwt_refresh_secret_key,
        settings.jwt_refresh_token_exp_minutes,
    )


def _decode_token(token: str, *, refresh: bool) -> Dict[str, Any]:
    settings = get_settings()
    secret = settings.jwt_refresh_secret_key if refresh else settings.jwt_secret_key
    try:
        payload = jwt.decode(token, secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    expected_type = "refresh" if refresh else "access"
    if payload.get("typ") != expected_type:
        raise HTTPException(status_code=401, detail="Invalid token type")
    return payload


def _extract_api_key(request: Request) -> Optional[str]:
    header_key = request.headers.get("x-api-key")
    if header_key:
        return header_key.strip()
    return None


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthUser:
    settings = get_settings()

    if credentials and credentials.scheme.lower() == "bearer":
        payload = _decode_token(credentials.credentials, refresh=False)
        return AuthUser(username=str(payload["sub"]), role=str(payload.get("role", "user")))

    # Backward compatible fallback for Phase 0 API key usage
    api_key = _extract_api_key(request)
    if api_key:
        if api_key == settings.dashboard_api_key:
            return AuthUser(username="api-key-dashboard", role="dashboard")
        if api_key == settings.scraper_api_key:
            return AuthUser(username="api-key-scraper", role="scraper")
        if api_key == settings.api_key:
            return AuthUser(username="api-key-admin", role="admin")

    raise HTTPException(status_code=401, detail="Unauthorized")


def require_roles(*roles: str):
    role_set = set(roles)

    def _dep(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if current_user.role not in role_set:
            raise HTTPException(status_code=403, detail="Forbidden")
        return current_user

    return _dep


def refresh_access_token(refresh_token: str) -> Dict[str, str]:
    payload = _decode_token(refresh_token, refresh=True)
    user = AuthUser(username=str(payload["sub"]), role=str(payload.get("role", "user")))
    return {
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
        "token_type": "bearer",
    }

