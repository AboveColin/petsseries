"""
Authentication management for the PetsSeries application.

This module handles loading, saving, and refreshing authentication tokens,
as well as decoding JWTs to retrieve necessary information.
Supports PKCE-based OAuth 2.0 authorization code flow.
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import secrets
import time
import urllib.parse
from typing import Any, Dict, Optional

import aiofiles
import aiohttp

try:
    import jwt

    # Verify it's PyJWT, not another jwt module
    if not hasattr(jwt, "decode"):
        raise ImportError(
            "The 'jwt' module imported is not PyJWT. "
            "Please ensure PyJWT is installed: pip install PyJWT"
        )
except ImportError as e:
    raise ImportError("PyJWT is required. Install it with: pip install PyJWT") from e

from .config import Config
from .session import create_ssl_context

_LOGGER = logging.getLogger(__name__)


class AuthError(Exception):
    """Custom exception for authentication errors."""

    def __init__(self, message: str):
        super().__init__(message)


class AuthManager:
    """
    Manages authentication tokens for the PetsSeries client.

    Handles loading tokens from a file, refreshing access tokens, and saving tokens.
    """

    def __init__(
        self,
        token_file: Optional[str] = "tokens.json",
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        save_callback: Optional[callable] = None,
    ):
        """
        Initialize the AuthManager.

        Args:
            token_file (str): Path to the token file.
            access_token (Optional[str]): Existing access token.
            refresh_token (Optional[str]): Existing refresh token.
            save_callback (Optional[callable]): Callback to save tokens asynchronously.
        """
        if token_file:
            self.token_file_path = os.path.join(os.path.dirname(__file__), token_file)
            _LOGGER.info(
                "AuthManager initialized. Looking for tokens.json at: %s",
                self.token_file_path,
            )
        else:
            self.token_file_path = None
            _LOGGER.info("AuthManager initialized without token file storage.")
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.save_callback = save_callback
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
        if not self.token_file_path:
            return

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
                _LOGGER.error("Token file not found and no tokens provided.")
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
            _LOGGER.error("Access token is None")
            raise AuthError("Access token is None")

        # Verify jwt module is PyJWT
        if not hasattr(jwt, "decode"):
            raise AuthError(
                "Wrong JWT library installed. The 'jwt' module does not have 'decode' method. "
                "Please ensure PyJWT is installed: pip install PyJWT"
            )

        try:
            # Decode without verifying the signature
            token = jwt.decode(
                self.access_token,
                options={"verify_signature": False},
                algorithms=["RS256"],
            )
            client_id = token.get("client_id")
            if not client_id:
                _LOGGER.error("client_id not found in token")
                raise AuthError("client_id not found in token")
            return client_id
        except AttributeError as exc:
            if "decode" in str(exc) or not hasattr(jwt, "decode"):
                _LOGGER.error(
                    "JWT module error: %s. The wrong 'jwt' package may be installed. "
                    "Please ensure PyJWT is installed: pip install PyJWT",
                    exc,
                )
                raise AuthError(
                    "Wrong JWT library installed. Please install PyJWT: pip install PyJWT"
                ) from exc
            raise
        except jwt.DecodeError as exc:
            _LOGGER.error("Error decoding JWT: %s", exc)
            raise AuthError(f"Error decoding JWT: {exc}") from exc
        except Exception as exc:
            _LOGGER.error("Unexpected error: %s", exc)
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
            _LOGGER.error("Access token is None")
            raise AuthError("Access token is None")

        # Verify jwt module is PyJWT
        if not hasattr(jwt, "decode"):
            raise AuthError(
                "Wrong JWT library installed. The 'jwt' module does not have 'decode' method. "
                "Please ensure PyJWT is installed: pip install PyJWT"
            )

        try:
            token = jwt.decode(
                self.access_token,
                options={"verify_signature": False},
                algorithms=["RS256"],
            )
            exp = token.get("exp")
            if exp is None:
                _LOGGER.error("Expiration time (exp) not found in token")
                raise AuthError("Expiration time (exp) not found in token")
            return exp
        except AttributeError as exc:
            if "decode" in str(exc) or not hasattr(jwt, "decode"):
                _LOGGER.error(
                    "JWT module error: %s. The wrong 'jwt' package may be installed. "
                    "Please ensure PyJWT is installed: pip install PyJWT",
                    exc,
                )
                raise AuthError(
                    "Wrong JWT library installed. Please install PyJWT: pip install PyJWT"
                ) from exc
            raise
        except jwt.DecodeError as exc:
            _LOGGER.error("Error decoding JWT: %s", exc)
            raise AuthError(f"Error decoding JWT: {exc}") from exc
        except Exception as exc:
            _LOGGER.error("Unexpected error: %s", exc)
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
            async with session.post(
                Config.token_url, headers=headers, data=data
            ) as response:
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
            if self.save_callback:
                if asyncio.iscoroutinefunction(self.save_callback):
                    await self.save_callback(self.access_token, self.refresh_token)
                else:
                    self.save_callback(self.access_token, self.refresh_token)

            if self.token_file_path:
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

    # ========================================================================
    # PKCE OAuth 2.0 Authorization Code Flow Methods
    # ========================================================================

    @staticmethod
    def generate_code_verifier() -> str:
        """
        Generate a cryptographically random code verifier for PKCE.

        Returns:
            str: A URL-safe base64-encoded random string (43-128 characters).
        """
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_code_challenge(verifier: str) -> str:
        """
        Generate a code challenge from the code verifier using SHA-256.

        Args:
            verifier (str): The code verifier string.

        Returns:
            str: The base64url-encoded SHA-256 hash of the verifier.
        """
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").replace("=", "")

    async def get_openid_configuration(self) -> Dict[str, Any]:
        """
        Fetch the OpenID Connect discovery document.

        Returns:
            Dict[str, Any]: The OpenID configuration containing endpoints.

        Raises:
            AuthError: If fetching the configuration fails.
        """
        try:
            session = await self._get_session()
            async with session.get(Config.oidc_discovery_url) as response:
                if response.status == 200:
                    config = await response.json()
                    _LOGGER.debug("Fetched OpenID configuration successfully")
                    return config
                text = await response.text()
                _LOGGER.error("Failed to fetch OpenID config: %s", text)
                raise AuthError(f"Failed to fetch OpenID configuration: {text}")
        except aiohttp.ClientError as e:
            _LOGGER.error("Network error fetching OpenID config: %s", e)
            raise AuthError(f"Network error fetching OpenID configuration: {e}") from e

    async def get_authorization_url(
        self,
        code_verifier: Optional[str] = None,
        state: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Generate the authorization URL for the PKCE OAuth flow.

        Args:
            code_verifier (Optional[str]): The code verifier. If not provided, one will be generated.
            state (Optional[str]): The state parameter. If not provided, one will be generated.

        Returns:
            Dict[str, str]: A dictionary containing:
                - authorization_url: The URL to redirect the user to
                - code_verifier: The code verifier to use for token exchange
                - state: The state parameter for CSRF protection

        Raises:
            AuthError: If fetching the OpenID configuration fails.
        """
        config = await self.get_openid_configuration()
        auth_endpoint = config.get("authorization_endpoint")

        if not auth_endpoint:
            raise AuthError("Authorization endpoint not found in OpenID configuration")

        if code_verifier is None:
            code_verifier = self.generate_code_verifier()
        if state is None:
            state = secrets.token_urlsafe(16)

        code_challenge = self.generate_code_challenge(code_verifier)

        params = {
            "client_id": Config.oidc_client_id,
            "redirect_uri": Config.oidc_redirect_uri,
            "response_type": "code",
            "scope": Config.oidc_scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        authorization_url = auth_endpoint + "?" + urllib.parse.urlencode(params)

        _LOGGER.info("Generated authorization URL")
        _LOGGER.debug("Authorization URL: %s", authorization_url)

        return {
            "authorization_url": authorization_url,
            "code_verifier": code_verifier,
            "state": state,
        }

    async def exchange_authorization_code(
        self,
        authorization_code: str,
        code_verifier: str,
    ) -> Dict[str, Any]:
        """
        Exchange an authorization code for access and refresh tokens.

        Args:
            authorization_code (str): The authorization code from the callback.
            code_verifier (str): The code verifier used when generating the auth URL.

        Returns:
            Dict[str, Any]: The token response containing access_token, refresh_token, id_token, etc.

        Raises:
            AuthError: If the token exchange fails.
        """
        config = await self.get_openid_configuration()
        token_endpoint = config.get("token_endpoint")

        if not token_endpoint:
            raise AuthError("Token endpoint not found in OpenID configuration")

        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": Config.oidc_redirect_uri,
            "client_id": Config.oidc_client_id,
            "code_verifier": code_verifier,
        }

        headers = {
            "Accept-Encoding": "gzip",
            "Accept": "application/json",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "UnofficialPetsSeriesClient/1.0",
        }

        try:
            _LOGGER.info("Exchanging authorization code for tokens...")
            session = await self._get_session()
            async with session.post(
                token_endpoint, headers=headers, data=data
            ) as response:
                if response.status == 200:
                    tokens = await response.json()
                    self.access_token = tokens.get("access_token")
                    self.refresh_token = tokens.get("refresh_token")
                    self.id_token = tokens.get("id_token")
                    _LOGGER.info("Successfully exchanged authorization code for tokens")
                    await self.save_tokens()
                    return tokens

                text = await response.text()
                _LOGGER.error("Token exchange failed: %s", text)
                raise AuthError(f"Token exchange failed: {text}")

        except aiohttp.ClientResponseError as e:
            _LOGGER.error(
                "HTTP error during token exchange: %s %s", e.status, e.message
            )
            raise AuthError(
                f"HTTP error during token exchange: {e.status} {e.message}"
            ) from e
        except aiohttp.ClientError as e:
            _LOGGER.error("Request exception during token exchange: %s", e)
            raise AuthError(f"Request exception during token exchange: {e}") from e

    @staticmethod
    def parse_callback_url(callback_url: str) -> Dict[str, Optional[str]]:
        """
        Parse the callback URL to extract the authorization code and state.

        Args:
            callback_url (str): The full callback URL (e.g., paw://login?code=...&state=...).

        Returns:
            Dict[str, Optional[str]]: A dictionary with 'code' and 'state' keys.

        Raises:
            AuthError: If the URL cannot be parsed or required parameters are missing.
        """
        try:
            parsed = urllib.parse.urlparse(callback_url)
            query_params = urllib.parse.parse_qs(parsed.query)

            code = query_params.get("code", [None])[0]
            state = query_params.get("state", [None])[0]
            error = query_params.get("error", [None])[0]
            error_description = query_params.get("error_description", [None])[0]

            if error:
                error_msg = f"OAuth error: {error}"
                if error_description:
                    error_msg += f" - {error_description}"
                raise AuthError(error_msg)

            if not code:
                raise AuthError("Authorization code not found in callback URL")

            return {"code": code, "state": state}

        except AuthError:
            raise
        except Exception as e:
            raise AuthError(f"Failed to parse callback URL: {e}") from e
