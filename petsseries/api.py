"""
API client for interacting with the PetsSeries backend services.

This module provides the PetsSeriesClient class, which handles authentication,
data retrieval, and device management for the PetsSeries application.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Union

import aiohttp  # type: ignore[import-not-found]

from .auth import AuthManager
from .config import Config
from .constants import DeviceConstants, HTTPStatus, Timeouts, UserAgents
from .decorators import handle_api_errors, validate_device_id, validate_local_key
from .devices import DevicesManager
from .discovery import DiscoveryManager
from .events import EventsManager
from .exceptions import PetsSeriesValidationError
from .homes import HomesManager

# Import MealsManager
from .meals import MealsManager
from .models import (
    Consumer,
    Device,
    Home,
    ModeDevice,
    User,
)
from .session import create_ssl_context

# Optional import for Tuya local control
try:
    from .tuya import TuyaClient, TuyaError
except ImportError:
    TuyaClient = None  # type: ignore[assignment, misc]
    TuyaError = Exception  # type: ignore[assignment, misc]

_LOGGER = logging.getLogger(__name__)


class PetsSeriesClient:
    # pylint: disable=too-many-public-methods
    """
    Client for interacting with the PetsSeries API.

    Provides methods to authenticate, retrieve user and device information,
    and manage device settings.
    """

    def __init__(
        self,
        token_file="tokens.json",
        access_token=None,
        refresh_token=None,
        tuya_credentials: Optional[Dict[str, str]] = None,
        token_save_callback: Optional[Callable] = None,
    ):
        self.auth = AuthManager(
            token_file, access_token, refresh_token, save_callback=token_save_callback
        )
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers: Dict[str, str] = {}
        self.headers_token: Dict[str, str] = {}
        self.timeout = aiohttp.ClientTimeout(total=Timeouts.REQUEST)
        self.config = Config()
        self.tuya_client: Optional[TuyaClient] = None  # type: ignore
        self.tuya_device_credentials: list = []  # List of device credentials (manually set)

        # Initialize managers
        self.meals = MealsManager(self)
        self.events = EventsManager(self)
        self.homes_manager = HomesManager(self)
        self.devices_manager = DevicesManager(self)
        self.discovery_manager = DiscoveryManager(self.session)

        if tuya_credentials:
            if TuyaClient is None:
                _LOGGER.error(
                    "TuyaClient not available. Install 'tinytuya' to enable Tuya support."
                )
                raise ImportError(
                    "TuyaClient not available. Install 'tinytuya' to enable Tuya support."
                )
            try:
                self.tuya_client = TuyaClient(
                    client_id=tuya_credentials["client_id"],
                    ip=tuya_credentials["ip"],
                    local_key=tuya_credentials["local_key"],
                    version=float(
                        tuya_credentials.get(
                            "version", DeviceConstants.DEFAULT_TUYA_VERSION
                        )
                    ),
                )
                _LOGGER.info("TuyaClient initialized successfully.")
            except TuyaError as e:
                _LOGGER.error("Failed to initialize TuyaClient: %s", e)
                raise

    async def get_client(self) -> aiohttp.ClientSession:
        # pylint: disable=duplicate-code
        """
        Get an aiohttp.ClientSession with certifi's CA bundle.

        Initializes the session if it doesn't exist.
        """
        if self.session is None:
            ssl_context = await create_ssl_context()
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(
                timeout=self.timeout, connector=connector
            )
            _LOGGER.debug("aiohttp.ClientSession initialized with certifi CA bundle.")
        assert self.session is not None
        return self.session

    async def initialize(self) -> None:
        """
        Initialize the client by loading tokens and refreshing the access token if necessary.
        """
        if self.auth.access_token and self.auth.refresh_token:
            await self.auth.save_tokens(
                str(self.auth.access_token), str(self.auth.refresh_token)
            )
        await self.auth.load_tokens()
        if await self.auth.is_token_expired():
            _LOGGER.info("Access token expired, refreshing...")
            await self.auth.refresh_access_token()
        await self._refresh_headers()

    async def _refresh_headers(self) -> None:
        """
        Refresh the headers with the latest access token.
        """
        access_token = await self.auth.get_access_token()
        self.headers = {
            "Accept-Encoding": "gzip",
            "Authorization": f"Bearer {access_token}",
            "Connection": "keep-alive",
            "User-Agent": UserAgents.CLIENT,
        }
        self.headers_token = {
            "Accept-Encoding": "gzip",
            "Accept": "application/json",
            "Connection": "keep-alive",
            "Host": "cdc.accounts.home.id",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": UserAgents.TOKEN,
        }
        _LOGGER.debug("Headers refreshed successfully.")

    async def close(self) -> None:
        """
        Close the client session and save tokens.
        """
        if self.session:
            await self.session.close()
            self.session = None
            _LOGGER.debug("aiohttp.ClientSession closed.")
        await self.auth.close()

    def _find_device_credential(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a device credential by device_id.

        Args:
            device_id: The Tuya device ID to search for.

        Returns:
            The device credential dictionary if found, None otherwise.
        """
        for device in self.tuya_device_credentials:
            if device.get("device_id") == device_id:
                return device
        return None

    def get_device_credentials(
        self, device_id: Optional[str] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, Any], None]:
        """
        Get Tuya credentials for a specific device or all devices.

        Args:
            device_id: Optional device ID to filter by. If None, returns all devices.

        Returns:
            If device_id is provided: A single device credential dict or None if not found.
            If device_id is None: List of all device credentials.
        """
        if device_id is None:
            return self.tuya_device_credentials

        return self._find_device_credential(device_id)

    @validate_device_id
    def get_device_local_key(self, device_id: str) -> Optional[str]:
        """
        Get the local key for a specific device.

        Args:
            device_id: The Tuya device ID.

        Returns:
            The local key string or None if device not found.

        Raises:
            PetsSeriesValidationError: If device_id is invalid.
        """
        device = self._find_device_credential(device_id)
        return device.get("local_key") if device else None

    @validate_device_id
    def get_device_ip(self, device_id: str) -> Optional[str]:
        """
        Get the local IP address for a specific device.

        Args:
            device_id: The Tuya device ID.

        Returns:
            The IP address string or None if device not found or IP unavailable.

        Raises:
            PetsSeriesValidationError: If device_id is invalid.
        """
        device = self._find_device_credential(device_id)
        return device.get("ip") if device else None

    @validate_device_id
    @validate_local_key
    def set_device_credentials(
        self,
        device_id: str,
        local_key: str,
        ip: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        """
        Manually set device credentials (localKey, IP) for a device.

        You can obtain the localKey through other means (e.g., from Tuya IoT Platform,
        tinytuya wizard, or Frida interception).

        Args:
            device_id: The Tuya device ID (same as vendor_id from Philips API).
                       Must be a non-empty string.
            local_key: The device's local encryption key. Must be a non-empty string.
            ip: Optional local IP address of the device (e.g., "192.168.1.100").
            name: Optional device name for easier identification.

        Raises:
            PetsSeriesValidationError: If device_id or local_key is invalid.

        Example:
            >>> client = PetsSeriesClient()
            >>> await client.initialize()
            >>> client.set_device_credentials(
            ...     device_id="",
            ...     local_key="",
            ...     ip="192.168.1.100",
            ...     name="Pet Feeder"
            ... )
        """
        # Check if device already exists
        device = self._find_device_credential(device_id)
        if device:
            device["local_key"] = local_key
            if ip:
                device["ip"] = ip
            if name:
                device["name"] = name
            _LOGGER.info("Updated credentials for device %s", device_id)
            return

        # Add new device
        new_device: Dict[str, Any] = {
            "device_id": device_id,
            "local_key": local_key,
        }
        if ip:
            new_device["ip"] = ip
        if name:
            new_device["name"] = name

        self.tuya_device_credentials.append(new_device)
        _LOGGER.info("Added credentials for device %s", device_id)

    async def ensure_token_valid(self) -> None:
        """
        Ensure the access token is valid, refreshing it if necessary.
        """
        if await self.auth.is_token_expired():
            _LOGGER.info("Access token expired, refreshing...")
            await self.auth.refresh_access_token()
            await self._refresh_headers()

    @handle_api_errors("get user info")
    async def get_user_info(self) -> User:
        """
        Get user information from the UserInfo endpoint.

        Returns:
            User: User information object.

        Raises:
            PetsSeriesAPIError: If the API request fails.
            PetsSeriesNetworkError: If a network error occurs.
        """
        await self.ensure_token_valid()
        session = await self.get_client()
        async with session.get(
            self.config.user_info_url, headers=self.headers
        ) as response:
            response.raise_for_status()
            data = await response.json()
            return User(
                sub=data["sub"],
                name=data["name"],
                given_name=data["given_name"],
                picture=data.get("picture"),
                locale=data.get("locale"),
                email=data["email"],
            )

    @handle_api_errors("get consumer")
    async def get_consumer(self) -> Consumer:
        """
        Get Consumer information from the Consumer endpoint.

        Returns:
            Consumer: Consumer information object.

        Raises:
            PetsSeriesAPIError: If the API request fails.
            PetsSeriesNetworkError: If a network error occurs.
        """
        await self.ensure_token_valid()
        session = await self.get_client()
        async with session.get(
            self.config.consumer_url, headers=self.headers
        ) as response:
            response.raise_for_status()
            data = await response.json()
            # New consumer endpoint returns additional fields
            consumer = Consumer(
                id=str(data.get("id", "")),
                country_code=str(data.get("countryCode", "")),
                url=str(data.get("url", "")),
            )
            consumer.language = data.get("language")
            consumer.identities = data.get("identities")
            consumer.identities_url = data.get("identitiesUrl")
            consumer.installations = data.get("installations")
            consumer.installations_url = data.get("installationsUrl")
            return consumer

    @handle_api_errors("get homes")
    async def get_homes(self) -> list[Home]:
        """
        Get available homes for the user.

        Returns:
            list[Home]: List of Home objects.

        Raises:
            PetsSeriesAPIError: If the API request fails.
            PetsSeriesNetworkError: If a network error occurs.
        """
        await self.ensure_token_valid()
        session = await self.get_client()
        async with session.get(self.config.homes_url, headers=self.headers) as response:
            response.raise_for_status()
            homes_data = await response.json()
            items = homes_data.get(
                "item", homes_data if isinstance(homes_data, list) else []
            )
            homes: list[Home] = []
            for h in items:
                home = Home(
                    id=str(h.get("id", "")),
                    name=str(h.get("name", "")),
                    shared=bool(h.get("shared", False)),
                    number_of_devices=int(h.get("numberOfDevices", 0)),
                    external_id=str(h.get("externalId", "")),
                    number_of_activities=int(h.get("numberOfActivities", 0)),
                )
                home.url = str(h.get("url", home.url))
                home.devices_url = str(h.get("devicesUrl", home.devices_url))
                home.events_url = str(h.get("eventsUrl", home.events_url))
                home.invites_url = str(h.get("invitesUrl", home.invites_url))
                home.time_zone = h.get("timeZone", home.time_zone)
                home.active_mode = h.get("activeMode", home.active_mode)
                home.modes = h.get("modes", home.modes)
                home.members = h.get("members", home.members)
                home.vendor_ids = h.get("vendorIds", home.vendor_ids)
                homes.append(home)
            return homes

    @handle_api_errors("get devices")
    async def get_devices(self, home: Home) -> list[Device]:
        """
        Get devices for the selected home.

        Args:
            home: The Home object to get devices for.

        Returns:
            list[Device]: List of Device objects.

        Raises:
            PetsSeriesAPIError: If the API request fails.
            PetsSeriesNetworkError: If a network error occurs.
        """
        await self.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/devices"
        session = await self.get_client()
        async with session.get(url, headers=self.headers) as response:
            response.raise_for_status()
            devices_data = await response.json()
            devices: list[Device] = []
            for d in devices_data.get("item", []):
                device = Device(
                    id=str(d.get("id", "")),
                    name=str(d.get("name", "")),
                    product_ctn=d.get("productCtn"),
                    product_id=d.get("productId"),
                    vendor_id=d.get("vendorId"),
                    external_id=d.get("externalId"),
                    url=str(d.get("url", "")),
                    settings_url=str(d.get("settingsUrl", "")),
                    subscription_url=d.get("subscriptionUrl"),
                )
                devices.append(device)
            return devices

    @handle_api_errors("get mode devices")
    async def get_mode_devices(self, home: Home) -> list[ModeDevice]:
        """
        Get mode devices for the selected home.

        Args:
            home: The Home object to get mode devices for.

        Returns:
            list[ModeDevice]: List of ModeDevice objects.

        Raises:
            PetsSeriesAPIError: If the API request fails.
            PetsSeriesNetworkError: If a network error occurs.
        """
        await self.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/modes/home/devices"
        session = await self.get_client()
        async with session.get(url, headers=self.headers) as response:
            response.raise_for_status()
            mode_devices_data = await response.json()
            mode_devices = [
                ModeDevice(id=md["id"], name=md["name"], settings=md["settings"])
                for md in mode_devices_data.get("item", [])
            ]
            return mode_devices

    @handle_api_errors("update device settings")
    async def update_device_settings(
        self, home: Home, device_id: str, settings: dict
    ) -> bool:
        """
        Update the settings for a device.

        Args:
            home: The Home object containing the device.
            device_id: The device ID to update.
            settings: Dictionary of settings to update.

        Returns:
            bool: True if update was successful (HTTP 204), False otherwise.

        Raises:
            PetsSeriesAPIError: If the API request fails.
            PetsSeriesNetworkError: If a network error occurs.
        """
        await self.ensure_token_valid()
        url = (
            f"{self.config.base_url}/api/homes/{home.id}/modes/home/devices/{device_id}"
        )

        headers = {
            **self.headers,
            "Content-Type": "application/json; charset=UTF-8",
        }

        payload = {"settings": settings}
        session = await self.get_client()
        async with session.patch(url, headers=headers, json=payload) as response:
            if response.status == HTTPStatus.NO_CONTENT:
                _LOGGER.info("Device %s settings updated successfully.", device_id)
                return True

            text = await response.text()
            _LOGGER.error("Failed to update device settings: %s", text)
            response.raise_for_status()
        return False

    @handle_api_errors("get device settings")
    async def get_settings(self, home: Home, device_id: str) -> dict:
        """
        Get the settings for a device.

        Args:
            home: The Home object containing the device.
            device_id: The device ID to get settings for.

        Returns:
            dict: Simplified settings dictionary.

        Raises:
            PetsSeriesValidationError: If device is not found.
            PetsSeriesAPIError: If the API request fails.
            PetsSeriesNetworkError: If a network error occurs.
        """
        mode_devices = await self.get_mode_devices(home)
        for md in mode_devices:
            if md.id == device_id:
                simplified_settings = {
                    key: value["value"] for key, value in md.settings.items()
                }
                _LOGGER.debug(
                    "Simplified settings for device %s: %s",
                    device_id,
                    simplified_settings,
                )
                return simplified_settings
        _LOGGER.warning("No settings found for device %s", device_id)
        raise PetsSeriesValidationError(f"Device with ID {device_id} not found")

    async def power_off_device(self, home: Home, device_id: str) -> bool:
        """
        Power off a device.
        """
        _LOGGER.info("Powering off device %s", device_id)
        return await self.update_device_settings(
            home, device_id, {"device_active": {"value": False}}
        )

    async def power_on_device(self, home: Home, device_id: str) -> bool:
        """
        Power on a device.
        """
        _LOGGER.info("Powering on device %s", device_id)
        return await self.update_device_settings(
            home, device_id, {"device_active": {"value": True}}
        )

    async def disable_motion_notifications(self, home: Home, device_id: str) -> bool:
        """
        Disable motion notifications for a device.
        """
        _LOGGER.info("Disabling motion notifications for device %s", device_id)
        return await self.update_device_settings(
            home, device_id, {"push_notification_motion": {"value": False}}
        )

    async def enable_motion_notifications(self, home: Home, device_id: str) -> bool:
        """
        Enable motion notifications for a device.
        """
        _LOGGER.info("Enabling motion notifications for device %s", device_id)
        return await self.update_device_settings(
            home, device_id, {"push_notification_motion": {"value": True}}
        )

    async def toggle_motion_notifications(self, home: Home, device_id: str) -> bool:
        """
        Toggle motion notifications for a device.

        Args:
            home: The Home object containing the device.
            device_id: The device ID to toggle notifications for.

        Returns:
            bool: True if successful, False if device not found.

        Raises:
            PetsSeriesAPIError: If the API request fails.
            PetsSeriesNetworkError: If a network error occurs.
        """
        try:
            current_settings = await self.get_settings(home, device_id)
        except PetsSeriesValidationError as e:
            _LOGGER.error("Device not found: %s", e)
            return False
        new_value = not current_settings.get("push_notification_motion", False)
        _LOGGER.info(
            "Toggling motion notifications for device %s to %s", device_id, new_value
        )
        return await self.update_device_settings(
            home, device_id, {"push_notification_motion": {"value": new_value}}
        )

    async def toggle_device_power(self, home: Home, device_id: str) -> bool:
        """
        Toggle the power state of a device.

        Args:
            home: The Home object containing the device.
            device_id: The device ID to toggle power for.

        Returns:
            bool: True if successful, False if device not found.

        Raises:
            PetsSeriesAPIError: If the API request fails.
            PetsSeriesNetworkError: If a network error occurs.
        """
        try:
            current_settings = await self.get_settings(home, device_id)
        except PetsSeriesValidationError as e:
            _LOGGER.error("Device not found: %s", e)
            return False
        new_value = not current_settings.get("device_active", False)
        _LOGGER.info("Toggling power for device %s to %s", device_id, new_value)
        return await self.update_device_settings(
            home, device_id, {"device_active": {"value": new_value}}
        )

    async def __aenter__(self):
        await self.get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # Tuya methods
    def get_tuya_status(self) -> Optional[Dict[str, Any]]:
        """
        Get the status of the Tuya device.

        Returns:
            Optional[Dict[str, Any]]:
                The Tuya device status if TuyaClient is initialized, else None.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.get_status()
            except TuyaError as e:
                _LOGGER.error("Failed to get Tuya device status: %s", e)
                return None
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return None

    def set_tuya_value(self, dp_code: str, value: Any) -> bool:
        """
        Set a value on the Tuya device.

        Args:
            dp_code (str): The DP code to set.
            value (Any): The value to set.

        Returns:
            bool: True if successful, False otherwise.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.set_value(dp_code, value)
            except TuyaError as e:
                _LOGGER.error("Failed to set Tuya device value: %s", e)
                return False
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return False

    def toggle_tuya_switch(self, dp_code: str) -> bool:
        """
        Toggle a boolean switch on the Tuya device.

        Args:
            dp_code (str): The DP code to toggle.

        Returns:
            bool: True if successful, False otherwise.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.toggle_switch(dp_code)
            except TuyaError as e:
                _LOGGER.error("Failed to toggle Tuya device switch: %s", e)
                return False
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return False

    def set_flip(self) -> bool:
        """
        Flip the basic switch on the Tuya device.

        Returns:
            bool: True if successful, False otherwise.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.toggle_switch("flip")
            except TuyaError as e:
                _LOGGER.error("Failed to flip the Tuya device switch: %s", e)
                return False
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return False

    def get_flip(self) -> Optional[Dict[str, Any]]:
        """
        Get the status of the Tuya device.

        Returns:
            Optional[Dict[str, Any]]: The Tuya device status if TuyaClient is initialized, else None.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.get_value("flip")
            except TuyaError as e:
                _LOGGER.error("Failed to get Tuya device status: %s", e)
                return None
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return None

    def set_osd(self) -> bool:
        """
        Flip the OSD switch on the Tuya device.

        Returns:
            bool: True if successful, False otherwise.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.toggle_switch("osd")
            except TuyaError as e:
                _LOGGER.error("Failed to flip the Tuya device switch: %s", e)
                return False
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return False

    def get_osd(self) -> Optional[Dict[str, Any]]:
        """
        Get the OSD status of the Tuya device.

        Returns:
            Optional[Dict[str, Any]]: The Tuya device status if TuyaClient is initialized, else None.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.get_value("osd")
            except TuyaError as e:
                _LOGGER.error("Failed to get Tuya device status: %s", e)
                return None
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return None

    def set_private(self) -> bool:
        """
        Flip the private switch on the Tuya device.

        Returns:
            bool: True if successful, False otherwise.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.toggle_switch("private")
            except TuyaError as e:
                _LOGGER.error("Failed to flip the Tuya device switch: %s", e)
                return False
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return False

    def get_private(self) -> Optional[Dict[str, Any]]:
        """
        Get the private status of the Tuya device.

        Returns:
            Optional[Dict[str, Any]]: The Tuya device status if TuyaClient is initialized, else None.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.get_value("private")
            except TuyaError as e:
                _LOGGER.error("Failed to get Tuya device status: %s", e)
                return None
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return None

    def set_motion_sensitivity(self, value: str) -> bool:
        """
        Set the motion sensitivity on the Tuya device.
        [0, 1, 2]

        Returns:
            bool: True if successful, False otherwise.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.set_value("motion_sensitivity", value)
            except TuyaError as e:
                _LOGGER.error("Failed to set the Tuya device value: %s", e)
                return False
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return False

    def get_motion_sensitivity(self) -> Optional[Dict[str, Any]]:
        """
        Get the motion sensitivity status of the Tuya device.

        Returns:
            Optional[Dict[str, Any]]:
                The Tuya device status if TuyaClient is initialized, else None.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.get_value("motion_sensitivity")
            except TuyaError as e:
                _LOGGER.error("Failed to get Tuya device status: %s", e)
                return None
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return None

    def set_nightvision_level(self, value: str) -> bool:
        """
        Set the night vision level on the Tuya device.
        [0, 1, 2]

        Returns:
            bool: True if successful, False otherwise.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.set_value("nightvision", value)
            except TuyaError as e:
                _LOGGER.error("Failed to set the Tuya device value: %s", e)
                return False
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return False

    def get_nightvision_level(self) -> Optional[Dict[str, Any]]:
        """
        Get the night vision level status of the Tuya device.

        Returns:
            Optional[Dict[str, Any]]: The Tuya device status if TuyaClient is initialized, else None.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.get_value("nightvision")
            except TuyaError as e:
                _LOGGER.error("Failed to get Tuya device status: %s", e)
                return None
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return None

    def set_motion_switch(self) -> bool:
        """
        Flip the motion switch on the Tuya device.

        Returns:
            bool: True if successful, False otherwise.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.toggle_switch("motion_switch")
            except TuyaError as e:
                _LOGGER.error("Failed to flip the Tuya device switch: %s", e)
                return False
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return False

    def get_motion_switch(self) -> Optional[Dict[str, Any]]:
        """
        Get the motion switch status of the Tuya device.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.get_value("motion_switch")
            except TuyaError as e:
                _LOGGER.error("Failed to get Tuya device status: %s", e)
                return None
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return None

    def set_anti_flicker_level(self, value: str) -> bool:
        """
        Set the anti-flicker level on the Tuya device.
        [0, 1, 2]
        """
        if self.tuya_client:
            try:
                return self.tuya_client.set_value("anti_flicker", value)
            except TuyaError as e:
                _LOGGER.error("Failed to set the Tuya device value: %s", e)
                return False
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return False

    def get_anti_flicker_level(self) -> Optional[Dict[str, Any]]:
        """
        Get the anti-flicker level status of the Tuya device.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.get_value("anti_flicker")
            except TuyaError as e:
                _LOGGER.error("Failed to get Tuya device status: %s", e)
                return None
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return None

    def feed_num(self, value: int) -> bool:
        """
        Feed the specified number of times.
        0 - 20
        """
        if self.tuya_client:
            try:
                return self.tuya_client.set_value("feed_num", value)
            except TuyaError as e:
                _LOGGER.error("Failed to set the Tuya device value: %s", e)
                return False
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return False

    def set_device_volume(self, value: int) -> bool:
        """
        Set the device volume on the Tuya device.
        1 - 100
        """
        if self.tuya_client:
            try:
                return self.tuya_client.set_value("device_volume", value)
            except TuyaError as e:
                _LOGGER.error("Failed to set the Tuya device value: %s", e)
                return False
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return False

    def get_device_volume(self) -> Optional[Dict[str, Any]]:
        """
        Get the device volume status of the Tuya device.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.get_value("device_volume")
            except TuyaError as e:
                _LOGGER.error("Failed to get Tuya device status: %s", e)
                return None
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return None

    def feed_abnormal(self, value: int) -> bool:
        """
        Set the feed abnormal value on the Tuya device.
        0 - 255
        """
        if self.tuya_client:
            try:
                return self.tuya_client.set_value("feed_abnormal", value)
            except TuyaError as e:
                _LOGGER.error("Failed to set the Tuya device value: %s", e)
                return False
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return False

    def set_food_weight(self, value: int) -> bool:
        """
        Set the food weight on the Tuya device.
        0 - 100
        """
        if self.tuya_client:
            try:
                return self.tuya_client.set_value("food_weight", value)
            except TuyaError as e:
                _LOGGER.error("Failed to set the Tuya device value: %s", e)
                return False
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return False

    def get_food_weight(self) -> Optional[Dict[str, Any]]:
        """
        Get the food weight status of the Tuya device.
        """
        if self.tuya_client:
            try:
                return self.tuya_client.get_value("food_weight")
            except TuyaError as e:
                _LOGGER.error("Failed to get Tuya device status: %s", e)
                return None
        else:
            _LOGGER.warning("TuyaClient is not initialized.")
            return None
