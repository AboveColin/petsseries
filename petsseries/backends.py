"""The two Philips apps that can own a feeder, and the backend each one uses.

A feeder set up in the Philips Pet Series app lives on the Pet Series backend
and in the Pet Series app's Tuya space. A feeder set up in the Philips HomeID
app lives on a second backend and in HomeID's own Tuya space. Both apps sign in
through the same Philips account, so one login reads both backends, and the
Philips id token opens a Tuya session in either app.

The Tuya values are the apps' public application identifiers, the same for every
install. They are not user secrets.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True)
class Backend:
    """One Philips app: its pet backend and its Tuya application."""

    key: str
    name: str
    base_url: str
    # Signer inputs for tuya_mobile.PurePythonTuyaSigner.
    tuya_app: Mapping[str, str] = field(repr=False)
    # Tuya partner prefix for the MQTT username. The login response carries it
    # as partnerIdentity; this value is the fallback when it does not.
    partner_id: str = ""
    # countryCode for the Tuya thirdLogin. Empty means the dial code of the
    # account's country: tuya_mobile then reads PETSERIES_TUYA_COUNTRY_CODE.
    tuya_country_code: str = ""

    @property
    def package(self) -> str:
        """Android package name of the app."""
        return self.tuya_app["package"]


PET_SERIES = Backend(
    key="pet_series",
    name="Philips Pet Series app",
    base_url="https://petseries.prd.nbx.iot.versuni.com",
    tuya_app=MappingProxyType(
        {
            "app_id": "7gqdt8hrgamaxeksxchg",
            "app_secret": "55v8jwqadnkpmdxtr4ep9yxefm7csgr7",
            "cert_sha256_hex": "1c625cd6777b18be9486130956c227b18aefcce5decc9505d46302ad71c806c5",
            "app_key": "fxe8mk3xnn4tjna35gqmvjd4kwvw3dyq",
            "package": "com.versuni.nbx.petsseries",
        }
    ),
    partner_id="p2065237",
    # This library has always sent "1" for this app, and those logins find the
    # user's devices. A change could log in to a different Tuya user.
    tuya_country_code="1",
)

HOMEID = Backend(
    key="homeid",
    name="Philips HomeID app",
    base_url="https://petseries.production.nbx.iot.versuni.com",
    tuya_app=MappingProxyType(
        {
            "app_id": "d997esphw5fevawrcyud",
            "app_secret": "fcxp5hwguv5vpa4wveu8tujnhky8nhde",
            "cert_sha256_hex": "d2d695a11d1b84f925a9456e27f445e9fd87c37463aa8a3432a66a233b0fd50f",
            "app_key": "dgsgxpwew54gdpcm5cuqfrvjpakxgvmn",
            "package": "com.philips.ka.oneka.app",
        }
    ),
    partner_id="p2645382",
    # The HomeID app sends the dial code of the app's country ("31" for the
    # Netherlands), so this login does the same.
)

BACKENDS: tuple[Backend, ...] = (PET_SERIES, HOMEID)


def backend_for(key: str | None) -> Backend:
    """Return the backend with this key. An empty key means the Pet Series app."""
    if not key:
        return PET_SERIES
    for backend in BACKENDS:
        if backend.key == key:
            return backend
    raise ValueError(
        f"unknown backend {key!r}; known: {', '.join(b.key for b in BACKENDS)}"
    )
