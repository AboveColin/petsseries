import aiohttp
import urllib.parse
from .auth import AuthManager
from .models import (
    User, Home, Meal, Device, Consumer, ModeDevice,
    MotionEvent, MealDispensedEvent, MealUpcomingEvent,
    Event, FoodLevelLowEvent
)
import logging
import certifi
import ssl
import asyncio

_LOGGER = logging.getLogger(__name__)


class PetsSeriesClient:
    def __init__(self, token_file="tokens.json", access_token=None, refresh_token=None):
        self.auth = AuthManager(token_file, access_token, refresh_token)
        self.session = None
        self.headers = {}
        self.headers_token = {}
        self.timeout = aiohttp.ClientTimeout(total=10.0)
        self.userInfoURL = "https://cdc.accounts.home.id/oidc/op/v1.0/4_JGZWlP8eQHpEqkvQElolbA/userinfo"
        self.consumerURL = "https://nbx-discovery.prod.eu-hs.iot.versuni.com/api/petsseries/consumer"
        self.homesURL = "https://petsseries-backend.prod.eu-hs.iot.versuni.com/api/v1/home-management/available-homes"

    async def _create_ssl_context(self) -> ssl.SSLContext:
        """Create an SSL context using certifi's CA bundle in a separate thread."""
        return await asyncio.to_thread(
            ssl.create_default_context, cafile=certifi.where()
        )

    async def _get_client(self) -> aiohttp.ClientSession:
        """
        Get an aiohttp.ClientSession with certifi's CA bundle.
        """
        if self.session is None:
            ssl_context = await self._create_ssl_context()
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(timeout=self.timeout, connector=connector)
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
        await self.refresh_headers()

    async def refresh_headers(self) -> None:
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
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 14)"
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
            await self.refresh_headers()

    async def get_user_info(self) -> User:
        """
        Get user information from the UserInfo endpoint.
        """
        await self._ensure_token_valid()
        session = await self._get_client()
        try:
            async with session.get(self.userInfoURL, headers=self.headers) as response:
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
            _LOGGER.error(f"Failed to get user info: {e.status} {e.message}")
            raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error in get_user_info: {e}")
            raise

    async def get_Consumer(self) -> Consumer:
        """
        Get Consumer information from the Consumer endpoint.
        """
        await self._ensure_token_valid()
        session = await self._get_client()
        try:
            async with session.get(self.consumerURL, headers=self.headers) as response:
                response.raise_for_status()
                data = await response.json()
                return Consumer(
                    id=data["id"],
                    countryCode=data["countryCode"],
                    url=data["url"]
                )
        except aiohttp.ClientResponseError as e:
            _LOGGER.error(f"Failed to get Consumer: {e.status} {e.message}")
            raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error in get_Consumer: {e}")
            raise

    async def get_homes(self) -> list[Home]:
        """
        Get available homes for the user.
        """
        await self._ensure_token_valid()
        session = await self._get_client()
        try:
            async with session.get(self.homesURL, headers=self.headers) as response:
                response.raise_for_status()
                homes_data = await response.json()
                homes = [
                    Home(
                        id=home["id"],
                        name=home["name"],
                        shared=home["shared"],
                        numberOfDevices=home["numberOfDevices"],
                        externalId=home["externalId"],
                        numberOfActivities=home["numberOfActivities"]
                    )
                    for home in homes_data
                ]
                return homes
        except aiohttp.ClientResponseError as e:
            _LOGGER.error(f"Failed to get homes: {e.status} {e.message}")
            raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error in get_homes: {e}")
            raise

    async def get_meals(self, home) -> list[Meal]:
        """
        Get meals for the selected home.
        """
        await self._ensure_token_valid()
        url = f"https://petsseries-backend.prod.eu-hs.iot.versuni.com/api/homes/{home.id}/meals"
        session = await self._get_client()
        try:
            async with session.get(url, headers=self.headers) as response:
                response.raise_for_status()
                meals_data = await response.json()
                meals = [
                    Meal(
                        id=meal["id"],
                        name=meal["name"],
                        portionAmount=meal["portionAmount"],
                        feedTime=meal["feedTime"],
                        repeatDays=meal["repeatDays"],
                        deviceId=meal["deviceId"],
                        enabled=meal["enabled"],
                        url=meal["url"]
                    )
                    for meal in meals_data.get("item", [])
                ]
                return meals
        except aiohttp.ClientResponseError as e:
            _LOGGER.error(f"Failed to get meals: {e.status} {e.message}")
            raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error in get_meals: {e}")
            raise

    async def get_devices(self, home) -> list[Device]:
        """
        Get devices for the selected home.
        """
        await self._ensure_token_valid()
        url = f"https://petsseries-backend.prod.eu-hs.iot.versuni.com/api/homes/{home.id}/devices"
        session = await self._get_client()
        try:
            async with session.get(url, headers=self.headers) as response:
                response.raise_for_status()
                devices_data = await response.json()
                devices = [
                    Device(
                        id=device["id"],
                        name=device["name"],
                        productCtn=device["productCtn"],
                        productId=device["productId"],
                        externalId=device["externalId"],
                        url=device["url"],
                        settingsUrl=device["settingsUrl"],
                        subscriptionUrl=device["subscriptionUrl"]
                    )
                    for device in devices_data.get("item", [])
                ]
                return devices
        except aiohttp.ClientResponseError as e:
            _LOGGER.error(f"Failed to get devices: {e.status} {e.message}")
            raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error in get_devices: {e}")
            raise

    async def get_mode_devices(self, home) -> list[ModeDevice]:
        """
        Get mode devices for the selected home.
        """
        await self._ensure_token_valid()
        url = f"https://petsseries-backend.prod.eu-hs.iot.versuni.com/api/homes/{home.id}/modes/home/devices"
        session = await self._get_client()
        try:
            async with session.get(url, headers=self.headers) as response:
                response.raise_for_status()
                mode_devices_data = await response.json()
                mode_devices = [
                    ModeDevice(
                        id=md["id"],
                        name=md["name"],
                        settings=md["settings"]
                    )
                    for md in mode_devices_data.get("item", [])
                ]
                return mode_devices
        except aiohttp.ClientResponseError as e:
            _LOGGER.error(f"Failed to get mode devices: {e.status} {e.message}")
            raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error in get_mode_devices: {e}")
            raise

    async def get_events(self, home, from_date, to_date, clustered, types="none") -> list[Event]:
        """
        Get events for the selected home within a date range.
        """
        await self._ensure_token_valid()
        if types not in Event.EventTypes and types != "none":
            raise ValueError(f"Invalid event type '{types}'")
        types_param = f"&types={types}" if types != "none" else ""

        from_date_str = from_date.isoformat()
        to_date_str = to_date.isoformat()

        from_date_encoded = urllib.parse.quote(from_date_str)
        to_date_encoded = urllib.parse.quote(to_date_str)

        url = (
            f"https://petsseries-backend.prod.eu-hs.iot.versuni.com/api/homes/{home.id}/events"
            f"?from={from_date_encoded}&to={to_date_encoded}&clustered={clustered}{types_param}"
        )
        session = await self._get_client()
        try:
            async with session.get(url, headers=self.headers) as response:
                response.raise_for_status()
                events_data = await response.json()
                events = [self.parse_event(event) for event in events_data.get("item", [])]
                return events
        except aiohttp.ClientResponseError as e:
            _LOGGER.error(f"Failed to get events: {e.status} {e.message}")
            raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error in get_events: {e}")
            raise

    def get_event_types(self) -> list[str]:
        """
        Get the available event types.
        """
        return Event.EventTypes

    def parse_event(self, event) -> Event:
        """
        Parse an event dictionary into an Event object.
        """
        event_type = event.get("type")
        if event_type == "motion_detected":
            return MotionEvent(
                id=event.get("id"),
                type=event_type,
                source=event.get("source"),
                time=event.get("time"),
                url=event.get("url"),
                clusterId=event.get("clusterId"),
                metadata=event.get("metadata"),
                thumbnailKey=event.get("thumbnailKey"),
                deviceId=event.get("deviceId"),
                deviceName=event.get("deviceName"),
                thumbnailUrl=event.get("thumbnailUrl"),
                productCtn=event.get("productCtn"),
                deviceExternalId=event.get("deviceExternalId")
            )
        elif event_type == "meal_dispensed":
            return MealDispensedEvent(
                id=event.get("id"),
                type=event_type,
                source=event.get("source"),
                time=event.get("time"),
                url=event.get("url"),
                clusterId=event.get("clusterId"),
                metadata=event.get("metadata"),
                mealName=event.get("mealName"),
                deviceId=event.get("deviceId"),
                mealUrl=event.get("mealUrl"),
                mealAmount=event.get("mealAmount"),
                deviceName=event.get("deviceName"),
                deviceExternalId=event.get("deviceExternalId"),
                productCtn=event.get("productCtn")
            )
        elif event_type == "meal_upcoming":
            return MealUpcomingEvent(
                id=event.get("id"),
                type=event_type,
                source=event.get("source"),
                time=event.get("time"),
                url=event.get("url"),
                clusterId=event.get("clusterId"),
                metadata=event.get("metadata"),
                mealName=event.get("mealName"),
                deviceId=event.get("deviceId"),
                mealUrl=event.get("mealUrl"),
                mealAmount=event.get("mealAmount"),
                deviceName=event.get("deviceName"),
                deviceExternalId=event.get("deviceExternalId"),
                productCtn=event.get("productCtn")
            )
        elif event_type == "food_level_low":
            return FoodLevelLowEvent(
                id=event.get("id"),
                type=event_type,
                source=event.get("source"),
                time=event.get("time"),
                url=event.get("url"),
                clusterId=event.get("clusterId"),
                metadata=event.get("metadata"),
                deviceId=event.get("deviceId"),
                deviceName=event.get("deviceName"),
                productCtn=event.get("productCtn"),
                deviceExternalId=event.get("deviceExternalId")
            )
        else:
            _LOGGER.warning(f"Unknown event type: {event_type}")
            # Generic event
            return Event(
                id=event["id"],
                type=event_type,
                source=event["source"],
                time=event["time"],
                url=event["url"]
            )

    async def get_event(self, home, event_id) -> Event:
        """
        Get a specific event by ID.
        """
        await self._ensure_token_valid()
        url = f"https://petsseries-backend.prod.eu-hs.iot.versuni.com/api/homes/{home.id}/events/{event_id}"
        session = await self._get_client()
        try:
            async with session.get(url, headers=self.headers) as response:
                response.raise_for_status()
                event_data = await response.json()
                return self.parse_event(event_data)
        except aiohttp.ClientResponseError as e:
            _LOGGER.error(f"Failed to get event {event_id}: {e.status} {e.message}")
            raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error in get_event: {e}")
            raise

    async def update_device_settings(self, home, device_id, settings) -> bool:
        """
        Update the settings for a device.
        """
        await self._ensure_token_valid()
        url = f"https://petsseries-backend.prod.eu-hs.iot.versuni.com/api/homes/{home.id}/modes/home/devices/{device_id}"

        headers = {
            **self.headers,
            "Content-Type": "application/json; charset=UTF-8",
        }

        payload = {"settings": settings}
        session = await self._get_client()
        try:
            async with session.patch(url, headers=headers, json=payload) as response:
                if response.status == 204:
                    _LOGGER.info(f"Device {device_id} settings updated successfully.")
                    return True
                else:
                    text = await response.text()
                    _LOGGER.error(f"Failed to update device settings: {text}")
                    response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error(f"Failed to update device settings: {e.status} {e.message}")
            raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error in update_device_settings: {e}")
            raise
        return False

    async def get_settings(self, home, device_id) -> dict:
        """
        Get the settings for a device.
        """
        mode_devices = await self.get_mode_devices(home)
        for md in mode_devices:
            if md.id == device_id:
                simplified_settings = {key: value["value"] for key, value in md.settings.items()}
                _LOGGER.debug(f"Simplified settings for device {device_id}: {simplified_settings}")
                return simplified_settings
        _LOGGER.warning(f"No settings found for device {device_id}")
        raise ValueError(f"Device with ID {device_id} not found.")

    async def power_off_device(self, home, device_id) -> bool:
        """
        Power off a device.
        """
        _LOGGER.info(f"Powering off device {device_id}")
        return await self.update_device_settings(home, device_id, {"device_active": {"value": False}})

    async def power_on_device(self, home, device_id) -> bool:
        """
        Power on a device.
        """
        _LOGGER.info(f"Powering on device {device_id}")
        return await self.update_device_settings(home, device_id, {"device_active": {"value": True}})

    async def disable_motion_notifications(self, home, device_id) -> bool:
        """
        Disable motion notifications for a device.
        """
        _LOGGER.info(f"Disabling motion notifications for device {device_id}")
        return await self.update_device_settings(home, device_id, {"push_notification_motion": {"value": False}})

    async def enable_motion_notifications(self, home, device_id) -> bool:
        """
        Enable motion notifications for a device.
        """
        _LOGGER.info(f"Enabling motion notifications for device {device_id}")
        return await self.update_device_settings(home, device_id, {"push_notification_motion": {"value": True}})

    async def toggle_motion_notifications(self, home, device_id) -> bool:
        """
        Toggle motion notifications for a device.
        """
        try:
            current_settings = await self.get_settings(home, device_id)
        except ValueError as e:
            _LOGGER.error(e)
            return False
        new_value = not current_settings.get("push_notification_motion", False)
        _LOGGER.info(f"Toggling motion notifications for device {device_id} to {new_value}")
        return await self.update_device_settings(home, device_id, {"push_notification_motion": {"value": new_value}})

    async def toggle_device_power(self, home, device_id) -> bool:
        """
        Toggle the power state of a device.
        """
        try:
            current_settings = await self.get_settings(home, device_id)
        except ValueError as e:
            _LOGGER.error(e)
            return False
        new_value = not current_settings.get("device_active", False)
        _LOGGER.info(f"Toggling power for device {device_id} to {new_value}")
        return await self.update_device_settings(home, device_id, {"device_active": {"value": new_value}})

    async def __aenter__(self):
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
