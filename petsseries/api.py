"""
API client for interacting with the PetsSeries backend services.

This module provides the PetsSeriesClient class, which handles authentication,
data retrieval, and device management for the PetsSeries application.
"""

import logging
from typing import Any, Dict, Optional

import aiohttp  # type: ignore[import-not-found]

from .auth import AuthManager
from .config import Config
from .events import EventsManager

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

# Optional import for Tuya
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
    ):
        self.auth = AuthManager(token_file, access_token, refresh_token)
        self.session = None
        self.headers: Dict[str, str] = {}
        self.headers_token: Dict[str, str] = {}
        self.timeout = aiohttp.ClientTimeout(total=10.0)
        self.config = Config()
        self.tuya_client: Optional[TuyaClient] = None  # type: ignore
        self.meals = MealsManager(self)
        self.events = EventsManager(self)

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
                    version=float(tuya_credentials.get("version", 3.4)),
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
            "User-Agent": "UnofficialPetsSeriesClient/1.0",
        }
        self.headers_token = {
            "Accept-Encoding": "gzip",
            "Accept": "application/json",
            "Connection": "keep-alive",
            "Host": "cdc.accounts.home.id",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 14)",
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

    async def ensure_token_valid(self) -> None:
        """
        Ensure the access token is valid, refreshing it if necessary.
        """
        if await self.auth.is_token_expired():
            _LOGGER.info("Access token expired, refreshing...")
            await self.auth.refresh_access_token()
            await self._refresh_headers()

    async def get_user_info(self) -> User:
        """
        Get user information from the UserInfo endpoint.
        """
        await self.ensure_token_valid()
        session = await self.get_client()
        try:
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
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to get user info: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in get_user_info: %s", e)
            raise

    async def get_consumer(self) -> Consumer:
        """
        Get Consumer information from the Consumer endpoint.
        """
        await self.ensure_token_valid()
        session = await self.get_client()
        try:
            async with session.get(
                self.config.consumer_url, headers=self.headers
            ) as response:
                response.raise_for_status()
                data = await response.json()
                # New consumer endpoint observed returns: id, identities, installations, url, identitiesUrl, installationsUrl, language
                # countryCode may be absent; set to empty string if missing for backward compatibility
                return Consumer(
                    id=str(data.get("id", "")),
                    country_code=str(data.get("countryCode", "")),
                    url=str(data.get("url", "")),
                )
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to get Consumer: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in get_consumer: %s", e)
            raise

    async def get_homes(self) -> list[Home]:
        """
        Get available homes for the user.
        """
        await self.ensure_token_valid()
        session = await self.get_client()
        try:
            async with session.get(
                self.config.homes_url, headers=self.headers
            ) as response:
                response.raise_for_status()
                homes_data = await response.json()
                items = homes_data.get(
                    "item", homes_data if isinstance(homes_data, list) else []
                )
                homes = [
                    Home(
                        id=home.get("id", ""),
                        name=home.get("name", ""),
                        shared=bool(home.get("shared", False)),
                        number_of_devices=int(home.get("numberOfDevices", 0)),
                        external_id=str(home.get("externalId", "")),
                        number_of_activities=int(home.get("numberOfActivities", 0)),
                    )
                    for home in items
                ]
                return homes
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to get homes: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in get_homes: %s", e)
            raise

    async def get_devices(self, home: Home) -> list[Device]:
        """
        Get devices for the selected home.
        """
        await self.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/devices"
        session = await self.get_client()
        try:
            async with session.get(url, headers=self.headers) as response:
                response.raise_for_status()
                devices_data = await response.json()
                devices = [
                    Device(
                        id=device["id"],
                        name=device["name"],
                        product_ctn=device["productCtn"],
                        product_id=device["productId"],
                        external_id=device["externalId"],
                        url=device["url"],
                        settings_url=device["settingsUrl"],
                        subscription_url=device["subscriptionUrl"],
                    )
                    for device in devices_data.get("item", [])
                ]
                return devices
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to get devices: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in get_devices: %s", e)
            raise

    async def get_mode_devices(self, home: Home) -> list[ModeDevice]:
        """
        Get mode devices for the selected home.
        """
        await self.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/modes/home/devices"
        session = await self.get_client()
        try:
            async with session.get(url, headers=self.headers) as response:
                response.raise_for_status()
                mode_devices_data = await response.json()
                mode_devices = [
                    ModeDevice(id=md["id"], name=md["name"], settings=md["settings"])
                    for md in mode_devices_data.get("item", [])
                ]
                return mode_devices
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to get mode devices: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in get_mode_devices: %s", e)
            raise

    async def update_device_settings(
        self, home: Home, device_id: str, settings: dict
    ) -> bool:
        """
        Update the settings for a device.
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
        try:
            async with session.patch(url, headers=headers, json=payload) as response:
                if response.status == 204:
                    _LOGGER.info("Device %s settings updated successfully.", device_id)
                    return True

                text = await response.text()
                _LOGGER.error("Failed to update device settings: %s", text)
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error(
                "Failed to update device settings: %s %s", e.status, e.message
            )
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in update_device_settings: %s", e)
            raise
        return False

    async def get_settings(self, home: Home, device_id: str) -> dict:
        """
        Get the settings for a device.
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
        raise ValueError(f"Device with ID {device_id} not found")

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
        """
        try:
            current_settings = await self.get_settings(home, device_id)
        except ValueError as e:
            _LOGGER.error(e)
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
        """
        try:
            current_settings = await self.get_settings(home, device_id)
        except ValueError as e:
            _LOGGER.error(e)
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
