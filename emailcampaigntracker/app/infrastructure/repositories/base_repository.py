"""Base Repository Pattern

Phase 2: Abstract repository class with common CRUD operations.

All concrete repositories inherit from BaseRepository to ensure
consistent data access patterns and testability.
"""

from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy.orm import Session

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """
    Abstract repository with common CRUD operations.

    Provides:
    - get_by_id(id) -> T | None
    - list_all() -> List[T]
    - create(entity: T) -> T
    - update(entity: T) -> T
    - delete(id: int) -> bool
    - count() -> int

    Concrete repositories inherit this and add domain-specific queries.
    """

    def __init__(self, db: Session, entity_class: Type[T]):
        """
        Initialize repository with database session and entity class.

        Args:
            db: SQLAlchemy database session
            entity_class: The ORM model class (e.g., Lead, EmailSequence)
        """
        self.db = db
        self.entity_class = entity_class

    def get_by_id(self, entity_id: int) -> Optional[T]:
        """Get entity by primary key"""
        return self.db.query(self.entity_class).filter(
            self.entity_class.id == entity_id
        ).first()

    def list_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """List all entities with pagination"""
        return self.db.query(self.entity_class).offset(skip).limit(limit).all()

    def create(self, entity: T) -> T:
        """Create and persist new entity"""
        self.db.add(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity

    def update(self, entity: T) -> T:
        """Update existing entity"""
        self.db.merge(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity

    def delete(self, entity_id: int) -> bool:
        """Delete entity by ID. Returns True if deleted, False if not found."""
        entity = self.get_by_id(entity_id)
        if not entity:
            return False
        self.db.delete(entity)
        self.db.flush()
        return True

    def count(self) -> int:
        """Get total count of entities"""
        return self.db.query(self.entity_class).count()

    def exists(self, entity_id: int) -> bool:
        """Check if entity exists"""
        return self.db.query(
            self.db.query(self.entity_class).filter(
                self.entity_class.id == entity_id
            ).exists()
        ).scalar()
