"""
Custom exception classes for the PetsSeries package.

This module defines a hierarchy of exceptions for better error handling
and more specific error reporting.
"""

from typing import Optional


class PetsSeriesError(Exception):
    """Base exception for all PetsSeries errors."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class PetsSeriesAPIError(PetsSeriesError):
    """Error from API responses."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code

    def __str__(self) -> str:
        if self.status_code:
            return f"{self.message} (HTTP {self.status_code})"
        return self.message


class PetsSeriesAuthError(PetsSeriesError):
    """Authentication-related errors."""

    pass


class PetsSeriesNetworkError(PetsSeriesError):
    """Network-related errors."""

    pass


class PetsSeriesValidationError(PetsSeriesError):
    """Input validation errors."""

    pass


class PetsSeriesConfigurationError(PetsSeriesError):
    """Configuration-related errors."""

    pass
