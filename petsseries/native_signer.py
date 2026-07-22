"""Back-compat shim: the signer now lives in the standalone ``tuya_mobile`` package.

``NativeTuyaSigner.from_environment()`` returns the Philips-configured signer
(pure-Python by default; external only if ``PETSERIES_TUYA_SIGNER`` is set).
"""
from __future__ import annotations

from tuya_mobile.signer import (  # noqa: F401
    NativeSignerError,
    NativeTuyaSigner as _NativeTuyaSigner,
    PurePythonTuyaSigner,
)


class NativeTuyaSigner(_NativeTuyaSigner):
    """Philips-flavoured entry point kept for existing imports."""

    @classmethod
    def from_environment(cls):
        from .tuya_app import build_signer

        return build_signer()
