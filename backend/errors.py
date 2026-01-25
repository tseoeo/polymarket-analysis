"""Centralized exception hierarchy for Polymarket Analyzer.

Provides a structured exception hierarchy for consistent error handling
across the application. All exceptions inherit from PolymarketError.
"""


class PolymarketError(Exception):
    """Base exception for all Polymarket Analyzer errors."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} ({self.details})"
        return self.message


class APIError(PolymarketError):
    """Error from external API call."""

    def __init__(self, message: str, status_code: int = None, response: str = None):
        super().__init__(message, {"status_code": status_code})
        self.status_code = status_code
        self.response = response


class RateLimitError(APIError):
    """Rate limit exceeded (HTTP 429)."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = None):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class AuthenticationError(APIError):
    """Authentication failed (HTTP 401/403)."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class DataValidationError(PolymarketError):
    """Invalid data from API or database."""

    def __init__(self, message: str, field: str = None, value=None):
        super().__init__(message, {"field": field, "value": value})
        self.field = field
        self.value = value


class ConfigurationError(PolymarketError):
    """Invalid or missing configuration."""

    def __init__(self, message: str, setting: str = None):
        super().__init__(message, {"setting": setting})
        self.setting = setting


class AnalysisError(PolymarketError):
    """Error during analysis processing."""

    def __init__(self, message: str, analyzer: str = None):
        super().__init__(message, {"analyzer": analyzer})
        self.analyzer = analyzer
