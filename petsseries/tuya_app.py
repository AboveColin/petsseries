"""Philips Pet Series Tuya *application* credentials.

These are the only app-specific inputs to the generic :mod:`tuya_mobile` signer
— extracted from the Philips Pet Series Android app (``com.versuni.nbx.petsseries``),
identical for every install. They are the app's Tuya *application* identifiers,
not user secrets.
"""
from __future__ import annotations

import os

from tuya_mobile import NativeTuyaSigner, PurePythonTuyaSigner

PHILIPS_APP = {
    "app_id": "7gqdt8hrgamaxeksxchg",
    "app_secret": "55v8jwqadnkpmdxtr4ep9yxefm7csgr7",
    "cert_sha256_hex": "1c625cd6777b18be9486130956c227b18aefcce5decc9505d46302ad71c806c5",
    "app_key": "fxe8mk3xnn4tjna35gqmvjd4kwvw3dyq",
    "package": "com.versuni.nbx.petsseries",
}

# Tuya "partner" prefix used in the MQTT signaling username.
MQTT_PARTNER_ID = "p2065237"


def build_signer():
    """Return the Tuya signer for the Philips app.

    Pure-Python by default (no external dependency). Set ``PETSERIES_TUYA_SIGNER``
    to a signer command/URL only to use the legacy external signer.
    """
    command = os.environ.get("PETSERIES_TUYA_SIGNER")
    if command:
        return NativeTuyaSigner(
            command,
            app_id=PHILIPS_APP["app_id"],
            app_secret=PHILIPS_APP["app_secret"],
            cert_sha256=PHILIPS_APP["cert_sha256_hex"],
            key_global=PHILIPS_APP["app_key"],
            android_root=os.environ.get("PETSERIES_TUYA_ANDROID_ROOT"),
        )
    return PurePythonTuyaSigner(**PHILIPS_APP)
