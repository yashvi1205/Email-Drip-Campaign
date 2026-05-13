"""Repository Layer

Phase 2: Data access abstraction using Repository Pattern.

All database queries are encapsulated in repository classes,
providing a clean interface and testability.
"""

from .base_repository import BaseRepository
from .lead_repository import LeadRepository
from .email_sequence_repository import EmailSequenceRepository
from .event_repository import EventRepository
from .user_repository import UserRepository

__all__ = [
    "BaseRepository",
    "LeadRepository",
    "EmailSequenceRepository",
    "EventRepository",
    "UserRepository",
]
