"""
Constants used throughout the PetsSeries package.

This module centralizes magic strings, numbers, and configuration values.
"""


class HTTPStatus:
    """HTTP status codes used in the API."""

    OK = 200
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    INTERNAL_SERVER_ERROR = 500


class Timeouts:
    """Default timeout values in seconds."""

    REQUEST = 10.0
    CONNECT = 5.0
    READ = 10.0


class UserAgents:
    """User agent strings for different API endpoints."""

    CLIENT = "UnofficialPetsSeriesClient/1.0"
    TOKEN = "Dalvik/2.1.0 (Linux; U; Android 14)"


class DeviceConstants:
    """Constants related to device operations."""

    MIN_DEVICE_ID_LENGTH = 10
    DEFAULT_TUYA_VERSION = 3.4
