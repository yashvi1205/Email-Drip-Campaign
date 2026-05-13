"""Query builder for efficient database queries

Provides filtering, pagination, and optimization utilities.
"""

from typing import Any, Dict, List, Optional, Type, TypeVar

from sqlalchemy import and_, or_
from sqlalchemy.orm import Query, Session

T = TypeVar("T")


class QueryBuilder:
    """Fluent query builder for optimized database queries"""

    def __init__(self, session: Session, model: Type[T]):
        self.session = session
        self.model = model
        self.query = session.query(model)
        self._limit = None
        self._offset = None

    def filter(self, **kwargs) -> "QueryBuilder":
        """Add equality filters"""
        for key, value in kwargs.items():
            if hasattr(self.model, key) and value is not None:
                self.query = self.query.filter(
                    getattr(self.model, key) == value
                )
        return self

    def filter_in(self, field: str, values: List[Any]) -> "QueryBuilder":
        """Add IN filter"""
        if values and hasattr(self.model, field):
            self.query = self.query.filter(
                getattr(self.model, field).in_(values)
            )
        return self

    def filter_range(
        self, field: str, min_val: Optional[Any], max_val: Optional[Any]
    ) -> "QueryBuilder":
        """Add range filter"""
        if hasattr(self.model, field):
            column = getattr(self.model, field)
            if min_val is not None:
                self.query = self.query.filter(column >= min_val)
            if max_val is not None:
                self.query = self.query.filter(column <= max_val)
        return self

    def filter_like(self, field: str, pattern: str) -> "QueryBuilder":
        """Add LIKE filter for text search"""
        if pattern and hasattr(self.model, field):
            self.query = self.query.filter(
                getattr(self.model, field).ilike(f"%{pattern}%")
            )
        return self

    def order_by(self, field: str, desc: bool = False) -> "QueryBuilder":
        """Add ordering"""
        if hasattr(self.model, field):
            column = getattr(self.model, field)
            self.query = self.query.order_by(
                column.desc() if desc else column
            )
        return self

    def limit(self, limit: int) -> "QueryBuilder":
        """Set result limit"""
        self._limit = limit
        return self

    def offset(self, offset: int) -> "QueryBuilder":
        """Set result offset"""
        self._offset = offset
        return self

    def paginate(self, page: int = 1, per_page: int = 20) -> "QueryBuilder":
        """Apply pagination"""
        if page < 1:
            page = 1
        if per_page < 1:
            per_page = 20

        self._offset = (page - 1) * per_page
        self._limit = per_page
        return self

    def all(self) -> List[T]:
        """Execute query and return all results"""
        query = self.query
        if self._offset is not None:
            query = query.offset(self._offset)
        if self._limit is not None:
            query = query.limit(self._limit)
        return query.all()

    def first(self) -> Optional[T]:
        """Execute query and return first result"""
        return self.query.first()

    def count(self) -> int:
        """Count results"""
        return self.query.count()

    def get_paginated(self, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Get paginated results with metadata"""
        self.paginate(page, per_page)
        total = self.query.count()
        results = self.all()

        return {
            "data": results,
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
        }


def build_query(session: Session, model: Type[T]) -> QueryBuilder:
    """Create a new query builder"""
    return QueryBuilder(session, model)
