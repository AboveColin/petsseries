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
from typing import Any, Awaitable, Callable, Dict, Optional

import aiofiles
import aiohttp
from yarl import URL

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
        save_callback: Optional[Callable[..., Awaitable[None] | None]] = None,
    ):
        """
        Initialize the AuthManager.

        Args:
            token_file (str): Path to the token file.
            access_token (Optional[str]): Existing access token.
            refresh_token (Optional[str]): Existing refresh token.
            save_callback (Optional[callable]): Callback to save tokens asynchronously.
        """
        self.token_file_path: Optional[str]
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
        self._refresh_lock = asyncio.Lock()

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
                raw_token_content = await file.read()
            token_content: Any = json.loads(raw_token_content)
            self.access_token = token_content.get("access_token")
            self.refresh_token = token_content.get("refresh_token")
            self.id_token = token_content.get("id_token")
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
        async with self._refresh_lock:
            # Another request may have refreshed the token while we waited.
            if self.access_token and not await self.is_token_expired():
                return {"access_token": self.access_token, "refresh_token": self.refresh_token or ""}

            _LOGGER.info("Access token expired, refreshing...")
            if not self.refresh_token:
                raise AuthError("Refresh token is missing")
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
                _LOGGER.debug("Refreshing access token")
                session = await self._get_session()
                async with session.post(Config.token_url, headers=headers, data=data) as response:
                    _LOGGER.debug("Token refresh response status: %s", response.status)
                    if response.status == 200:
                        response_json = await response.json()
                        self.access_token = response_json.get("access_token")
                        self.refresh_token = response_json.get("refresh_token") or self.refresh_token
                        self.id_token = response_json.get("id_token") or self.id_token
                        _LOGGER.info("Access token refreshed successfully.")
                        await self.save_tokens()
                        return response_json

                    text = await response.text()
                    _LOGGER.error("Failed to refresh token: %s", text)
                    raise AuthError(f"Failed to refresh token: {text}")

            except aiohttp.ClientResponseError as e:
                raise AuthError(f"HTTP error during token refresh: {e.status} {e.message}") from e
            except aiohttp.ClientError as e:
                raise AuthError(f"Request exception during token refresh: {e}") from e
            except AuthError:
                raise
            except Exception as e:
                raise AuthError(f"Unexpected error during token refresh: {e}") from e

    async def request_email_code(self, email: str) -> Dict[str, Any]:
        """Send a one-time login code to an email address."""
        email = email.strip()
        if not email or "@" not in email:
            raise AuthError("A valid email address is required")
        session = await self._get_session()
        self._ensure_device_cookies(session)
        data = {
            "apiKey": Config.cdc_api_key,
            "email": email,
            "type": "email",
            "lang": "en",
            "format": "json",
        }
        async with session.post(f"{Config.cdc_base_url}/accounts.otp.sendCode", data=data) as response:
            payload = await response.json(content_type=None)
        if payload.get("errorCode", 0) not in (0, "0"):
            raise AuthError(payload.get("errorMessage") or payload.get("statusReason") or "Unable to send email code")
        return payload

    @staticmethod
    def _ensure_device_cookies(session: aiohttp.ClientSession) -> None:
        """Create the CDC device cookies used by the official web client."""
        ucid = secrets.token_urlsafe(16)
        gmid = f"gmid.ver4.{secrets.token_urlsafe(8)}.{secrets.token_urlsafe(48)}.sc3"
        cookies = {
            "ucid": ucid,
            f"gig_bootstrap_{Config.cdc_api_key}": "cdc_ver4",
            "hasGmid": "ver4",
            "gmid": gmid,
        }
        for base in (Config.cdc_base_url, Config.authui_base_url):
            session.cookie_jar.update_cookies(cookies, response_url=URL(base))

    async def login_with_email_code(self, email: str, code: str, vtoken: Optional[str] = None) -> Dict[str, Any]:
        """Exchange an emailed OTP for OAuth tokens using the CDC/OIDC flow."""
        if not code.strip():
            raise AuthError("The email code is required")
        session = await self._get_session()
        try:
            async with session.get(
                f"{Config.authui_base_url}/authui/client/login",
                params={"client_id": Config.oidc_client_id, "ui_locales": "en-US"},
            ):
                pass
        except aiohttp.ClientError as err:
            raise AuthError(f"Unable to initialize Philips login session: {err}") from err
        data: Dict[str, str] = {
            "apiKey": Config.cdc_api_key,
            "code": code.strip(),
            "lang": "en",
            "format": "json",
            "targetEnv": "jssdk",
            "includeUserInfo": "true",
            "include": "profile,id_token,data,subscriptions,sessionInfo",
            "sessionExpiration": "0",
            "sdk": "js_latest",
            "authMode": "cookie",
            "pageURL": f"{Config.authui_base_url}/authui/client/login",
            "sdkBuild": "16477",
        }
        if vtoken:
            data["vToken"] = vtoken
        else:
            data["email"] = email.strip()
        async with session.post(f"{Config.cdc_base_url}/accounts.otp.login", data=data) as response:
            payload = await response.json(content_type=None)
        if payload.get("errorCode", 0) not in (0, "0"):
            raise AuthError(payload.get("errorMessage") or payload.get("statusReason") or "Invalid email code")
        session_info = payload.get("sessionInfo") or {}
        cookie_name = session_info.get("cookieName")
        cookie_value = session_info.get("cookieValue")
        if cookie_name and cookie_value:
            session.cookie_jar.update_cookies({cookie_name: cookie_value})
        login_token = session_info.get("login_token")
        if not login_token:
            raise AuthError("OTP login did not return a login token")
        # The continuation endpoint returns a short-lived OIDC authorization code.
        verifier = self.generate_code_verifier()
        challenge = self.generate_code_challenge(verifier)
        context = await self._start_authorize(session, challenge)
        uid = payload.get("UID")
        uid_signature = payload.get("UIDSignature")
        signature_timestamp = payload.get("signatureTimestamp")
        consent = None
        if uid and uid_signature:
            consent, context, consent_user_key, consent_signature = await self._request_consent(
                session, uid, uid_signature, context, signature_timestamp
            )
            uid = consent_user_key or uid
            uid_signature = consent_signature or uid_signature
        auth_code = await self._continue_authorize(
            session, login_token, context, consent, uid, uid_signature
        )
        tokens = await self._exchange_code(auth_code, verifier)
        self.access_token = tokens.get("access_token")
        self.refresh_token = tokens.get("refresh_token")
        self.id_token = tokens.get("id_token")
        if not self.access_token or not self.refresh_token:
            raise AuthError("OAuth exchange did not return required tokens")
        await self.save_tokens()
        return tokens

    async def _start_authorize(self, session: aiohttp.ClientSession, challenge: str) -> str:
        # OTP login already authenticated the browser session. Asking for
        # prompt=login here causes CDC to reject the context because its
        # session-start timestamp predates the newly-created context.
        params = {
            "client_id": Config.oidc_client_id,
            "response_type": "code",
            "scope": Config.oidc_scope,
            "redirect_uri": Config.oidc_redirect_uri,
            "prompt": "none",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "nonce": secrets.token_urlsafe(16),
            "state": secrets.token_urlsafe(16),
        }
        try:
            device_id = next(
                (cookie.value for cookie in session.cookie_jar if cookie.key == "ucid"),
                None,
            )
        except (AttributeError, TypeError):
            device_id = None
        if device_id:
            params["DeviceId"] = device_id
            params["deviceId"] = device_id
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/140.0.0.0 Mobile Safari/537.36",
            "Referer": f"{Config.authui_base_url}/",
        }
        async with session.get(
            f"{Config.cdc_base_url}/oidc/op/v1.0/{Config.cdc_api_key}/authorize",
            params=params,
            headers=headers,
            allow_redirects=False,
        ) as response:
            location = response.headers.get("Location", "")
        context = urllib.parse.parse_qs(urllib.parse.urlparse(location).query).get("context", [""])[0]
        if not context:
            # Some CDC tenants return context through contextData instead of
            # the AuthUI proxy redirect after an OTP login.
            fallback_params = {
                "client_id": Config.oidc_client_id,
                "mode": "forceLogin",
                "oidc_context": "",
                "sdk": "js",
                "sdkBuild": "1",
            }
            async with session.get(
                f"{Config.cdc_base_url}/oidc/op/v1.0/{Config.cdc_api_key}/contextData",
                params=fallback_params,
                headers={"Accept": "application/json"},
            ) as fallback:
                payload = await fallback.json(content_type=None)
            context = (
                payload.get("context")
                or payload.get("ctx_id")
                or payload.get("oidc_context")
                or ""
            )
        if not context:
            raise AuthError("OIDC authorize did not return a context")
        session.cookie_jar.update_cookies({"oidc_ctx": context})
        return context

    async def _request_consent(
        self,
        session: aiohttp.ClientSession,
        uid: str,
        uid_signature: str,
        context: str,
        signature_timestamp: Optional[str] = None,
    ) -> tuple[str, str, Optional[str], Optional[str]]:
        """Obtain the AuthUI consent payload required by OIDC continuation."""
        params: Dict[str, str] = {
            "UID": uid,
            "UIDSignature": uid_signature,
            "clientID": Config.oidc_client_id,
            "gig_client_id": Config.oidc_client_id,
            "context": context,
            "prompt": "Login",
            "scope": Config.oidc_scope,
        }
        if signature_timestamp:
            params["signatureTimestamp"] = str(signature_timestamp)
        async with session.get(
            f"{Config.authui_base_url}/authui/api/ui/consent",
            params=params,
            allow_redirects=False,
        ) as response:
            location = response.headers.get("Location", "")
        query = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
        consent = query.get("consent", [""])[0]
        returned_context = query.get("context", [""])[0] or context
        if not consent:
            raise AuthError("AuthUI consent was not returned")
        if not returned_context:
            raise AuthError("AuthUI consent did not return context")
        session.cookie_jar.update_cookies({"oidc_ctx": returned_context})
        return (
            consent,
            returned_context,
            query.get("userKey", [None])[0],
            query.get("sig", [None])[0],
        )

    async def _continue_authorize(
        self,
        session: aiohttp.ClientSession,
        login_token: str,
        context: str,
        consent: Optional[str] = None,
        uid: Optional[str] = None,
        signature: Optional[str] = None,
    ) -> str:
        params: Dict[str, str] = {
            "login_token": login_token,
            "client_id": Config.oidc_client_id,
            "context": context,
        }
        if consent:
            params["consent"] = consent
        if uid:
            params["userKey"] = uid
        if signature:
            params["sig"] = signature
        try:
            device_id = next(
                (cookie.value for cookie in session.cookie_jar if cookie.key == "ucid"),
                None,
            )
        except (AttributeError, TypeError):
            device_id = None
        if device_id:
            params["DeviceId"] = device_id
            params["deviceId"] = device_id
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/140.0.0.0 Mobile Safari/537.36",
            "Referer": f"{Config.authui_base_url}/",
            "Origin": Config.authui_base_url,
        }
        async with session.get(
            f"{Config.cdc_base_url}/oidc/op/v1.0/{Config.cdc_api_key}/authorize/continue",
            params=params,
            headers=headers,
            allow_redirects=False,
        ) as response:
            location = response.headers.get("Location", "")
        code = urllib.parse.parse_qs(urllib.parse.urlparse(location).query).get("code", [""])[0]
        if not code:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
            detail = query.get("error_description", query.get("errorMessage", [""]))[0]
            raise AuthError(detail or "OIDC continuation did not return an authorization code")
        return code

    async def _exchange_code(self, code: str, verifier: str) -> Dict[str, Any]:
        session = await self._get_session()
        data = {"grant_type": "authorization_code", "code": code, "redirect_uri": Config.oidc_redirect_uri, "client_id": Config.oidc_client_id, "code_verifier": verifier}
        async with session.post(Config.token_url, data=data) as response:
            payload = await response.json(content_type=None)
        if response.status != 200 or payload.get("error"):
            raise AuthError(payload.get("error_description") or "OAuth token exchange failed")
        return payload

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
        if not self.access_token:
            raise AuthError("Access token is unavailable")
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
                "id_token": self.id_token,
            }
            if self.save_callback:
                if asyncio.iscoroutinefunction(self.save_callback):
                    try:
                        await self.save_callback(self.access_token, self.refresh_token, self.id_token)
                    except TypeError:
                        await self.save_callback(self.access_token, self.refresh_token)
                else:
                    try:
                        self.save_callback(self.access_token, self.refresh_token, self.id_token)
                    except TypeError:
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
