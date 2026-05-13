import pytest
from app.core.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    AuthUser,
)


class TestAuthentication:
    def test_authenticate_user_success(self):
        user = authenticate_user("admin", "admin123")
        assert user is not None
        assert user.username == "admin"
        assert user.role == "admin"

    def test_authenticate_user_invalid_username(self):
        user = authenticate_user("nonexistent", "password")
        assert user is None

    def test_authenticate_user_invalid_password(self):
        user = authenticate_user("admin", "wrongpassword")
        assert user is None

    def test_authenticate_scraper_user(self):
        user = authenticate_user("scraper", "scraper123")
        assert user is not None
        assert user.role == "scraper"

    def test_authenticate_dashboard_user(self):
        user = authenticate_user("dashboard", "dashboard123")
        assert user is not None
        assert user.role == "dashboard"


class TestJWTTokens:
    def test_create_access_token(self):
        user = AuthUser(username="testuser", role="user")
        token = create_access_token(user)
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self):
        user = AuthUser(username="testuser", role="user")
        token = create_refresh_token(user)
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_access_token_contains_user_info(self):
        import jwt
        from app.core.settings import get_settings

        user = AuthUser(username="testuser", role="admin")
        token = create_access_token(user)
        settings = get_settings()

        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "testuser"
        assert payload["role"] == "admin"
        assert payload["typ"] == "access"

    def test_tokens_have_expiry(self):
        import jwt
        from app.core.settings import get_settings

        user = AuthUser(username="testuser", role="user")
        token = create_access_token(user)
        settings = get_settings()

        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert "exp" in payload
        assert "iat" in payload
