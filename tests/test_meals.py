"""Tests for the meal scheduler.

This is the part of the library that dispenses food, so the payloads it builds
get checked field by field. Two behaviours matter most: an empty repeat-days
list has to become every day rather than no days, and a create can come back
as either a 201 with a Location header or a 200 with a body.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import time

import aiohttp
import pytest
import pytest_asyncio
from aiohttp import web

from petsseries.config import Config
from petsseries.meals import MealsManager
from petsseries.models import Home, Meal

HOME = Home(id="h1", name="Thuis", shared=False, number_of_devices=1, external_id="e", url="u")
EVERY_DAY = [1, 2, 3, 4, 5, 6, 7]


class StubClient:
    """The three things MealsManager uses from the API client."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self.headers = {"Authorization": "Bearer test-token"}
        self.token_checks = 0

    async def ensure_token_valid(self) -> None:
        self.token_checks += 1

    async def get_client(self) -> aiohttp.ClientSession:
        return self._session


class FakeApi:
    """A loopback server standing in for the meals endpoints."""

    def __init__(self) -> None:
        self.app = web.Application()
        self.requests: list[web.Request] = []
        self.bodies: list[object] = []
        self._routes: dict[tuple[str, str], object] = {}
        self.app.router.add_route("*", "/{tail:.*}", self._dispatch)
        self.url = ""

    def handle(self, method: str, path: str, handler) -> None:  # noqa: ANN001
        self._routes[(method, path)] = handler

    def json(self, method: str, path: str, payload: object, status: int = 200, headers=None) -> None:  # noqa: ANN001
        self.handle(method, path, lambda _r: web.json_response(payload, status=status, headers=headers))

    def empty(self, method: str, path: str, status: int, headers=None) -> None:  # noqa: ANN001
        self.handle(method, path, lambda _r: web.Response(status=status, headers=headers))

    async def _dispatch(self, request: web.Request) -> web.StreamResponse:
        self.requests.append(request)
        try:
            self.bodies.append(await request.json())
        except Exception:  # noqa: BLE001  a bodyless request is a valid case
            self.bodies.append(None)
        handler = self._routes.get((request.method, request.path))
        if handler is None:
            return web.json_response({"message": "no route"}, status=404)
        result = handler(request)
        return await result if hasattr(result, "__await__") else result


@pytest_asyncio.fixture
async def api() -> AsyncIterator[FakeApi]:
    """A running fake meals API."""
    fake = FakeApi()
    runner = web.AppRunner(fake.app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    fake.url = f"http://127.0.0.1:{runner.addresses[0][1]}"
    try:
        yield fake
    finally:
        await runner.cleanup()


@pytest_asyncio.fixture
async def meals(api: FakeApi) -> AsyncIterator[MealsManager]:
    """A meals manager pointed at the fake."""
    async with aiohttp.ClientSession() as session:
        manager = MealsManager(StubClient(session))
        manager.config = Config(base_url=api.url)
        yield manager


def a_meal(**overrides: object) -> Meal:
    """A meal with every field filled in."""
    fields = {
        "id": "m1",
        "name": "Ontbijt",
        "portion_amount": 2.0,
        "feed_time": "07:30:00",
        "repeat_days": [1, 2, 3, 4, 5],
        "device_id": "d1",
        "enabled": True,
        "url": "u",
    }
    fields.update(overrides)
    return Meal(**fields)  # type: ignore[arg-type]


class TestListing:
    """Reading the schedule."""

    async def test_meals_are_parsed(self, api: FakeApi, meals: MealsManager) -> None:
        api.json(
            "GET",
            "/api/homes/h1/meals",
            {
                "item": [
                    {
                        "id": "m1",
                        "name": "Ontbijt",
                        "portionAmount": 2,
                        "feedTime": "07:30:00",
                        "repeatDays": [1, 2, 3],
                        "deviceId": "d1",
                        "enabled": True,
                        "url": "u",
                    }
                ]
            },
        )
        result = await meals.get_meals(HOME)
        assert [m.name for m in result] == ["Ontbijt"]
        assert result[0].repeat_days == [1, 2, 3]

    async def test_the_older_field_names_still_parse(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        # Earlier firmware sent amount/time rather than portionAmount/feedTime.
        api.json(
            "GET",
            "/api/homes/h1/meals",
            {
                "item": [
                    {
                        "id": "m1",
                        "name": "Ontbijt",
                        "amount": 3,
                        "time": "08:00:00",
                        "repeatDays": [1],
                        "deviceId": "d1",
                        "enabled": True,
                        "url": "u",
                    }
                ]
            },
        )
        result = await meals.get_meals(HOME)
        assert result[0].portion_amount == 3
        assert result[0].feed_time == "08:00:00"

    async def test_an_empty_schedule_is_not_an_error(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.json("GET", "/api/homes/h1/meals", {"item": []})
        assert await meals.get_meals(HOME) == []

    async def test_a_missing_item_key_yields_nothing(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.json("GET", "/api/homes/h1/meals", {})
        assert await meals.get_meals(HOME) == []

    async def test_the_token_is_checked_before_the_request(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.json("GET", "/api/homes/h1/meals", {"item": []})
        await meals.get_meals(HOME)
        assert meals.client.token_checks == 1

    async def test_the_authorization_header_is_sent(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.json("GET", "/api/homes/h1/meals", {"item": []})
        await meals.get_meals(HOME)
        assert api.requests[-1].headers["Authorization"] == "Bearer test-token"

    async def test_a_server_error_is_raised(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.json("GET", "/api/homes/h1/meals", {"message": "boom"}, status=500)
        with pytest.raises(aiohttp.ClientResponseError):
            await meals.get_meals(HOME)


class TestUpdating:
    """Changing a meal, which the API answers two ways."""

    async def test_the_payload_carries_the_four_editable_fields(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.empty("PATCH", "/api/homes/h1/meals/m1", 204)
        await meals.update_meal(HOME, a_meal())
        assert api.bodies[-1] == {
            "name": "Ontbijt",
            "portionAmount": 2.0,
            "feedTime": "07:30:00",
            "repeatDays": [1, 2, 3, 4, 5],
        }

    async def test_an_empty_repeat_list_becomes_every_day(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        # Sending [] would schedule the meal on no day at all, which reads as
        # "saved" and silently stops feeding the animal.
        api.empty("PATCH", "/api/homes/h1/meals/m1", 204)
        await meals.update_meal(HOME, a_meal(repeat_days=[]))
        assert api.bodies[-1]["repeatDays"] == EVERY_DAY

    async def test_a_time_object_is_sent_as_iso_8601(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.empty("PATCH", "/api/homes/h1/meals/m1", 204)
        await meals.update_meal(HOME, a_meal(feed_time=time(7, 30)))
        assert api.bodies[-1]["feedTime"] == "07:30:00"

    async def test_a_204_returns_the_meal_that_was_sent(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.empty("PATCH", "/api/homes/h1/meals/m1", 204)
        result = await meals.update_meal(HOME, a_meal(name="Avondeten"))
        assert result.name == "Avondeten"

    async def test_a_200_returns_the_server_copy(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.json(
            "PATCH",
            "/api/homes/h1/meals/m1",
            {
                "id": "m1",
                "name": "Server naam",
                "portionAmount": 4,
                "feedTime": "09:00:00",
                "repeatDays": [6, 7],
                "deviceId": "d1",
                "enabled": False,
                "url": "u",
            },
        )
        result = await meals.update_meal(HOME, a_meal())
        assert result.name == "Server naam"
        assert result.repeat_days == [6, 7]
        assert result.enabled is False

    async def test_string_repeat_days_from_the_server_become_integers(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.json(
            "PATCH",
            "/api/homes/h1/meals/m1",
            {
                "id": "m1",
                "name": "n",
                "portionAmount": 1,
                "feedTime": "t",
                "repeatDays": ["1", "2"],
                "deviceId": "d1",
                "url": "u",
            },
        )
        assert (await meals.update_meal(HOME, a_meal())).repeat_days == [1, 2]

    async def test_unusable_repeat_days_fall_back_to_what_was_sent(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.json(
            "PATCH",
            "/api/homes/h1/meals/m1",
            {
                "id": "m1",
                "name": "n",
                "portionAmount": 1,
                "feedTime": "t",
                "repeatDays": "monday",
                "deviceId": "d1",
                "url": "u",
            },
        )
        assert (await meals.update_meal(HOME, a_meal())).repeat_days == [1, 2, 3, 4, 5]

    async def test_a_meal_without_an_id_is_refused_before_any_request(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        with pytest.raises(ValueError, match="Meal ID"):
            await meals.update_meal(HOME, a_meal(id=""))
        assert api.requests == []

    async def test_a_rejected_update_raises(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.json("PATCH", "/api/homes/h1/meals/m1", {"message": "no"}, status=400)
        with pytest.raises(aiohttp.ClientResponseError):
            await meals.update_meal(HOME, a_meal())


class TestCreating:
    """A new meal, which the API answers two ways."""

    async def test_the_payload_carries_the_five_fields(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.empty(
            "POST",
            "/api/homes/h1/meals",
            201,
            headers={"Location": "https://api.test/api/homes/h1/meals/m9"},
        )
        await meals.create_meal(HOME, a_meal(id=""))
        assert api.bodies[-1] == {
            "deviceId": "d1",
            "feedTime": "07:30:00",
            "name": "Ontbijt",
            "portionAmount": 2.0,
            "repeatDays": [1, 2, 3, 4, 5],
        }

    async def test_a_201_takes_the_new_id_out_of_the_location_header(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.empty(
            "POST",
            "/api/homes/h1/meals",
            201,
            headers={"Location": "https://api.test/api/homes/h1/meals/m9"},
        )
        result = await meals.create_meal(HOME, a_meal(id=""))
        assert result.id == "m9"
        assert result.url == "https://api.test/api/homes/h1/meals/m9"

    async def test_a_201_without_a_location_header_is_an_error(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        # Returning a meal with a blank id would look like success and then
        # fail on the next update.
        api.empty("POST", "/api/homes/h1/meals", 201)
        with pytest.raises(aiohttp.ClientResponseError):
            await meals.create_meal(HOME, a_meal(id=""))

    async def test_a_200_returns_the_server_copy(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.json(
            "POST",
            "/api/homes/h1/meals",
            {
                "id": "m9",
                "name": "Ontbijt",
                "portionAmount": 2,
                "feedTime": "07:30:00",
                "deviceId": "d1",
                "url": "u",
            },
        )
        result = await meals.create_meal(HOME, a_meal(id=""))
        assert result.id == "m9"
        assert result.enabled is True

    async def test_a_missing_repeat_list_becomes_every_day(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.empty(
            "POST",
            "/api/homes/h1/meals",
            201,
            headers={"Location": "https://api.test/api/homes/h1/meals/m9"},
        )
        await meals.create_meal(HOME, a_meal(id="", repeat_days=None))
        assert api.bodies[-1]["repeatDays"] == EVERY_DAY

    async def test_a_rejected_create_raises(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.json("POST", "/api/homes/h1/meals", {"message": "no"}, status=400)
        with pytest.raises(aiohttp.ClientResponseError):
            await meals.create_meal(HOME, a_meal(id=""))


class TestEnabling:
    """The toggle the integration exposes as a switch."""

    async def test_the_payload_is_just_the_flag(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.empty("PATCH", "/api/homes/h1/meals/m1", 204)
        await meals.set_meal_enabled(HOME, "m1", False)
        assert api.bodies[-1] == {"enabled": False}

    async def test_enabling_reports_success(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.empty("PATCH", "/api/homes/h1/meals/m1", 204)
        assert await meals.set_meal_enabled(HOME, "m1", True) is True


class TestEnableAndDisableWrappers:
    """Two thin wrappers the integration calls instead of passing a bool."""

    async def test_enable_sends_true(self, api: FakeApi, meals: MealsManager) -> None:
        api.empty("PATCH", "/api/homes/h1/meals/m1", 204)
        assert await meals.enable_meal(HOME, "m1") is True
        assert api.bodies[-1] == {"enabled": True}

    async def test_disable_sends_false(self, api: FakeApi, meals: MealsManager) -> None:
        api.empty("PATCH", "/api/homes/h1/meals/m1", 204)
        assert await meals.disable_meal(HOME, "m1") is True
        assert api.bodies[-1] == {"enabled": False}

    async def test_a_rejected_toggle_raises(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.json("PATCH", "/api/homes/h1/meals/m1", {"message": "no"}, status=409)
        with pytest.raises(aiohttp.ClientResponseError):
            await meals.set_meal_enabled(HOME, "m1", True)


class TestDeleting:
    """Removing a meal from the schedule."""

    async def test_a_204_reports_success(self, api: FakeApi, meals: MealsManager) -> None:
        api.empty("DELETE", "/api/homes/h1/meals/m1", 204)
        assert await meals.delete_meal(HOME, "m1") is True

    async def test_the_meal_id_reaches_the_path(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.empty("DELETE", "/api/homes/h1/meals/m1", 204)
        await meals.delete_meal(HOME, "m1")
        assert api.requests[-1].path == "/api/homes/h1/meals/m1"

    async def test_a_missing_meal_raises_rather_than_reporting_success(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        # Reporting a delete that did not happen leaves the animal on a
        # schedule the user believes is gone.
        api.json("DELETE", "/api/homes/h1/meals/m1", {"message": "not found"}, status=404)
        with pytest.raises(aiohttp.ClientResponseError):
            await meals.delete_meal(HOME, "m1")

    async def test_the_token_is_checked_first(
        self, api: FakeApi, meals: MealsManager
    ) -> None:
        api.empty("DELETE", "/api/homes/h1/meals/m1", 204)
        await meals.delete_meal(HOME, "m1")
        assert meals.client.token_checks == 1
