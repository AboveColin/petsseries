"""Tests for the validation and error-mapping decorators.

The validators run before a request, so a bad argument fails locally with a
message naming the argument, rather than as a 400 from the cloud. The error
mapper is what turns aiohttp's exceptions into this package's own, which is
what lets the Home Assistant integration tell an auth problem from an outage.
"""

from __future__ import annotations

import aiohttp
import pytest

from petsseries.decorators import handle_api_errors, validate_device_id, validate_local_key
from petsseries.exceptions import (
    PetsSeriesAPIError,
    PetsSeriesError,
    PetsSeriesNetworkError,
    PetsSeriesValidationError,
)


class Subject:
    """A stand-in for the client the decorators wrap."""

    @validate_device_id
    def with_device(self, device_id: str) -> str:
        return device_id

    @validate_local_key
    def with_key(self, device_id: str, local_key: str) -> str:
        return local_key


class TestDeviceIdValidation:
    """A device id has to be a non-empty string."""

    def test_a_normal_id_passes(self) -> None:
        assert Subject().with_device("bf1234567890abcdef") == "bf1234567890abcdef"

    @pytest.mark.parametrize("value", ["", None, 0, [], {}])
    def test_anything_falsey_or_non_string_is_refused(self, value: object) -> None:
        with pytest.raises(PetsSeriesValidationError, match="non-empty string"):
            Subject().with_device(value)  # type: ignore[arg-type]

    def test_whitespace_alone_is_refused(self) -> None:
        with pytest.raises(PetsSeriesValidationError, match="whitespace"):
            Subject().with_device("   ")

    def test_a_short_id_warns_but_is_allowed(self, caplog: pytest.LogCaptureFixture) -> None:
        # Short ids are suspicious, not invalid: refusing one would break any
        # device whose id does not match the shape seen so far.
        with caplog.at_level("WARNING"):
            assert Subject().with_device("abc") == "abc"
        assert "unusually short" in caplog.text


class TestLocalKeyValidation:
    """The local key guards the on-device control path."""

    def test_a_normal_key_passes(self) -> None:
        assert Subject().with_key("bf1234567890abcdef", "0123456789abcdef") == "0123456789abcdef"

    @pytest.mark.parametrize("value", ["", None, 0])
    def test_anything_falsey_or_non_string_is_refused(self, value: object) -> None:
        with pytest.raises(PetsSeriesValidationError, match="non-empty string"):
            Subject().with_key("bf1234567890abcdef", value)  # type: ignore[arg-type]

    def test_whitespace_alone_is_refused(self) -> None:
        with pytest.raises(PetsSeriesValidationError, match="whitespace"):
            Subject().with_key("bf1234567890abcdef", "  ")


class TestErrorMapping:
    """aiohttp's exceptions become this package's, so callers can branch."""

    async def test_a_successful_call_passes_its_result_through(self) -> None:
        @handle_api_errors("fetch things")
        async def works() -> str:
            return "ok"

        assert await works() == "ok"

    async def test_a_response_error_becomes_an_api_error_with_its_status(self) -> None:
        @handle_api_errors("fetch things")
        async def fails() -> None:
            raise aiohttp.ClientResponseError(
                request_info=None, history=(), status=403, message="Forbidden"
            )

        with pytest.raises(PetsSeriesAPIError) as caught:
            await fails()
        assert caught.value.status_code == 403
        assert "fetch things" in str(caught.value)

    async def test_a_transport_error_becomes_a_network_error(self) -> None:
        @handle_api_errors("fetch things")
        async def fails() -> None:
            raise aiohttp.ClientError("connection reset")

        with pytest.raises(PetsSeriesNetworkError, match="fetch things"):
            await fails()

    async def test_an_unexpected_error_is_left_alone(self) -> None:
        # Swallowing a programming error into an API error would hide the bug.
        @handle_api_errors("fetch things")
        async def fails() -> None:
            raise KeyError("deviceId")

        with pytest.raises(KeyError):
            await fails()

    async def test_the_operation_name_reaches_the_message(self) -> None:
        @handle_api_errors("dispense a meal")
        async def fails() -> None:
            raise aiohttp.ClientError("nope")

        with pytest.raises(PetsSeriesNetworkError, match="dispense a meal"):
            await fails()


class TestExceptionHierarchy:
    """One base, so a caller can catch everything this package raises."""

    @pytest.mark.parametrize(
        "error",
        [PetsSeriesAPIError, PetsSeriesNetworkError, PetsSeriesValidationError],
    )
    def test_every_error_shares_one_base(self, error: type) -> None:
        assert issubclass(error, PetsSeriesError)

    def test_the_api_error_renders_its_status(self) -> None:
        assert str(PetsSeriesAPIError("no", 404)) == "no (HTTP 404)"

    def test_a_status_free_api_error_renders_the_message_alone(self) -> None:
        assert str(PetsSeriesAPIError("no")) == "no"

    def test_the_message_is_kept_on_the_attribute(self) -> None:
        assert PetsSeriesError("boom").message == "boom"
