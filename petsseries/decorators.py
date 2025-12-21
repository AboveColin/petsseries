"""
Decorators for the PetsSeries package.

This module provides decorators for error handling, input validation,
and other cross-cutting concerns.
"""

import logging
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar, cast

try:
    import aiohttp  # type: ignore[import-not-found]
except ImportError:
    aiohttp = None  # type: ignore[assignment, misc]

from .exceptions import (
    PetsSeriesAPIError,
    PetsSeriesNetworkError,
    PetsSeriesValidationError,
)

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


def handle_api_errors(operation_name: str):
    """
    Decorator to handle common API errors consistently.

    Args:
        operation_name: Human-readable name of the operation for logging.

    Example:
        @handle_api_errors("get user info")
        async def get_user_info(self) -> User:
            ...
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                result = await func(*args, **kwargs)
                return result
            except aiohttp.ClientResponseError as e:  # type: ignore[misc]
                _LOGGER.error(
                    "Failed to %s: HTTP %s %s",
                    operation_name,
                    e.status,
                    e.message,
                )
                raise PetsSeriesAPIError(
                    f"Failed to {operation_name}: {e.message}", status_code=e.status
                ) from e
            except aiohttp.ClientError as e:  # type: ignore[misc]
                _LOGGER.error("Network error during %s: %s", operation_name, e)
                raise PetsSeriesNetworkError(
                    f"Network error during {operation_name}: {e}"
                ) from e
            except Exception as e:
                _LOGGER.error("Unexpected error in %s: %s", operation_name, e)
                raise

        return cast(Callable[..., Awaitable[T]], wrapper)

    return decorator


def validate_device_id(func: Callable[..., T]) -> Callable[..., T]:
    """
    Validate device ID format before calling the function.

    Args:
        func: The function to wrap.

    Raises:
        PetsSeriesValidationError: If device_id is invalid.
    """

    @wraps(func)
    def wrapper(self: Any, device_id: str, *args: Any, **kwargs: Any) -> T:
        if not device_id or not isinstance(device_id, str):
            raise PetsSeriesValidationError("device_id must be a non-empty string")
        if len(device_id.strip()) == 0:
            raise PetsSeriesValidationError("device_id cannot be empty or whitespace")
        # Device IDs are typically alphanumeric with some special chars, min length ~10
        if len(device_id) < 10:
            _LOGGER.warning(
                "device_id '%s' appears to be unusually short", device_id[:20]
            )
        return func(self, device_id, *args, **kwargs)

    return cast(Callable[..., T], wrapper)


def validate_local_key(func: Callable[..., T]) -> Callable[..., T]:
    """
    Validate local key format before calling the function.

    Args:
        func: The function to wrap.

    Raises:
        PetsSeriesValidationError: If local_key is invalid.
    """

    @wraps(func)
    def wrapper(
        self: Any, device_id: str, local_key: str, *args: Any, **kwargs: Any
    ) -> T:
        if not local_key or not isinstance(local_key, str):
            raise PetsSeriesValidationError("local_key must be a non-empty string")
        if len(local_key.strip()) == 0:
            raise PetsSeriesValidationError("local_key cannot be empty or whitespace")
        return func(self, device_id, local_key, *args, **kwargs)

    return cast(Callable[..., T], wrapper)
