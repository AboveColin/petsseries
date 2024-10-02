"""
API client for interacting with the PetsSeries backend services.

This module provides the PetsSeriesClient class, which handles authentication,
data retrieval, and device management for the PetsSeries application.
"""

import logging
import urllib.parse

import aiohttp

from .auth import AuthManager
from .models import (
    User,
    Home,
    Meal,
    Device,
    Consumer,
    ModeDevice,
    Event,
    MotionEvent,
    MealDispensedEvent,
    MealUpcomingEvent,
    FoodLevelLowEvent,
    MealEnabledEvent,
    FilterReplacementDueEvent,
    FoodOutletStuckEvent,
    DeviceOfflineEvent,
    DeviceOnlineEvent,
)
from .config import Config
from .session import create_ssl_context

_LOGGER = logging.getLogger(__name__)


class PetsSeriesClient:
    # pylint: disable=too-many-public-methods
    """
    Client for interacting with the PetsSeries API.

    Provides methods to authenticate, retrieve user and device information,
    and manage device settings.
    """

    def __init__(self, token_file="tokens.json", access_token=None, refresh_token=None):
        self.auth = AuthManager(token_file, access_token, refresh_token)
        self.session = None
        self.headers = {}
        self.headers_token = {}
        self.timeout = aiohttp.ClientTimeout(total=10.0)
        self.config = Config()

    async def _get_client(self) -> aiohttp.ClientSession:
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

    async def _ensure_token_valid(self) -> None:
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
        await self._ensure_token_valid()
        session = await self._get_client()
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
        await self._ensure_token_valid()
        session = await self._get_client()
        try:
            async with session.get(
                self.config.consumer_url, headers=self.headers
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return Consumer(
                    id=data["id"], country_code=data["countryCode"], url=data["url"]
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
        await self._ensure_token_valid()
        session = await self._get_client()
        try:
            async with session.get(
                self.config.homes_url, headers=self.headers
            ) as response:
                response.raise_for_status()
                homes_data = await response.json()
                homes = [
                    Home(
                        id=home["id"],
                        name=home["name"],
                        shared=home["shared"],
                        number_of_devices=home["numberOfDevices"],
                        external_id=home["externalId"],
                        number_of_activities=home["numberOfActivities"],
                    )
                    for home in homes_data
                ]
                return homes
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to get homes: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in get_homes: %s", e)
            raise

    async def get_meals(self, home: Home) -> list[Meal]:
        """
        Get meals for the selected home.
        """
        await self._ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/meals"
        session = await self._get_client()
        try:
            async with session.get(url, headers=self.headers) as response:
                response.raise_for_status()
                meals_data = await response.json()
                meals = [
                    Meal(
                        id=meal["id"],
                        name=meal["name"],
                        portion_amount=meal["portionAmount"],
                        feed_time=meal["feedTime"],
                        repeat_days=meal["repeatDays"],
                        device_id=meal["deviceId"],
                        enabled=meal["enabled"],
                        url=meal["url"],
                    )
                    for meal in meals_data.get("item", [])
                ]
                return meals
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to get meals: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in get_meals: %s", e)
            raise

    async def update_meal(self, home: Home, meal: Meal) -> Meal:
        """
        Update an existing meal for the specified home.

        Args:
            home (Home): The home where the meal is located.
            meal (Meal): The Meal object containing updated information. The `id` field must be set.

        Returns:
            Meal: The updated Meal object.

        Raises:
            ValueError: If the meal ID is not provided.
            aiohttp.ClientResponseError: If the HTTP request fails.
            Exception: For any unexpected errors.
        """
        await self._ensure_token_valid()

        if not meal.id:
            raise ValueError("Meal ID must be provided for updating a meal.")

        url = f"{self.config.base_url}/api/homes/{home.id}/meals/{meal.id}"

        # Prepare the payload with updated fields
        payload = {
            "name": meal.name,
            "portionAmount": meal.portion_amount,
            "feedTime": meal.feed_time.isoformat(),
            "repeatDays": meal.repeat_days or [1, 2, 3, 4, 5, 6, 7],
        }

        session = await self._get_client()
        try:
            async with session.patch(
                url, headers=self.headers, json=payload
            ) as response:
                if response.status == 200:
                    updated_data = await response.json()
                    _LOGGER.info("Meal %s updated successfully.", meal.id)
                    return Meal(
                        id=updated_data["id"],
                        name=updated_data["name"],
                        portion_amount=updated_data["portionAmount"],
                        feed_time=updated_data["feedTime"],
                        repeat_days=updated_data.get(
                            "repeatDays", [1, 2, 3, 4, 5, 6, 7]
                        ),
                        device_id=updated_data["deviceId"],
                        enabled=updated_data.get("enabled", True),
                        url=updated_data["url"],
                    )
                text = await response.text()
                _LOGGER.error(
                    "Failed to update meal %s: %s %s", meal.id, response.status, text
                )
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error(
                "Failed to update meal %s: %s %s", meal.id, e.status, e.message
            )
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in update_meal: %s", e)
            raise

    async def create_meal(
        self,
        home: Home,
        meal: Meal,
    ) -> Meal:
        """
        Create a new meal for the specified home and device.

        Args:
            home (Home): The home where the meal will be created.
            meal should contain the following attributes:
                - name: The name of the meal.
                - portion_amount: The amount of food per portion.
                - feed_time: The time the meal should be dispensed.
                - device_id: The ID of the device dispensing the meal.
                - repeat_days: Days of the week to repeat the meal (1=Monday,...,7=Sunday).
        Returns:
            Meal: The created Meal object.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
            Exception: For any unexpected errors.
        """
        await self._ensure_token_valid()
        if meal.repeat_days is None:
            repeat_days = [1, 2, 3, 4, 5, 6, 7]
        else:
            repeat_days = meal.repeat_days

        payload = {
            "deviceId": meal.device_id,
            "feedTime": meal.feed_time.isoformat(),
            "name": meal.name,
            "portionAmount": meal.portion_amount,
            "repeatDays": repeat_days,
        }

        session = await self._get_client()
        try:
            async with session.post(
                f"{self.config.base_url}/api/homes/{home.id}/meals",
                headers=self.headers,
                json=payload,
            ) as response:

                if response.status == 201:
                    location = response.headers.get("Location")
                    if not location:
                        _LOGGER.error("Location header missing in response.")

                    # Extract the meal ID from the Location URL
                    parsed_url = urllib.parse.urlparse(location)
                    meal_id = parsed_url.path.split("/")[-1]

                    _LOGGER.info("Meal created successfully with ID: %s", meal_id)

                    return Meal(
                        id=meal_id,
                        name=meal.name,
                        portion_amount=meal.portion_amount,
                        feed_time=meal.feed_time.isoformat(),
                        repeat_days=repeat_days,
                        device_id=meal.device_id,
                        enabled=True,
                        url=location,
                    )
                text = await response.text()
                _LOGGER.error("Failed to create meal: %s %s", response.status, text)
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to create meal: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in create_meal: %s", e)
            raise

    async def set_meal_enabled(self, home: Home, meal_id: str, enabled: bool) -> bool:
        """
        Enable or disable a specific meal.

        Args:
            home (Home): The home where the meal is located.
            meal_id (str): The ID of the meal to update.
            enabled (bool): The desired enabled state of the meal.

        Returns:
            bool: True if the update was successful, False otherwise.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
            Exception: For any unexpected errors.
        """
        await self._ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/meals/{meal_id}"

        payload = {"enabled": enabled}

        session = await self._get_client()
        try:
            async with session.patch(
                url, headers=self.headers, json=payload
            ) as response:
                if response.status == 204:
                    _LOGGER.info(
                        "Meal %s has been %s successfully.",
                        meal_id,
                        "enabled" if enabled else "disabled",
                    )
                    return True
                text = await response.text()
                _LOGGER.error(
                    "Failed to %s meal %s: %s %s",
                    "enable" if enabled else "disable",
                    meal_id,
                    response.status,
                    text,
                )
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error(
                "HTTP error while trying to %s meal %s: %s %s",
                "enable" if enabled else "disable",
                meal_id,
                e.status,
                e.message,
            )
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in set_meal_enabled: %s", e)
            raise

    async def enable_meal(self, home: Home, meal_id: str) -> bool:
        """
        Enable a specific meal.

        Args:
            home (Home): The home where the meal is located.
            meal_id (str): The ID of the meal to enable.

        Returns:
            bool: True if the meal was enabled successfully, False otherwise.
        """
        return await self.set_meal_enabled(home, meal_id, True)

    async def disable_meal(self, home: Home, meal_id: str) -> bool:
        """
        Disable a specific meal.

        Args:
            home (Home): The home where the meal is located.
            meal_id (str): The ID of the meal to disable.

        Returns:
            bool: True if the meal was disabled successfully, False otherwise.
        """
        return await self.set_meal_enabled(home, meal_id, False)

    async def delete_meal(self, home: Home, meal_id: str) -> bool:
        """
        Delete a specific meal from the selected home.

        Args:
            home (Home): The home from which the meal will be deleted.
            meal_id (str): The ID of the meal to delete.

        Returns:
            bool: True if the meal was deleted successfully, False otherwise.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
            Exception: For any unexpected errors.
        """
        await self._ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/meals/{meal_id}"

        session = await self._get_client()
        try:
            async with session.delete(url, headers=self.headers) as response:
                if response.status == 204:
                    _LOGGER.info(
                        "Meal %s deleted successfully from home %s.", meal_id, home.id
                    )
                    return True
                text = await response.text()
                _LOGGER.error(
                    "Failed to delete meal %s from home %s: %s %s",
                    meal_id,
                    home.id,
                    response.status,
                    text,
                )
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error(
                "HTTP error while trying to delete meal %s from home %s: %s %s",
                meal_id,
                home.id,
                e.status,
                e.message,
            )
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in delete_meal: %s", e)
            raise

    async def get_devices(self, home: Home) -> list[Device]:
        """
        Get devices for the selected home.
        """
        await self._ensure_token_valid()
        url = (
            f"https://petsseries-backend.prod.eu-hs.iot.versuni.com/"
            f"api/homes/{home.id}/devices"
        )
        session = await self._get_client()
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
        await self._ensure_token_valid()
        url = (
            f"https://petsseries-backend.prod.eu-hs.iot.versuni.com/"
            f"api/homes/{home.id}/modes/home/devices"
        )
        session = await self._get_client()
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

    async def get_events(
        self, home: Home, from_date, to_date, types: str = "none"
    ) -> list[Event]:
        """
        Get events for the selected home within a date range.
        """
        clustered = "true"
        await self._ensure_token_valid()
        if types not in Event.get_event_types() and types != "none":
            raise ValueError(f"Invalid event type '{types}'")
        types_param = f"&types={types}" if types != "none" else ""

        from_date_encoded = urllib.parse.quote(from_date.isoformat())
        to_date_encoded = urllib.parse.quote(to_date.isoformat())

        url = (
            f"https://petsseries-backend.prod.eu-hs.iot.versuni.com/"
            f"api/homes/{home.id}/events"
            f"?from={from_date_encoded}&to={to_date_encoded}&clustered={clustered}"
            f"{types_param}"
        )
        session = await self._get_client()
        try:
            async with session.get(url, headers=self.headers) as response:
                response.raise_for_status()
                events_data = await response.json()
                events = [
                    self.parse_event(event) for event in events_data.get("item", [])
                ]
                return events
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to get events: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in get_events: %s", e)
            raise

    def parse_event(self, event: dict) -> Event:
        """
        Parse an event dictionary into an Event object.
        """
        event_type = event.get("type")
        match event_type:
            case "motion_detected":
                return MotionEvent(
                    id=event.get("id"),
                    type=event_type,
                    source=event.get("source"),
                    time=event.get("time"),
                    url=event.get("url"),
                    cluster_id=event.get("clusterId"),
                    metadata=event.get("metadata"),
                    thumbnail_key=event.get("thumbnailKey"),
                    device_id=event.get("deviceId"),
                    device_name=event.get("deviceName"),
                    thumbnail_url=event.get("thumbnailUrl"),
                    product_ctn=event.get("productCtn"),
                    device_external_id=event.get("deviceExternalId"),
                )
            case "meal_dispensed":
                return MealDispensedEvent(
                    id=event.get("id"),
                    type=event_type,
                    source=event.get("source"),
                    time=event.get("time"),
                    url=event.get("url"),
                    cluster_id=event.get("clusterId"),
                    metadata=event.get("metadata"),
                    meal_name=event.get("mealName"),
                    device_id=event.get("deviceId"),
                    meal_url=event.get("mealUrl"),
                    meal_amount=event.get("mealAmount"),
                    device_name=event.get("deviceName"),
                    device_external_id=event.get("deviceExternalId"),
                    product_ctn=event.get("productCtn"),
                )
            case "meal_upcoming":
                return MealUpcomingEvent(
                    id=event.get("id"),
                    type=event_type,
                    source=event.get("source"),
                    time=event.get("time"),
                    url=event.get("url"),
                    cluster_id=event.get("clusterId"),
                    metadata=event.get("metadata"),
                    meal_name=event.get("mealName"),
                    device_id=event.get("deviceId"),
                    meal_url=event.get("mealUrl"),
                    meal_amount=event.get("mealAmount"),
                    device_name=event.get("deviceName"),
                    device_external_id=event.get("deviceExternalId"),
                    product_ctn=event.get("productCtn"),
                )
            case "food_level_low":
                return FoodLevelLowEvent(
                    id=event.get("id"),
                    type=event_type,
                    source=event.get("source"),
                    time=event.get("time"),
                    url=event.get("url"),
                    cluster_id=event.get("clusterId"),
                    metadata=event.get("metadata"),
                    device_id=event.get("deviceId"),
                    device_name=event.get("deviceName"),
                    product_ctn=event.get("productCtn"),
                    device_external_id=event.get("deviceExternalId"),
                )
            case "meal_enabled":
                return MealEnabledEvent(
                    id=event.get("id"),
                    type=event_type,
                    source=event.get("source"),
                    time=event.get("time"),
                    url=event.get("url"),
                    cluster_id=event.get("clusterId"),
                    metadata=event.get("metadata"),
                    meal_amount=event.get("mealAmount"),
                    meal_url=event.get("mealUrl"),
                    device_external_id=event.get("deviceExternalId"),
                    product_ctn=event.get("productCtn"),
                    meal_time=event.get("mealTime"),
                    device_id=event.get("deviceId"),
                    device_name=event.get("deviceName"),
                    meal_repeat_days=event.get("mealRepeatDays"),
                )
            case "filter_replacement_due":
                return FilterReplacementDueEvent(
                    id=event.get("id"),
                    type=event_type,
                    source=event.get("source"),
                    time=event.get("time"),
                    url=event.get("url"),
                    cluster_id=event.get("clusterId"),
                    metadata=event.get("metadata"),
                    device_id=event.get("deviceId"),
                    device_name=event.get("deviceName"),
                    product_ctn=event.get("productCtn"),
                    device_external_id=event.get("deviceExternalId"),
                )
            case "food_outlet_stuck":
                return FoodOutletStuckEvent(
                    id=event.get("id"),
                    type=event_type,
                    source=event.get("source"),
                    time=event.get("time"),
                    url=event.get("url"),
                    cluster_id=event.get("clusterId"),
                    metadata=event.get("metadata"),
                    device_id=event.get("deviceId"),
                    device_name=event.get("deviceName"),
                    product_ctn=event.get("productCtn"),
                    device_external_id=event.get("deviceExternalId"),
                )
            case "device_offline":
                return DeviceOfflineEvent(
                    id=event.get("id"),
                    type=event_type,
                    source=event.get("source"),
                    time=event.get("time"),
                    url=event.get("url"),
                    cluster_id=event.get("clusterId"),
                    metadata=event.get("metadata"),
                    device_id=event.get("deviceId"),
                    device_name=event.get("deviceName"),
                    product_ctn=event.get("productCtn"),
                    device_external_id=event.get("deviceExternalId"),
                )
            case "device_online":
                return DeviceOnlineEvent(
                    id=event.get("id"),
                    type=event_type,
                    source=event.get("source"),
                    time=event.get("time"),
                    url=event.get("url"),
                    cluster_id=event.get("clusterId"),
                    metadata=event.get("metadata"),
                    device_id=event.get("deviceId"),
                    device_name=event.get("deviceName"),
                    product_ctn=event.get("productCtn"),
                    device_external_id=event.get("deviceExternalId"),
                )
            case _:
                _LOGGER.warning("Unknown event type: %s", event_type)
                # Generic event
                return Event(
                    id=event["id"],
                    type=event_type,
                    source=event["source"],
                    time=event["time"],
                    url=event["url"],
                )

    async def get_event(self, home: Home, event_id: str) -> Event:
        """
        Get a specific event by ID.
        """
        await self._ensure_token_valid()
        url = (
            f"https://petsseries-backend.prod.eu-hs.iot.versuni.com/"
            f"api/homes/{home.id}/events/{event_id}"
        )
        session = await self._get_client()
        try:
            async with session.get(url, headers=self.headers) as response:
                response.raise_for_status()
                event_data = await response.json()
                return self.parse_event(event_data)
        except aiohttp.ClientResponseError as e:
            _LOGGER.error(
                "Failed to get event %s: %s %s", event_id, e.status, e.message
            )
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in get_event: %s", e)
            raise

    async def update_device_settings(
        self, home: Home, device_id: str, settings: dict
    ) -> bool:
        """
        Update the settings for a device.
        """
        await self._ensure_token_valid()
        url = (
            f"https://petsseries-backend.prod.eu-hs.iot.versuni.com/"
            f"api/homes/{home.id}/modes/home/devices/{device_id}"
        )

        headers = {
            **self.headers,
            "Content-Type": "application/json; charset=UTF-8",
        }

        payload = {"settings": settings}
        session = await self._get_client()
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
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
