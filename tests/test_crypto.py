"""Tests for thumbnail decryption.

Event thumbnails come off an S3 bucket encrypted, with a header the mobile app
parses by hand. The header has two versions and they place the ciphertext at
different offsets, so a version mix-up decrypts garbage rather than failing:
the round trip below is what distinguishes the two.
"""

from __future__ import annotations

import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from petsseries.crypto import decrypt_image

KEY = "0123456789abcdef"  # 16 bytes: AES-128, as the app uses.
PLAINTEXT = b"\xff\xd8\xff\xe0 a small pretend JPEG " * 4


def encrypt(plaintext: bytes, key: str, *, header_version: int, level: int = 3) -> bytes:
    """Build a blob in the same frame the app writes, for a round trip.

    Version 1 skips one byte after the IV block; version 2 spends that byte on
    the cipher level. Both then skip 39 bytes of metadata.
    """
    iv = os.urandom(16)
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(key.encode()), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    header = header_version.to_bytes(4, "big") + iv + b"\x00" * 4
    header += bytes([level]) if header_version == 2 else b"\x00"
    header += b"\x00" * 39
    return header + ciphertext


class TestRoundTrip:
    """What the app writes, this reads back."""

    def test_a_version_2_blob_decrypts(self) -> None:
        blob = encrypt(PLAINTEXT, KEY, header_version=2)
        assert decrypt_image(blob, KEY) == PLAINTEXT

    def test_a_version_1_blob_decrypts(self) -> None:
        # Version 1 has no level byte and is assumed to be AES.
        blob = encrypt(PLAINTEXT, KEY, header_version=1)
        assert decrypt_image(blob, KEY) == PLAINTEXT

    def test_a_short_payload_decrypts(self) -> None:
        blob = encrypt(b"x", KEY, header_version=2)
        assert decrypt_image(blob, KEY) == b"x"

    def test_an_exactly_block_sized_payload_decrypts(self) -> None:
        # PKCS7 adds a whole block of padding here; dropping it would return
        # 16 bytes of 0x10 appended to the image.
        payload = b"A" * 16
        assert decrypt_image(encrypt(payload, KEY, header_version=2), KEY) == payload


class TestMissingInput:
    """Absence is empty, not a crash: a thumbnail is optional."""

    def test_no_data_yields_nothing(self) -> None:
        assert decrypt_image(b"", KEY) == b""

    def test_no_key_yields_nothing(self) -> None:
        assert decrypt_image(b"some data", "") == b""

    def test_neither_yields_nothing(self) -> None:
        assert decrypt_image(b"", "") == b""


class TestWrongKey:
    """A wrong key must not return plausible-looking bytes."""

    def test_the_wrong_key_yields_nothing_rather_than_garbage(self) -> None:
        blob = encrypt(PLAINTEXT, KEY, header_version=2)
        # Unpadding fails on garbage, which is what makes this detectable.
        assert decrypt_image(blob, "fedcba9876543210") == b""


class TestUnsupportedLevel:
    """Only AES-CBC is implemented; anything else returns empty, not garbage."""

    def test_an_unknown_cipher_level_yields_nothing(self) -> None:
        blob = encrypt(PLAINTEXT, KEY, header_version=2, level=4)
        assert decrypt_image(blob, KEY) == b""
