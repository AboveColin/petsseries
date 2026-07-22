"""
PetsSeriesClient module.
"""

from .api import PetsSeriesClient
from .auth import AuthError, AuthManager
from .native_signer import NativeSignerError, NativeTuyaSigner
from .tuya_mobile import TuyaMobileClient
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
from .tuya_cloud import TuyaCloudClient, get_tuya_credentials_from_philips
from .enhanced_credentials import (
    get_complete_device_credentials,
    get_device_info_from_philips,
    save_credentials_to_file,
    format_credentials_for_display
)

__all__ = [
    # Main client
    "PetsSeriesClient",
    # Auth
    "AuthManager",
    "AuthError",
    "NativeTuyaSigner",
    "NativeSignerError",
    "TuyaMobileClient",
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
    # Tuya Cloud
    "TuyaCloudClient",
    "get_tuya_credentials_from_philips",
    # Enhanced Credentials
    "get_complete_device_credentials",
    "get_device_info_from_philips",
    "save_credentials_to_file",
    "format_credentials_for_display",
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
