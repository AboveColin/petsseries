"""Tuya *application* credentials of the Philips apps, and a signer for each.

These are the only app-specific inputs to the generic :mod:`tuya_mobile` signer,
extracted from the Philips Android apps and identical for every install. They
are the apps' Tuya *application* identifiers, not user secrets. The values live
in :mod:`petsseries.backends`, one set per app.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from tuya_mobile import NativeTuyaSigner, PurePythonTuyaSigner

from .backends import PET_SERIES, Backend

# The Pet Series app's values, kept under their old names for existing callers.
PHILIPS_APP = dict(PET_SERIES.tuya_app)
MQTT_PARTNER_ID = PET_SERIES.partner_id


@dataclass
class TuyaSession:
    """One logged-in Tuya mobile session in one Philips app's Tuya space."""

    backend: Backend
    client: Any = field(repr=False)  # tuya_mobile.TuyaMobileClient
    http: Any = field(repr=False)  # the aiohttp.ClientSession it owns
    # Tuya partner prefix for the MQTT username, from the login response.
    partner_id: str = ""


def build_signer(backend: Backend = PET_SERIES):
    """Return the Tuya signer for one Philips app.

    Pure-Python by default (no external dependency). ``PETSERIES_TUYA_SIGNER``
    selects the legacy external signer, which only knows the Pet Series app, so
    it applies to that app alone.
    """
    app = dict(backend.tuya_app)
    command = os.environ.get("PETSERIES_TUYA_SIGNER")
    if command and backend is PET_SERIES:
        return NativeTuyaSigner(
            command,
            app_id=app["app_id"],
            app_secret=app["app_secret"],
            cert_sha256=app["cert_sha256_hex"],
            key_global=app["app_key"],
            android_root=os.environ.get("PETSERIES_TUYA_ANDROID_ROOT"),
        )
    return PurePythonTuyaSigner(**app)
