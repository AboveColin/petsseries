# discovery.py

"""
DiscoveryManager module for handling discovery service operations.

This module provides functionality for:
- Fetching global configuration from the discovery service
- No authentication required for these endpoints
"""

import logging
from typing import Optional

import aiohttp  # type: ignore[import-not-found]

from .models import DiscoveryConfig

_LOGGER = logging.getLogger(__name__)

# Discovery service base URL (no authentication required)
DISCOVERY_BASE_URL = "https://discovery.prd.nbx.iot.versuni.com"


class DiscoveryManager:
    """
    Manager class for handling discovery service operations.
    
    The discovery service provides global configuration including:
    - API URLs
    - Supported countries
    - App version requirements
    """

    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        """
        Initialize the DiscoveryManager.

        Args:
            session (Optional[aiohttp.ClientSession]): Optional aiohttp session.
                If not provided, a new session will be created for each request.
        """
        self._session = session
        self._owns_session = False

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None
            self._owns_session = False

    async def get_discovery_config(self) -> DiscoveryConfig:
        """
        Get the global discovery configuration.

        This endpoint does not require authentication.

        Returns:
            DiscoveryConfig: The discovery configuration containing API URLs,
                countries, and app version information.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        url = f"{DISCOVERY_BASE_URL}/.well-known/petseries"

        session = await self._get_session()
        try:
            headers = {
                "Accept": "application/json",
                "User-Agent": "PetsSeries/2.0 (Python)",
            }
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                config = DiscoveryConfig.from_dict(data)
                _LOGGER.info(
                    "Discovery config loaded: API URL = %s", config.api_url
                )
                return config
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to get discovery config: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in get_discovery_config: %s", e)
            raise

    async def get_api_url(self) -> str:
        """
        Get the main API URL from the discovery service.

        Returns:
            str: The main API URL.
        """
        config = await self.get_discovery_config()
        return config.api_url

    async def get_consumer_url(self) -> str:
        """
        Get the consumer API URL from the discovery service.

        Returns:
            str: The consumer API URL.
        """
        config = await self.get_discovery_config()
        return config.consumer_url

    async def __aenter__(self) -> "DiscoveryManager":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()


async def get_discovery_config() -> DiscoveryConfig:
    """
    Convenience function to get discovery config without managing a session.

    Returns:
        DiscoveryConfig: The discovery configuration.
    """
    async with DiscoveryManager() as manager:
        return await manager.get_discovery_config()
