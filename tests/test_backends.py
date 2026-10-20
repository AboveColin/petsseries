"""Tests for the two Philips app backends.

A feeder set up in the Pet Series app and one set up in the HomeID app live on
different backends and in different Tuya spaces, behind one Philips login. The
behaviours that matter: homes come from both backends and remember which one,
every home-scoped call goes back to that backend, and a failing backend is an
error rather than a shorter list.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from aiohttp import web

from petsseries import HOMEID, PET_SERIES, backend_for
from petsseries.api import PetsSeriesClient
from petsseries.config import Config
from petsseries.exceptions import PetsSeriesAPIError
from petsseries.models import Home


class FakeBackend:
    """A loopback server standing in for one Philips pet backend."""

    def __init__(self) -> None:
        self.app = web.Application()
        self.paths: list[str] = []
        self.routes: dict[str, tuple[int, object]] = {}
        self.app.router.add_route("*", "/{tail:.*}", self._dispatch)
        self.url = ""

    def json(self, path: str, payload: object, status: int = 200) -> None:
        self.routes[path] = (status, payload)

    async def _dispatch(self, request: web.Request) -> web.StreamResponse:
        self.paths.append(request.path)
        status, payload = self.routes.get(request.path, (404, {"message": "no route"}))
        return web.json_response(payload, status=status)


async def _serve(fake: FakeBackend) -> web.AppRunner:
    runner = web.AppRunner(fake.app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    fake.url = f"http://127.0.0.1:{runner.addresses[0][1]}"
    return runner


@pytest_asyncio.fixture
async def backends() -> AsyncIterator[tuple[FakeBackend, FakeBackend]]:
    """A running fake Pet Series backend and a running fake HomeID backend."""
    pet, homeid = FakeBackend(), FakeBackend()
    runners = [await _serve(pet), await _serve(homeid)]
    try:
        yield pet, homeid
    finally:
        for runner in runners:
            await runner.cleanup()


@pytest_asyncio.fixture
async def client(
    backends: tuple[FakeBackend, FakeBackend], monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[PetsSeriesClient]:
    """A client pointed at both fakes, with the token check stubbed out."""
    pet, homeid = backends
    instance = PetsSeriesClient(access_token="a", refresh_token="r", id_token="id")
    instance.config = Config(base_url=pet.url, homeid_base_url=homeid.url)

    async def token_ok() -> None:
        return None

    monkeypatch.setattr(instance, "ensure_token_valid", token_ok)
    instance.headers = {"Authorization": "Bearer a"}
    try:
        yield instance
    finally:
        # Not instance.close(): that also saves tokens to a file.
        if instance.session:
            await instance.session.close()


def homes_payload(*ids: str) -> dict[str, Any]:
    return {"item": [{"id": i, "name": f"home {i}"} for i in ids]}


class TestBackendTable:
    def test_an_empty_key_means_the_pet_series_app(self) -> None:
        assert backend_for(None) is PET_SERIES
        assert backend_for("") is PET_SERIES

    def test_an_unknown_key_names_the_known_ones(self) -> None:
        with pytest.raises(ValueError, match="pet_series, homeid"):
            backend_for("nutriu")

    def test_the_two_apps_differ_in_host_and_tuya_app(self) -> None:
        assert PET_SERIES.base_url != HOMEID.base_url
        assert PET_SERIES.tuya_app["app_id"] != HOMEID.tuya_app["app_id"]
        assert HOMEID.package == "com.philips.ka.oneka.app"


class TestHomes:
    @pytest.mark.asyncio
    async def test_homes_come_from_both_backends_and_remember_which(
        self, client: PetsSeriesClient, backends: tuple[FakeBackend, FakeBackend]
    ) -> None:
        pet, homeid = backends
        pet.json("/api/homes", homes_payload("p1", "p2"))
        homeid.json("/api/homes", homes_payload("h1"))

        homes = await client.get_homes()

        assert [(h.id, h.backend) for h in homes] == [
            ("p1", "pet_series"),
            ("p2", "pet_series"),
            ("h1", "homeid"),
        ]

    @pytest.mark.asyncio
    async def test_an_account_with_only_homeid_homes_still_has_homes(
        self, client: PetsSeriesClient, backends: tuple[FakeBackend, FakeBackend]
    ) -> None:
        pet, homeid = backends
        pet.json("/api/homes", {"item": []})
        homeid.json("/api/homes", homes_payload("h1"))

        assert [h.id for h in await client.get_homes()] == ["h1"]

    @pytest.mark.asyncio
    async def test_a_failing_backend_is_an_error_not_a_shorter_list(
        self, client: PetsSeriesClient, backends: tuple[FakeBackend, FakeBackend]
    ) -> None:
        pet, homeid = backends
        pet.json("/api/homes", homes_payload("p1"))
        homeid.json("/api/homes", {"message": "down"}, status=503)

        with pytest.raises(PetsSeriesAPIError):
            await client.get_homes()


class TestHomeScopedCalls:
    @pytest.mark.asyncio
    async def test_devices_of_a_homeid_home_come_from_the_homeid_backend(
        self, client: PetsSeriesClient, backends: tuple[FakeBackend, FakeBackend]
    ) -> None:
        pet, homeid = backends
        homeid.json("/api/homes/h1/devices", {"item": [{"id": "d1", "name": "Feeder"}]})

        devices = await client.get_devices(Home(id="h1", name="x", backend="homeid"))

        assert homeid.paths == ["/api/homes/h1/devices"]
        assert pet.paths == []
        assert devices[0].backend == "homeid"
        assert client.device_backend("d1") is HOMEID

    @pytest.mark.asyncio
    async def test_meals_of_a_homeid_home_come_from_the_homeid_backend(
        self, client: PetsSeriesClient, backends: tuple[FakeBackend, FakeBackend]
    ) -> None:
        pet, homeid = backends
        homeid.json("/api/homes/h1/meals", {"item": []})
        client.meals.config = client.config

        await client.meals.get_meals(Home(id="h1", name="x", backend="homeid"))

        assert homeid.paths == ["/api/homes/h1/meals"]
        assert pet.paths == []

    def test_a_home_without_a_backend_is_a_pet_series_home(self) -> None:
        config = Config(base_url="https://pet.example", homeid_base_url="https://hid.example")
        assert config.home_url(Home(id="p1", name="x")) == "https://pet.example/api/homes/p1"
        assert (
            config.home_url(Home(id="h1", name="x", backend="homeid"))
            == "https://hid.example/api/homes/h1"
        )

    def test_a_device_the_client_has_not_listed_is_a_pet_series_device(
        self, client: PetsSeriesClient
    ) -> None:
        assert client.device_backend("never-seen") is PET_SERIES
