# devices.py

"""
DevicesManager module for handling device-related operations in the PetsSeriesClient.

This module provides functionality for:
- Device management (add, rename, delete)
- Device settings retrieval and updates
"""

import logging
from typing import Optional

import aiohttp  # type: ignore[import-not-found]

from .config import Config
from .models import Device, DeviceSettings, Home

_LOGGER = logging.getLogger(__name__)


class DevicesManager:
    """
    Manager class for handling device-related operations.
    """

    def __init__(self, client):
        """
        Initialize the DevicesManager with a reference to the PetsSeriesClient.

        Args:
            client (PetsSeriesClient): The main API client.
        """
        self.client = client
        self.config = Config()

    async def add_device(self, home: Home, product_ctn: str) -> bool:
        """
        Add a new device to a home.

        Args:
            home (Home): The home to add the device to.
            product_ctn (str): Product CTN (e.g., "PAW5320").

        Returns:
            bool: True if successful.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/devices"
        payload = {"productCtn": product_ctn}

        session = await self.client.get_client()
        try:
            headers = {
                **self.client.headers,
                "Content-Type": "application/json; charset=UTF-8",
            }
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status in (200, 201, 204):
                    _LOGGER.info(
                        "Device with CTN %s added to home %s", product_ctn, home.id
                    )
                    return True

                text = await response.text()
                _LOGGER.error("Failed to add device: %s %s", response.status, text)
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to add device: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in add_device: %s", e)
            raise
        return False

    async def rename_device(
        self, home: Home, device: Device, new_name: str
    ) -> bool:
        """
        Rename an existing device.

        Args:
            home (Home): The home the device belongs to.
            device (Device): The device to rename.
            new_name (str): New name for the device.

        Returns:
            bool: True if successful.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/devices/{device.id}"
        payload = {"name": new_name}

        session = await self.client.get_client()
        try:
            headers = {
                **self.client.headers,
                "Content-Type": "application/json; charset=UTF-8",
            }
            async with session.patch(url, headers=headers, json=payload) as response:
                if response.status in (200, 204):
                    _LOGGER.info("Device %s renamed to: %s", device.id, new_name)
                    return True

                text = await response.text()
                _LOGGER.error("Failed to rename device: %s %s", response.status, text)
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to rename device: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in rename_device: %s", e)
            raise
        return False

    async def delete_device(self, home: Home, device: Device) -> bool:
        """
        Remove/unpair a device from a home.

        Args:
            home (Home): The home the device belongs to.
            device (Device): The device to remove.

        Returns:
            bool: True if successful.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/devices/{device.id}"

        session = await self.client.get_client()
        try:
            async with session.delete(url, headers=self.client.headers) as response:
                if response.status == 204:
                    _LOGGER.info(
                        "Device %s removed from home %s", device.id, home.id
                    )
                    return True

                text = await response.text()
                _LOGGER.error("Failed to delete device: %s %s", response.status, text)
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to delete device: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in delete_device: %s", e)
            raise
        return False

    async def get_device_settings(
        self, home: Home, device: Device
    ) -> DeviceSettings:
        """
        Get detailed settings for a device.

        Args:
            home (Home): The home the device belongs to.
            device (Device): The device to get settings for.

        Returns:
            DeviceSettings: The device settings.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/devices/{device.id}/settings"

        session = await self.client.get_client()
        try:
            async with session.get(url, headers=self.client.headers) as response:
                response.raise_for_status()
                data = await response.json()
                settings = DeviceSettings.from_dict(data)
                _LOGGER.info("Retrieved settings for device %s", device.id)
                return settings
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to get device settings: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in get_device_settings: %s", e)
            raise

    async def update_device_settings(
        self,
        home: Home,
        device: Device,
        filter_application_time: Optional[str] = None,
        feeder_voice_audio_id: Optional[str] = None,
    ) -> bool:
        """
        Update device settings.

        Args:
            home (Home): The home the device belongs to.
            device (Device): The device to update settings for.
            filter_application_time (Optional[str]): New filter application time (ISO 8601).
            feeder_voice_audio_id (Optional[str]): Audio ID for feeder voice.

        Returns:
            bool: True if successful.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/devices/{device.id}/settings"

        payload = {}
        if filter_application_time is not None:
            payload["filter_application_time"] = {
                "type": "fountain",
                "value": filter_application_time,
            }
        if feeder_voice_audio_id is not None:
            payload["feeder_voice_audio_id"] = {
                "audioId": feeder_voice_audio_id,
            }

        if not payload:
            _LOGGER.warning("No settings provided to update")
            return False

        session = await self.client.get_client()
        try:
            headers = {
                **self.client.headers,
                "Content-Type": "application/json; charset=UTF-8",
            }
            async with session.patch(url, headers=headers, json=payload) as response:
                if response.status in (200, 204):
                    _LOGGER.info("Device %s settings updated", device.id)
                    return True

                text = await response.text()
                _LOGGER.error(
                    "Failed to update device settings: %s %s", response.status, text
                )
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

    async def reset_filter(self, home: Home, device: Device) -> bool:
        """
        Reset the filter replacement timer for a fountain device.

        This sets the filter application time to now, effectively resetting
        the countdown for filter replacement.

        Args:
            home (Home): The home the device belongs to.
            device (Device): The device to reset the filter for.

        Returns:
            bool: True if successful.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        return await self.update_device_settings(
            home, device, filter_application_time=now
        )
