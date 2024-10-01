import jwt
import aiohttp
import json
import logging
import os
import asyncio
import aiofiles
import certifi
import ssl

from .utils import get_current_time

_LOGGER = logging.getLogger(__name__)


class AuthError(Exception):
    """Custom exception for authentication errors."""
    pass


class AuthManager:
    def __init__(self, token_file="tokens.json", access_token=None, refresh_token=None):
        self.token_file_path = os.path.join(os.path.dirname(__file__), token_file)
        _LOGGER.info(f"AuthManager initialized. Looking for tokens.json at: {self.token_file_path}")
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.id_token = None
        self.session = None
        self.timeout = aiohttp.ClientTimeout(total=10.0)

    async def _create_ssl_context(self) -> ssl.SSLContext:
        """Create an SSL context using certifi's CA bundle in a separate thread."""
        return await asyncio.to_thread(
            ssl.create_default_context, cafile=certifi.where()
        )

    async def _get_session(self):
        if self.session is None:
            ssl_context = await self._create_ssl_context()
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(timeout=self.timeout, connector=connector)
            _LOGGER.debug("aiohttp.ClientSession initialized with certifi CA bundle.")
        return self.session

    async def load_tokens(self):
        try:
            async with aiofiles.open(self.token_file_path, "r") as file:
                token_content = await file.read()
            token_content = json.loads(token_content)
            self.access_token = token_content.get("access_token")
            self.refresh_token = token_content.get("refresh_token")
            _LOGGER.info("Tokens loaded successfully.")
        except FileNotFoundError:
            _LOGGER.warning(f"Token file not found at: {self.token_file_path}")
            if self.access_token is None or self.refresh_token is None:
                raise AuthError("Token file not found and no tokens provided.")
            _LOGGER.warning("Generating tokens from arguments.")
            await self.save_tokens()
        except json.JSONDecodeError as e:
            _LOGGER.error(f"Invalid JSON in token file: {e}")
            raise AuthError(f"Invalid JSON in token file: {e}")
        except Exception as e:
            _LOGGER.error(f"Unexpected error loading tokens: {e}")
            raise AuthError(f"Unexpected error loading tokens: {e}")

    async def get_client_id(self):
        """Decode the access token to retrieve the client ID."""
        if self.access_token is None:
            raise AuthError("Access token is None")
        try:
            # Decode without verifying the signature
            token = jwt.decode(
                self.access_token,
                options={"verify_signature": False},
                algorithms=["RS256"]
            )
            client_id = token.get("client_id")
            if not client_id:
                raise AuthError("client_id not found in token")
            return client_id
        except jwt.DecodeError as e:
            raise AuthError(f"Error decoding JWT: {e}")
        except Exception as e:
            raise AuthError(f"Unexpected error: {e}")

    async def get_expiration(self):
        """Decode the access token to retrieve its expiration time."""
        if self.access_token is None:
            raise AuthError("Access token is None")
        try:
            token = jwt.decode(
                self.access_token,
                options={"verify_signature": False},
                algorithms=["RS256"]
            )
            exp = token.get("exp")
            if exp is None:
                raise AuthError("Expiration time (exp) not found in token")
            return exp
        except jwt.DecodeError as e:
            raise AuthError(f"Error decoding JWT: {e}")
        except Exception as e:
            raise AuthError(f"Unexpected error: {e}")

    async def is_token_expired(self):
        """Check if the access token has expired."""
        exp = await self.get_expiration()
        current_time = get_current_time()
        _LOGGER.debug(f"Token expiration time: {exp}, Current time: {current_time}")
        return exp < current_time

    async def refresh_access_token(self):
        """Refresh the access token using the refresh token."""
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
            _LOGGER.debug(f"Refreshing access token with data: {data} and headers: {headers}")
            session = await self._get_session()
            async with session.post(url, headers=headers, data=data) as response:
                _LOGGER.debug(f"Token refresh response status: {response.status}")
                if response.status == 200:
                    response_json = await response.json()
                    self.access_token = response_json.get("access_token")
                    self.refresh_token = response_json.get("refresh_token")
                    _LOGGER.info("Access token refreshed successfully.")
                    await self.save_tokens()
                    return response_json
                else:
                    text = await response.text()
                    _LOGGER.error(f"Failed to refresh token: {text}")
                    raise AuthError(f"Failed to refresh token: {text}")
        except aiohttp.ClientResponseError as e:
            _LOGGER.error(f"HTTP error during token refresh: {e.status} {e.message}")
            raise AuthError(f"HTTP error during token refresh: {e.status} {e.message}")
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Request exception during token refresh: {e}")
            raise AuthError(f"Request exception during token refresh: {e}")
        except Exception as e:
            _LOGGER.error(f"Unexpected error during token refresh: {e}")
            raise AuthError(f"Unexpected error during token refresh: {e}")

    async def get_access_token(self):
        """Retrieve the current access token, refreshing it if necessary."""
        if self.access_token is None:
            await self.load_tokens()
        if await self.is_token_expired():
            await self.refresh_access_token()
        return self.access_token

    async def save_tokens(self, access_token=None, refresh_token=None, id_token=None):
        """Save the updated tokens back to tokens.json."""
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
            _LOGGER.info(f"Tokens saved successfully to {self.token_file_path}")
        except Exception as e:
            _LOGGER.error(f"Failed to save tokens.json: {e}")
            raise AuthError(f"Failed to save tokens.json: {e}")

    async def close(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
            _LOGGER.debug("aiohttp.ClientSession closed.")

    async def __aenter__(self):
        await self._get_session()
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        await self.close()

