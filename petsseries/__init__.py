"""
PetsSeriesClient module.
"""

from .api import PetsSeriesClient
from .auth import AuthError, AuthManager
from .devices import DevicesManager
from .discovery import DiscoveryManager, get_discovery_config
from .exceptions import (
    PetsSeriesAPIError,
    PetsSeriesAuthError,
    PetsSeriesConfigurationError,
    PetsSeriesError,
    PetsSeriesNetworkError,
    PetsSeriesValidationError,
)
from .homes import HomesManager
from .models import (
    AppRelease,
    Consumer,
    CountryInfo,
    Device,
    DeviceSettings,
    DiscoveryConfig,
    Event,
    EventType,
    FeederVoiceAudio,
    FilterTime,
    Home,
    HomeInvite,
    HomeInviteRole,
    HomeInviteStatus,
    Meal,
    ModeDevice,
    User,
)

__all__ = [
    # Main client
    "PetsSeriesClient",
    # Auth
    "AuthManager",
    "AuthError",
    # Exceptions
    "PetsSeriesError",
    "PetsSeriesAPIError",
    "PetsSeriesAuthError",
    "PetsSeriesNetworkError",
    "PetsSeriesValidationError",
    "PetsSeriesConfigurationError",
    # Managers
    "HomesManager",
    "DevicesManager",
    "DiscoveryManager",
    "get_discovery_config",
    # Models
    "Home",
    "Device",
    "Meal",
    "Consumer",
    "User",
    "ModeDevice",
    "Event",
    "EventType",
    "HomeInvite",
    "HomeInviteRole",
    "HomeInviteStatus",
    "DeviceSettings",
    "FilterTime",
    "FeederVoiceAudio",
    "DiscoveryConfig",
    "AppRelease",
    "CountryInfo",
]
