# meals.py

"""
MealsManager module for handling meal-related operations in the PetsSeriesClient.
"""

import logging
import re
import urllib.parse
from typing import Any, List

import aiohttp  # type: ignore[import-not-found]

from .config import Config
from .models import Home, Meal

_LOGGER = logging.getLogger(__name__)


def _wire_time(value: Any) -> str:
    """Return a meal time in the "HH:mm" form that both app backends take.

    The apps send CreateMealRequest.time as "HH:mm" and the backends return
    the same form. A datetime.time, "HH:mm", "HH:mm:ss" and "HH:mmZ" are
    accepted. Anything else raises, because a time the backend reads
    differently would feed the animal at the wrong hour.
    """
    if hasattr(value, "hour") and hasattr(value, "minute"):
        return f"{int(value.hour):02d}:{int(value.minute):02d}"
    match = re.match(r"^(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?Z?$", str(value).strip())
    if match is None:
        raise ValueError(f"Meal time must be HH:mm, got {value!r}")
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        raise ValueError(f"Meal time must be HH:mm, got {value!r}")
    return f"{hour:02d}:{minute:02d}"


def _wire_amount(value: Any) -> int:
    """Return a portion count as the integer the backends take.

    CreateMealRequest.amount is an int in the app. A fractional amount
    raises instead of being rounded, because rounding changes the food the
    feeder gives.
    """
    amount = float(value)
    if not amount.is_integer() or amount < 1:
        raise ValueError(f"Meal amount must be a whole number of portions, got {value!r}")
    return int(amount)


def _meal_body(meal: Meal, repeat_days: List[int]) -> dict:
    """Return the CreateMealRequest body. POST and the full PATCH use it."""
    return {
        "name": meal.name,
        "time": _wire_time(meal.feed_time),
        "amount": _wire_amount(meal.portion_amount),
        "deviceId": meal.device_id,
        "repeatDays": repeat_days,
    }


def _first(data: dict, *keys: str) -> Any:
    """Return the first value of keys that is present and not None."""
    for key in keys:
        if data.get(key) is not None:
            return data[key]
    return None


class MealsManager:
    """
    Manager class for handling meal-related operations.
    """

    def __init__(self, client):
        """
        Initialize the MealsManager with a reference to the PetsSeriesClient.

        Args:
            client (PetsSeriesClient): The main API client.
        """
        self.client = client
        self.config = Config()

    async def get_meals(self, home: Home) -> List[Meal]:
        """
        Get meals for the selected home.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.home_url(home)}/meals"
        session = await self.client.get_client()
        try:
            async with session.get(url, headers=self.client.headers) as response:
                response.raise_for_status()
                meals_data = await response.json()
                meals = [
                    Meal(
                        id=meal["id"],
                        name=meal["name"],
                        portion_amount=_first(meal, "amount", "portionAmount"),
                        feed_time=_first(meal, "time", "feedTime"),
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
            meal (Meal): The Meal object containing updated information.

        Returns:
            Meal: The updated Meal object.

        Raises:
            ValueError: If the meal ID is not provided.
            aiohttp.ClientResponseError: If the HTTP request fails.
            Exception: For any unexpected errors.
        """
        await self.client.ensure_token_valid()

        if not meal.id:
            raise ValueError("Meal ID must be provided for updating a meal.")

        url = f"{self.config.home_url(home)}/meals/{meal.id}"

        # Normalize repeat days to a list of ints
        repeat_days: List[int] = (
            meal.repeat_days if meal.repeat_days else [1, 2, 3, 4, 5, 6, 7]
        )

        payload = _meal_body(meal, repeat_days)

        session = await self.client.get_client()
        try:
            headers = {
                **self.client.headers,
                "Content-Type": "application/json; charset=UTF-8",
            }
            async with session.patch(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    updated_data = await response.json()
                    _LOGGER.info("Meal %s updated successfully.", meal.id)

                    def _ensure_int_list(value: Any, fallback: List[int]) -> List[int]:
                        if isinstance(value, list):
                            result: List[int] = []
                            for v in value:
                                try:
                                    result.append(int(v))
                                except Exception:
                                    continue
                            return result or fallback
                        return fallback

                    parsed_repeat_days = _ensure_int_list(
                        updated_data.get("repeatDays"), repeat_days
                    )
                    return Meal(
                        id=updated_data["id"],
                        name=updated_data["name"],
                        portion_amount=_first(updated_data, "amount", "portionAmount"),
                        feed_time=_first(updated_data, "time", "feedTime"),
                        repeat_days=parsed_repeat_days,
                        device_id=updated_data.get("deviceId", meal.device_id),
                        enabled=updated_data.get("enabled", True),
                        url=updated_data["url"],
                    )
                if response.status == 204:
                    _LOGGER.info("Meal %s updated successfully (no content).", meal.id)
                    # Return the provided meal as the updated representation
                    return Meal(
                        id=meal.id,
                        name=meal.name,
                        portion_amount=payload["amount"],
                        feed_time=payload["time"],
                        repeat_days=repeat_days,
                        device_id=meal.device_id,
                        enabled=getattr(meal, "enabled", True),
                        url=getattr(meal, "url", url),
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
        raise RuntimeError("Failed to update meal")

    async def create_meal(self, home: Home, meal: Meal) -> Meal:
        """
        Create a new meal for the specified home and device.

        Args:
            home (Home): The home where the meal will be created.
            meal (Meal): The Meal object containing meal details.

        Returns:
            Meal: The created Meal object.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
            Exception: For any unexpected errors.
        """
        await self.client.ensure_token_valid()
        if meal.repeat_days is None:
            repeat_days: List[int] = [1, 2, 3, 4, 5, 6, 7]
        else:
            repeat_days = meal.repeat_days

        payload = _meal_body(meal, repeat_days)

        session = await self.client.get_client()
        try:
            headers = {
                **self.client.headers,
                "Content-Type": "application/json; charset=UTF-8",
            }
            async with session.post(
                f"{self.config.home_url(home)}/meals",
                headers=headers,
                json=payload,
            ) as response:
                if response.status == 201:
                    location = response.headers.get("Location")
                    if not location:
                        _LOGGER.error("Location header missing in response.")
                        raise aiohttp.ClientResponseError(
                            status=response.status,
                            message="Location header missing in response.",
                            request_info=response.request_info,
                            history=response.history,
                        )

                    # Extract the meal ID from the Location URL
                    parsed_url = urllib.parse.urlparse(location)
                    meal_id = parsed_url.path.split("/")[-1]

                    _LOGGER.info("Meal created successfully with ID: %s", meal_id)

                    return Meal(
                        id=meal_id,
                        name=meal.name,
                        portion_amount=payload["amount"],
                        feed_time=payload["time"],
                        repeat_days=repeat_days,
                        device_id=meal.device_id,
                        enabled=True,
                        url=location,
                    )
                if response.status == 200:
                    created = await response.json()
                    _LOGGER.info(
                        "Meal created successfully with ID: %s", created.get("id")
                    )
                    return Meal(
                        id=created["id"],
                        name=created["name"],
                        portion_amount=_first(created, "amount", "portionAmount"),
                        feed_time=_first(created, "time", "feedTime"),
                        repeat_days=created.get("repeatDays", repeat_days),
                        device_id=created.get("deviceId", meal.device_id),
                        enabled=created.get("enabled", True),
                        url=created.get("url", ""),
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
        raise RuntimeError("Failed to create meal")

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
        await self.client.ensure_token_valid()
        url = f"{self.config.home_url(home)}/meals/{meal_id}"

        payload = {"enabled": enabled}

        session = await self.client.get_client()
        try:
            async with session.patch(
                url, headers=self.client.headers, json=payload
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
                "Failed to %s meal %s: %s %s",
                "enable" if enabled else "disable",
                meal_id,
                e.status,
                e.message,
            )
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in set_meal_enabled: %s", e)
            raise
        return False

    async def enable_meal(self, home: Home, meal_id: str) -> bool:
        """
        Enable a specific meal.
        """
        return await self.set_meal_enabled(home, meal_id, True)

    async def disable_meal(self, home: Home, meal_id: str) -> bool:
        """
        Disable a specific meal.
        """
        return await self.set_meal_enabled(home, meal_id, False)

    async def delete_meal(self, home: Home, meal_id: str) -> bool:
        """
        Delete a specific meal from the selected home.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.home_url(home)}/meals/{meal_id}"

        session = await self.client.get_client()
        try:
            async with session.delete(url, headers=self.client.headers) as response:
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
        return False
