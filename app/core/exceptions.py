class AppError(Exception):
    """Base application exception."""


class ValidationError(AppError):
    """Validation error for domain inputs."""


class ExternalServiceError(AppError):
    """Raised when external API or service call fails."""
