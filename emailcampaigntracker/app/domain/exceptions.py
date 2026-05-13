"""Domain-specific exceptions

These exceptions represent business logic violations and invalid states.
They are independent of HTTP status codes or framework details.
"""


class DomainException(Exception):
    """Base exception for all domain logic errors"""
    pass


class EntityNotFoundError(DomainException):
    """Entity does not exist in the system"""
    pass


class EntityAlreadyExistsError(DomainException):
    """Entity with the same unique identifier already exists"""
    pass


class ValidationError(DomainException):
    """Domain validation failed (invalid email, URL, etc.)"""
    pass


class AuthenticationError(DomainException):
    """User authentication failed"""
    pass


class AuthorizationError(DomainException):
    """User is not authorized to perform this action"""
    pass


class InvalidStateError(DomainException):
    """Operation violates state constraints"""
    pass


class ExternalServiceError(DomainException):
    """Call to external service (Google Sheets, email, etc.) failed"""
    pass
