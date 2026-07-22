"""Back-compat shim: the mobile client now lives in the ``tuya_mobile`` package."""
from __future__ import annotations

from tuya_mobile.client import (  # noqa: F401  # pylint: disable=unused-import
    SIGN_KEYS,
    TuyaMobileClient,
    canonical_string,
    _decrypt,
    _encrypt,
    _swap_md5,
    _walk,
)
