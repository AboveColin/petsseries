# meals.py

"""
MealsManager module for handling meal-related operations in the PetsSeriesClient.
"""

import logging
import urllib.parse
from typing import Any, List

import aiohttp  # type: ignore[import-not-found]

from .config import Config
from .models import Home, Meal

_LOGGER = logging.getLogger(__name__)


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
        url = f"{self.config.base_url}/api/homes/{home.id}/meals"
        session = await self.client.get_client()
        try:
            async with session.get(url, headers=self.client.headers) as response:
                response.raise_for_status()
                meals_data = await response.json()
                meals = [
                    Meal(
                        id=meal["id"],
                        name=meal["name"],
                        portion_amount=meal.get("portionAmount") if meal.get("portionAmount") is not None else meal.get("amount"),
                        feed_time=meal.get("feedTime") or meal.get("time"),
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

        url = f"{self.config.base_url}/api/homes/{home.id}/meals/{meal.id}"

        # Prepare the payload with updated fields
        def _to_iso8601(value):
            try:
                # datetime/date/time objects
                return value.isoformat()  # type: ignore[attr-defined]
            except Exception:
                return str(value)

        # Normalize repeat days to a list of ints
        repeat_days: List[int] = (
            meal.repeat_days if meal.repeat_days else [1, 2, 3, 4, 5, 6, 7]
        )

        payload = {
            "name": meal.name,
            "portionAmount": meal.portion_amount,
            "feedTime": _to_iso8601(meal.feed_time),
            "repeatDays": repeat_days,
        }

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
                        portion_amount=updated_data["portionAmount"],
                        feed_time=updated_data["feedTime"],
                        repeat_days=parsed_repeat_days,
                        device_id=updated_data["deviceId"],
                        enabled=updated_data.get("enabled", True),
                        url=updated_data["url"],
                    )
                if response.status == 204:
                    _LOGGER.info("Meal %s updated successfully (no content).", meal.id)
                    # Return the provided meal as the updated representation
                    return Meal(
                        id=meal.id,
                        name=meal.name,
                        portion_amount=meal.portion_amount,
                        feed_time=_to_iso8601(meal.feed_time),
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

        def _to_iso8601(value):
            try:
                return value.isoformat()  # type: ignore[attr-defined]
            except Exception:
                return str(value)

        payload = {
            "deviceId": meal.device_id,
            "feedTime": _to_iso8601(meal.feed_time),
            "name": meal.name,
            "portionAmount": meal.portion_amount,
            "repeatDays": repeat_days,
        }

        session = await self.client.get_client()
        try:
            headers = {
                **self.client.headers,
                "Content-Type": "application/json; charset=UTF-8",
            }
            async with session.post(
                f"{self.config.base_url}/api/homes/{home.id}/meals",
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
                        portion_amount=meal.portion_amount,
                        feed_time=_to_iso8601(meal.feed_time),
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
                        portion_amount=created["portionAmount"],
                        feed_time=created["feedTime"],
                        repeat_days=created.get("repeatDays", repeat_days),
                        device_id=created["deviceId"],
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
        url = f"{self.config.base_url}/api/homes/{home.id}/meals/{meal_id}"

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
        url = f"{self.config.base_url}/api/homes/{home.id}/meals/{meal_id}"

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
