"""Exceptions for the market data service layer."""


class DataServiceError(Exception):
    """Base exception for data service failures."""


class InvalidRequestError(DataServiceError):
    """Raised when user input is invalid."""


class InvalidSymbolError(InvalidRequestError):
    """Raised when a symbol cannot be normalized."""


class InvalidDateError(InvalidRequestError):
    """Raised when a date parameter is invalid."""


class InsufficientDataError(InvalidRequestError):
    """Raised when not enough data is available for analysis."""


class DataNotFoundError(DataServiceError):
    """Raised when a provider returns no usable data."""


class ProviderError(DataServiceError):
    """Raised when upstream providers fail."""
