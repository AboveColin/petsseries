"""
Authentication management for the PetsSeries application.

This module handles loading, saving, and refreshing authentication tokens,
as well as decoding JWTs to retrieve necessary information.
"""

import time
import json
import logging
import os
from typing import Optional, Dict

import aiofiles
import aiohttp
import jwt

from .session import create_ssl_context


_LOGGER = logging.getLogger(__name__)


class AuthError(Exception):
    """Custom exception for authentication errors."""

    _LOGGER.error("An error occurred: %s", Exception)


class AuthManager:
    """
    Manages authentication tokens for the PetsSeries client.

    Handles loading tokens from a file, refreshing access tokens, and saving tokens.
    """

    def __init__(
        self,
        token_file: str = "tokens.json",
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ):
        """
        Initialize the AuthManager.

        Args:
            token_file (str): Path to the token file.
            access_token (Optional[str]): Existing access token.
            refresh_token (Optional[str]): Existing refresh token.
        """
        self.token_file_path = os.path.join(os.path.dirname(__file__), token_file)
        _LOGGER.info(
            "AuthManager initialized. Looking for tokens.json at: %s",
            self.token_file_path,
        )
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.id_token: Optional[str] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=10.0)

    async def _get_session(self) -> aiohttp.ClientSession:
        # pylint: disable=duplicate-code
        """
        Get or create an aiohttp ClientSession with a custom SSL context.

        Returns:
            aiohttp.ClientSession: The HTTP session.
        """
        if self.session is None:
            ssl_context = await create_ssl_context()
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(
                timeout=self.timeout, connector=connector
            )
            _LOGGER.debug("aiohttp.ClientSession initialized with certifi CA bundle.")
        return self.session

    async def load_tokens(self) -> None:
        """
        Load tokens from the token file.

        Raises:
            AuthError: If the token file is missing or contains invalid JSON.
        """
        try:
            async with aiofiles.open(self.token_file_path, "r") as file:
                token_content = await file.read()
            token_content = json.loads(token_content)
            self.access_token = token_content.get("access_token")
            self.refresh_token = token_content.get("refresh_token")
            _LOGGER.info("Tokens loaded successfully.")
        except FileNotFoundError as exc:
            _LOGGER.warning("Token file not found at: %s", self.token_file_path)
            if self.access_token is None or self.refresh_token is None:
                raise AuthError("Token file not found and no tokens provided.") from exc
            _LOGGER.warning("Generating tokens from arguments.")
            await self.save_tokens()
        except json.JSONDecodeError as exc:
            _LOGGER.error("Invalid JSON in token file: %s", exc)
            raise AuthError(f"Invalid JSON in token file: {exc}") from exc
        except Exception as exc:
            _LOGGER.error("Unexpected error loading tokens: %s", exc)
            raise AuthError(f"Unexpected error loading tokens: {exc}") from exc

    async def get_client_id(self) -> str:
        """
        Decode the access token to retrieve the client ID.

        Returns:
            str: The client ID.

        Raises:
            AuthError: If decoding fails or client_id is missing.
        """
        if self.access_token is None:
            raise AuthError("Access token is None")
        try:
            # Decode without verifying the signature
            token = jwt.decode(
                self.access_token,
                options={"verify_signature": False},
                algorithms=["RS256"],
            )
            client_id = token.get("client_id")
            if not client_id:
                raise AuthError("client_id not found in token")
            return client_id
        except jwt.DecodeError as exc:
            raise AuthError(f"Error decoding JWT: {exc}") from exc
        except Exception as exc:
            raise AuthError(f"Unexpected error: {exc}") from exc

    async def get_expiration(self) -> int:
        """
        Decode the access token to retrieve its expiration time.

        Returns:
            int: The expiration timestamp.

        Raises:
            AuthError: If decoding fails or expiration time is missing.
        """
        if self.access_token is None:
            raise AuthError("Access token is None")
        try:
            token = jwt.decode(
                self.access_token,
                options={"verify_signature": False},
                algorithms=["RS256"],
            )
            exp = token.get("exp")
            if exp is None:
                raise AuthError("Expiration time (exp) not found in token")
            return exp
        except jwt.DecodeError as exc:
            raise AuthError(f"Error decoding JWT: {exc}") from exc
        except Exception as exc:
            raise AuthError(f"Unexpected error: {exc}") from exc

    async def is_token_expired(self) -> bool:
        """
        Check if the access token has expired.

        Returns:
            bool: True if expired, False otherwise.
        """
        exp = await self.get_expiration()
        current_time = int(time.time())
        _LOGGER.debug("Token expiration time: %s, Current time: %s", exp, current_time)
        return exp < current_time

    async def refresh_access_token(self) -> Dict[str, str]:
        """
        Refresh the access token using the refresh token.

        Returns:
            Dict[str, str]: The refreshed tokens.

        Raises:
            AuthError: If the token refresh fails.
        """
        _LOGGER.info("Access token expired, refreshing...")
        url = "https://cdc.accounts.home.id/oidc/op/v1.0/4_JGZWlP8eQHpEqkvQElolbA/token"
        client_id = await self.get_client_id()
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": client_id,
        }
        headers = {
            "Accept-Encoding": "gzip",
            "Accept": "application/json",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "UnofficialPetsSeriesClient/1.0",
        }

        try:
            _LOGGER.debug(
                "Refreshing access token with data: %s and headers: %s", data, headers
            )
            session = await self._get_session()
            async with session.post(url, headers=headers, data=data) as response:
                _LOGGER.debug("Token refresh response status: %s", response.status)
                if response.status == 200:
                    response_json = await response.json()
                    self.access_token = response_json.get("access_token")
                    self.refresh_token = response_json.get("refresh_token")
                    _LOGGER.info("Access token refreshed successfully.")
                    await self.save_tokens()
                    return response_json

                text = await response.text()
                _LOGGER.error("Failed to refresh token: %s", text)
                raise AuthError(f"Failed to refresh token: {text}")

        except aiohttp.ClientResponseError as e:
            _LOGGER.error("HTTP error during token refresh: %s %s", e.status, e.message)
            raise AuthError(
                f"HTTP error during token refresh: {e.status} {e.message}"
            ) from e
        except aiohttp.ClientError as e:
            _LOGGER.error("Request exception during token refresh: %s", e)
            raise AuthError(f"Request exception during token refresh: {e}") from e
        except Exception as e:
            _LOGGER.error("Unexpected error during token refresh: %s", e)
            raise AuthError(f"Unexpected error during token refresh: {e}") from e

    async def get_access_token(self) -> str:
        """
        Retrieve the current access token, refreshing it if necessary.

        Returns:
            str: The access token.

        Raises:
            AuthError: If token loading or refreshing fails.
        """
        if self.access_token is None:
            await self.load_tokens()
        if await self.is_token_expired():
            await self.refresh_access_token()
        return self.access_token

    async def save_tokens(
        self,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        id_token: Optional[str] = None,
    ) -> None:
        """
        Save the updated tokens back to tokens.json.

        Args:
            access_token (Optional[str]): New access token.
            refresh_token (Optional[str]): New refresh token.
            id_token (Optional[str]): New ID token.

        Raises:
            AuthError: If saving tokens fails.
        """
        try:
            if access_token:
                self.access_token = access_token
            if refresh_token:
                self.refresh_token = refresh_token
            if id_token:
                self.id_token = id_token
            tokens = {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
            }
            async with aiofiles.open(self.token_file_path, "w") as file:
                await file.write(json.dumps(tokens, indent=4))
            _LOGGER.info("Tokens saved successfully to %s", self.token_file_path)
        except Exception as e:
            _LOGGER.error("Failed to save tokens.json: %s", e)
            raise AuthError(f"Failed to save tokens.json: {e}") from e

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
            _LOGGER.debug("aiohttp.ClientSession closed.")

    async def __aenter__(self) -> "AuthManager":
        """Enter the runtime context related to this object."""
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the runtime context and close the session."""
        await self.close()
