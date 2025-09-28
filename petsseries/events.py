# events.py

"""
EventsManager module for handling event-related operations in the PetsSeriesClient.
"""

import logging
import urllib.parse
from typing import List

import aiohttp  # type: ignore[import-not-found]

from .config import Config
from .models import (
    DeviceOfflineEvent,
    DeviceOnlineEvent,
    Event,
    FilterReplacementDueEvent,
    FoodLevelLowEvent,
    FoodOutletStuckEvent,
    Home,
    MealDispensedEvent,
    MealEnabledEvent,
    MealUpcomingEvent,
    MotionEvent,
)

_LOGGER = logging.getLogger(__name__)


class EventsManager:
    """
    Manager class for handling event-related operations.
    """

    def __init__(self, client):
        """
        Initialize the EventsManager with a reference to the PetsSeriesClient.

        Args:
            client (PetsSeriesClient): The main API client.
        """
        self.client = client
        self.config = Config()

    async def get_events(
        self, home: Home, from_date, to_date, types: str = "none"
    ) -> List[Event]:
        """
        Get events for the selected home within a date range.

        Args:
            home (Home): The home to retrieve events for.
            from_date (datetime): The start date for event retrieval.
            to_date (datetime): The end date for event retrieval.
            types (str): Comma-separated event types to filter by.

        Returns:
            List[Event]: A list of Event objects.

        Raises:
            ValueError: If an invalid event type is provided.
            aiohttp.ClientResponseError: If the HTTP request fails.
            Exception: For any unexpected errors.
        """
        clustered = "true"
        await self.client.ensure_token_valid()
        if types != "none":
            valid_event_types = Event.get_event_types()
            requested_types = set(str(types).split(","))
            requested_types = {et.replace("EventType.", "") for et in requested_types}
            invalid_types = requested_types - {et.name for et in valid_event_types}
            if invalid_types:
                _LOGGER.error("Invalid event types: %s", invalid_types)
                raise ValueError(f"Invalid event types: {invalid_types}")

            # Map event type names to their corresponding values
            types_mapped = [
                str(event_type.value)
                for event_type in valid_event_types
                if event_type.name in requested_types
            ]
            types_param = f"&types={','.join(types_mapped)}" if types_mapped else ""
        else:
            types_param = ""

        from_date_encoded = urllib.parse.quote(from_date.isoformat())
        to_date_encoded = urllib.parse.quote(to_date.isoformat())

        url = (
            f"{self.config.base_url}/api/homes/{home.id}/events"
            f"?from={from_date_encoded}&to={to_date_encoded}&clustered={clustered}"
            f"{types_param}"
        )
        _LOGGER.debug("Getting events from %s", url)
        session = await self.client.get_client()
        try:
            async with session.get(url, headers=self.client.headers) as response:
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

    async def get_event(self, home: Home, event_id: str) -> Event:
        """
        Get a specific event by ID.

        Args:
            home (Home): The home to retrieve the event from.
            event_id (str): The ID of the event to retrieve.

        Returns:
            Event: The retrieved Event object.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
            Exception: For any unexpected errors.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/events/{event_id}"
        session = await self.client.get_client()
        try:
            async with session.get(url, headers=self.client.headers) as response:
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

    def parse_event(self, event: dict) -> Event:
        """
        Parse an event dictionary into an Event object.

        Args:
            event (dict): The event data.

        Returns:
            Event: The parsed Event object.
        """
        event_type = event.get("type")
        match event_type:
            case "motion_detected":
                return MotionEvent(
                    id=str(event.get("id", "")),
                    type=str(event_type),
                    source=str(event.get("source", "")),
                    time=str(event.get("time", "")),
                    url=str(event.get("url", "")),
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
                    id=str(event.get("id", "")),
                    type=str(event_type),
                    source=str(event.get("source", "")),
                    time=str(event.get("time", "")),
                    url=str(event.get("url", "")),
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
                    id=str(event.get("id", "")),
                    type=str(event_type),
                    source=str(event.get("source", "")),
                    time=str(event.get("time", "")),
                    url=str(event.get("url", "")),
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
                    id=str(event.get("id", "")),
                    type=str(event_type),
                    source=str(event.get("source", "")),
                    time=str(event.get("time", "")),
                    url=str(event.get("url", "")),
                    cluster_id=event.get("clusterId"),
                    metadata=event.get("metadata"),
                    device_id=event.get("deviceId"),
                    device_name=event.get("deviceName"),
                    product_ctn=event.get("productCtn"),
                    device_external_id=event.get("deviceExternalId"),
                )
            case "meal_enabled":
                return MealEnabledEvent(
                    id=str(event.get("id", "")),
                    type=str(event_type),
                    source=str(event.get("source", "")),
                    time=str(event.get("time", "")),
                    url=str(event.get("url", "")),
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
                    id=str(event.get("id", "")),
                    type=str(event_type),
                    source=str(event.get("source", "")),
                    time=str(event.get("time", "")),
                    url=str(event.get("url", "")),
                    cluster_id=event.get("clusterId"),
                    metadata=event.get("metadata"),
                    device_id=event.get("deviceId"),
                    device_name=event.get("deviceName"),
                    product_ctn=event.get("productCtn"),
                    device_external_id=event.get("deviceExternalId"),
                )
            case "food_outlet_stuck":
                return FoodOutletStuckEvent(
                    id=str(event.get("id", "")),
                    type=str(event_type),
                    source=str(event.get("source", "")),
                    time=str(event.get("time", "")),
                    url=str(event.get("url", "")),
                    cluster_id=event.get("clusterId"),
                    metadata=event.get("metadata"),
                    device_id=event.get("deviceId"),
                    device_name=event.get("deviceName"),
                    product_ctn=event.get("productCtn"),
                    device_external_id=event.get("deviceExternalId"),
                )
            case "device_offline":
                return DeviceOfflineEvent(
                    id=str(event.get("id", "")),
                    type=str(event_type),
                    source=str(event.get("source", "")),
                    time=str(event.get("time", "")),
                    url=str(event.get("url", "")),
                    cluster_id=event.get("clusterId"),
                    metadata=event.get("metadata"),
                    device_id=event.get("deviceId"),
                    device_name=event.get("deviceName"),
                    product_ctn=event.get("productCtn"),
                    device_external_id=event.get("deviceExternalId"),
                )
            case "device_online":
                return DeviceOnlineEvent(
                    id=str(event.get("id", "")),
                    type=str(event_type),
                    source=str(event.get("source", "")),
                    time=str(event.get("time", "")),
                    url=str(event.get("url", "")),
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
                    id=str(event.get("id", "")),
                    type=str(event_type),
                    source=str(event.get("source", "")),
                    time=str(event.get("time", "")),
                    url=str(event.get("url", "")),
                )
