# tuya.py

"""
Tuya integration for the PetsSeries client.

This module provides the TuyaClient class, which allows interaction with Tuya devices
using the TinyTuya library. It interprets device status based on predefined DP codes.
"""

import logging
from typing import Dict, Any, Optional
from .dp_codes import DP_CODES

try:
    import tinytuya
except ImportError:
    tinytuya = None

_LOGGER = logging.getLogger(__name__)


class TuyaError(Exception):
    """Custom exception for Tuya-related errors."""

    def __init__(self, message: str):
        super().__init__(message)


class TuyaClient:
    """
    Client for interacting with Tuya devices using TinyTuya.

    Attributes:
        client_id (str): The Tuya client ID.
        ip (str): The IP address of the Tuya device.
        local_key (str): The local key for the Tuya device.
        version (float): The Tuya device protocol version.
    """

    def __init__(self, client_id: str, ip: str, local_key: str, version: float = 3.4):
        """
        Initialize the TuyaClient.

        Args:
            client_id (str): The Tuya client ID.
            ip (str): The IP address of the Tuya device.
            local_key (str): The local key for the Tuya device.
            version (float, optional): The Tuya device protocol version. Defaults to 3.4.

        Raises:
            ImportError: If TinyTuya is not installed.
            TuyaError: If initialization fails.
        """
        if tinytuya is None:
            raise ImportError(
                "TinyTuya is not installed. Install it using 'pip install tinytuya'."
            )
        self.device = tinytuya.Device(client_id, ip, local_key, version=version)
        self.device.set_version(version)
        self.dp_codes = DP_CODES
        _LOGGER.info("Initialized Tuya device with IP: %s", ip)

    def get_status(self) -> Dict[str, Any]:
        """
        Retrieve the current status of the Tuya device.

        Returns:
            Dict[str, Any]: The device status with interpreted DP codes.

        Raises:
            TuyaError: If retrieving status fails.
        """
        try:
            status = self.device.status()
            interpreted_status = self._interpret_status(status.get("dps", {}))
            _LOGGER.debug("Tuya device status: %s", interpreted_status)
            return interpreted_status
        except Exception as e:
            _LOGGER.error("Failed to get Tuya device status: %s", e)
            raise TuyaError(f"Failed to get Tuya device status: {e}") from e

    def _interpret_status(self, dps: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interpret the raw DPS status from the Tuya device.

        Args:
            dps (Dict[str, Any]): The raw DPS status.

        Returns:
            Dict[str, Any]: The interpreted status with meaningful keys.
        """
        interpreted = {}
        for dp_id, value in dps.items():
            dp_info = self.dp_codes.get(dp_id)
            if dp_info:
                key = dp_info["dpCode"]
                interpreted[key] = value
            else:
                interpreted[dp_id] = value  # Unknown DP code
        return interpreted

    def set_value(self, dp_code: str, value: Any) -> bool:
        """
        Set a value for a specific DP code on the Tuya device.

        Args:
            dp_code (str): The DP code to set.
            value (Any): The value to set.

        Returns:
            bool: True if the operation was successful, False otherwise.

        Raises:
            TuyaError: If setting the value fails.
        """
        dp_id = self._get_dp_id(dp_code)
        if not dp_id:
            _LOGGER.error("DP code '%s' not recognized.", dp_code)
            raise TuyaError(f"DP code '{dp_code}' not recognized.")

        try:
            # if enum check if value is valid, or if it has a value range
            dp_info = self.dp_codes.get(dp_id)
            if dp_info["standardType"] == "Enum":
                if value not in dp_info["valueRange"]:
                    _LOGGER.error(
                        "Invalid value '%s' for DP code '%s'.", value, dp_code
                    )
                    raise TuyaError(f"Invalid value '{value}' for DP code '{dp_code}'.")

            elif dp_info["standardType"] == "Integer":
                if not isinstance(value, int):
                    _LOGGER.error(
                        "Value '%s' for DP code '%s' is not an Integer.", value, dp_code
                    )
                    raise TuyaError(
                        f"Value '{value}' for DP code '{dp_code}' is not an Integer."
                    )
                if (
                    "min" in dp_info["properties"]
                    and value < dp_info["properties"]["min"]
                ):
                    _LOGGER.error(
                        "Value '%s' for DP code '%s' is below minimum.", value, dp_code
                    )
                    raise TuyaError(
                        f"Value '{value}' for DP code '{dp_code}' is below minimum."
                    )
                if (
                    "max" in dp_info["properties"]
                    and value > dp_info["properties"]["max"]
                ):
                    _LOGGER.error(
                        "Value '%s' for DP code '%s' is above maximum.", value, dp_code
                    )
                    raise TuyaError(
                        f"Value '{value}' for DP code '{dp_code}' is above maximum."
                    )

            elif dp_info["standardType"] == "Boolean":
                if not isinstance(value, bool):
                    _LOGGER.error(
                        "Value '%s' for DP code '%s' is not a Boolean.", value, dp_code
                    )
                    raise TuyaError(
                        f"Value '{value}' for DP code '{dp_code}' is not a Boolean."
                    )

            self.device.set_value(dp_id, value)
            _LOGGER.info("Set DP code '%s' to '%s'.", dp_code, value)
            return True
        except Exception as e:
            _LOGGER.error("Failed to set DP code '%s': %s", dp_code, e)
            raise TuyaError(f"Failed to set DP code '{dp_code}': {e}") from e

    def get_value(self, dp_code: str) -> Optional[Any]:
        """
        Get the value of a specific DP code on the Tuya device.

        Args:
            dp_code (str): The DP code to get.

        Returns:
            Optional[Any]: The value if found, else None.

        Raises:
            TuyaError: If getting the value fails.
        """
        dp_id = self._get_dp_id(dp_code)
        if not dp_id:
            _LOGGER.error("DP code '%s' not recognized.", dp_code)
            raise TuyaError(f"DP code '{dp_code}' not recognized.")

        try:
            status = self.device.status()
            value = status.get("dps", {}).get(dp_id)
            if value is not None:
                _LOGGER.info("Got value '%s' for DP code '%s'.", value, dp_code)
                return value
            else:
                _LOGGER.error("Value not found for DP code '%s'.", dp_code)
                return None
        except Exception as e:
            _LOGGER.error("Failed to get value for DP code '%s': %s", dp_code, e)
            raise TuyaError(f"Failed to get value for DP code '{dp_code}': {e}") from e

    def _get_dp_id(self, dp_code: str) -> Optional[str]:
        """
        Get the DP ID corresponding to a DP code.

        Args:
            dp_code (str): The DP code.

        Returns:
            Optional[str]: The DP ID if found, else None.
        """
        for dp_id, info in self.dp_codes.items():
            if info["dpCode"] == dp_code:
                return dp_id
        return None

    def toggle_switch(self, dp_code: str) -> bool:
        """
        Toggle a boolean switch DP code.

        Args:
            dp_code (str): The DP code to toggle.

        Returns:
            bool: True if toggled successfully, False otherwise.

        Raises:
            TuyaError: If toggling fails or DP code is not Boolean.
        """
        dp_id = self._get_dp_id(dp_code)
        if not dp_id:
            _LOGGER.error("DP code '%s' not recognized.", dp_code)
            raise TuyaError(f"DP code '{dp_code}' not recognized.")

        dp_info = self.dp_codes.get(dp_id)
        if dp_info["standardType"] != "Boolean":
            _LOGGER.error("DP code '%s' is not a Boolean type.", dp_code)
            raise TuyaError(f"DP code '{dp_code}' is not a Boolean type.")

        current_status = self.get_status()
        current_value = current_status.get(dp_code)
        if not isinstance(current_value, bool):
            _LOGGER.error("Current value for DP code '%s' is not Boolean.", dp_code)
            raise TuyaError(f"Current value for DP code '{dp_code}' is not Boolean.")

        new_value = not current_value
        return self.set_value(dp_code, new_value)
