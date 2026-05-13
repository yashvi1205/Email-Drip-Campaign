"""Authentication Service

Phase 2: User authentication and authorization business logic.

Handles:
- User registration (with password hashing)
- User login (password verification)
- Token generation and validation
- Role-based access control
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.password import hash_password, verify_password
from app.domain.exceptions import (
    AuthenticationError,
    EntityAlreadyExistsError,
    ValidationError,
)
from app.infrastructure.repositories.user_repository import UserRepository
from database.models import User


class AuthService:
    """User authentication and authorization service"""

    def __init__(self, db: Session):
        """Initialize with database session"""
        self.db = db
        self.user_repo = UserRepository(db)

    def register_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "user"
    ) -> User:
        """
        Register a new user.

        Args:
            username: Unique username
            email: Unique email address
            password: Plain text password (will be hashed)
            role: User role (admin, user, scraper, dashboard, etc.)

        Returns:
            Created User entity

        Raises:
            EntityAlreadyExistsError: If username or email already exists
            ValidationError: If username or email invalid
        """
        # Validate inputs
        if not username or len(username) < 3:
            raise ValidationError("Username must be at least 3 characters")
        if not email or "@" not in email:
            raise ValidationError("Invalid email address")
        if not password or len(password) < 8:
            raise ValidationError("Password must be at least 8 characters")

        # Check uniqueness
        if self.user_repo.get_by_username(username):
            raise EntityAlreadyExistsError(f"Username '{username}' already exists")
        if self.user_repo.get_by_email(email):
            raise EntityAlreadyExistsError(f"Email '{email}' already exists")

        # Create user with hashed password
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )

        return self.user_repo.create(user)

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate user with username and password.

        Args:
            username: Username
            password: Plain text password

        Returns:
            Authenticated User entity or None if authentication fails

        Raises:
            AuthenticationError: If user is inactive
        """
        user = self.user_repo.get_by_username(username)

        if not user:
            return None

        if not user.is_active:
            raise AuthenticationError(f"User '{username}' is inactive")

        if not verify_password(password, user.password_hash):
            return None

        return user

    def change_password(self, user_id: int, old_password: str, new_password: str) -> User:
        """
        Change user password.

        Args:
            user_id: User ID
            old_password: Current plain text password
            new_password: New plain text password

        Returns:
            Updated User entity

        Raises:
            EntityNotFoundError: If user doesn't exist
            AuthenticationError: If old password is incorrect
            ValidationError: If new password invalid
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            from app.domain.exceptions import EntityNotFoundError
            raise EntityNotFoundError(f"User {user_id} not found")

        if not verify_password(old_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect")

        if not new_password or len(new_password) < 8:
            raise ValidationError("New password must be at least 8 characters")

        user.password_hash = hash_password(new_password)
        return self.user_repo.update(user)

    def update_last_login(self, user_id: int) -> Optional[User]:
        """Update user's last login timestamp"""
        return self.user_repo.update_last_login(user_id)

    def set_user_active(self, user_id: int, is_active: bool) -> User:
        """Enable or disable user account"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            from app.domain.exceptions import EntityNotFoundError
            raise EntityNotFoundError(f"User {user_id} not found")

        user.is_active = is_active
        return self.user_repo.update(user)

    def change_user_role(self, user_id: int, new_role: str) -> User:
        """Change user's role"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            from app.domain.exceptions import EntityNotFoundError
            raise EntityNotFoundError(f"User {user_id} not found")

        valid_roles = ["admin", "user", "scraper", "dashboard"]
        if new_role not in valid_roles:
            raise ValidationError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")

        user.role = new_role
        return self.user_repo.update(user)
