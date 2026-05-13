"""User Repository

Phase 2: Data access layer for User entities (authentication).
"""

from typing import Optional

from sqlalchemy.orm import Session

from database.models import User
from .base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    """User authentication data access layer"""

    def __init__(self, db: Session):
        super().__init__(db, User)

    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self.db.query(User).filter(User.username == username).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.db.query(User).filter(User.email == email).first()

    def list_by_role(self, role: str):
        """Get all users with specific role"""
        return self.db.query(User).filter(User.role == role).all()

    def list_active(self):
        """Get all active users"""
        return self.db.query(User).filter(User.is_active == True).all()

    def update_last_login(self, user_id: int) -> Optional[User]:
        """Update user's last login timestamp"""
        from datetime import datetime
        user = self.get_by_id(user_id)
        if user:
            user.last_login_at = datetime.utcnow()
            self.update(user)
        return user
