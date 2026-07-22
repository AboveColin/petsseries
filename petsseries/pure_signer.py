"""Back-compat shim: the pure signer now lives in the ``tuya_mobile`` package.

``PurePythonTuyaSigner.from_environment()`` returns the Philips-configured
signer. New code should use ``petsseries.tuya_app.build_signer()`` or
``tuya_mobile.PurePythonTuyaSigner`` directly.
"""
from __future__ import annotations

from tuya_mobile.signer import PurePythonTuyaSigner as _PurePythonTuyaSigner


class PurePythonTuyaSigner(_PurePythonTuyaSigner):
    @classmethod
    def from_environment(cls) -> "PurePythonTuyaSigner":
        from .tuya_app import PHILIPS_APP

        return cls(**PHILIPS_APP)
