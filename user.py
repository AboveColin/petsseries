# petsseries/user.py

"""
User management for the PetsSeries client.
"""

import logging
import aiohttp

from .auth import AuthManager
from .models import User
from .config import Config

_LOGGER = logging.getLogger(__name__)


class UserManager:
    # pylint: disable=too-few-public-methods
    """
    Manages user-related operations.
    """

    def __init__(
        self, auth: AuthManager, config: Config, session: aiohttp.ClientSession
    ):
        self.auth = auth
        self.config = config
        self.session = session

    async def get_user_info(self) -> User:
        """
        Get user information from the UserInfo endpoint.
        """
        access_token = await self.auth.get_access_token()
        headers = {
            "Accept-Encoding": "gzip",
            "Authorization": f"Bearer {access_token}",
            "Connection": "keep-alive",
            "User-Agent": "UnofficialPetsSeriesClient/1.0",
        }
        try:
            async with self.session.get(
                self.config.user_info_url, headers=headers
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return User(
                    sub=data["sub"],
                    name=data["name"],
                    given_name=data["given_name"],
                    picture=data.get("picture"),
                    locale=data.get("locale"),
                    email=data["email"],
                )
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to get user info: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in get_user_info: %s", e)
            raise
