# homes.py

"""
HomesManager module for handling home-related operations in the PetsSeriesClient.

This module provides functionality for:
- Home CRUD operations (create, rename, delete)
- Home invitations (send, accept, resend, delete, update)
"""

import logging
from typing import List, Optional

import aiohttp  # type: ignore[import-not-found]

from .config import Config
from .models import Home, HomeInvite, HomeInviteRole

_LOGGER = logging.getLogger(__name__)


class HomesManager:
    """
    Manager class for handling home-related operations.
    """

    def __init__(self, client):
        """
        Initialize the HomesManager with a reference to the PetsSeriesClient.

        Args:
            client (PetsSeriesClient): The main API client.
        """
        self.client = client
        self.config = Config()

    # =========================================================================
    # HOME CRUD OPERATIONS
    # =========================================================================

    async def create_home(self, name: str) -> Home:
        """
        Create a new home.

        Args:
            name (str): Name for the new home.

        Returns:
            Home: The created Home object.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes"
        payload = {"name": name}

        session = await self.client.get_client()
        try:
            headers = {
                **self.client.headers,
                "Content-Type": "application/json; charset=UTF-8",
            }
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status in (200, 201):
                    # Try to get the home from response or Location header
                    if response.status == 201:
                        location = response.headers.get("Location")
                        if location:
                            # Extract home ID from Location URL
                            home_id = location.split("/")[-1]
                            _LOGGER.info("Home created successfully with ID: %s", home_id)
                            return Home(id=home_id, name=name, url=location)
                    
                    data = await response.json()
                    _LOGGER.info("Home created successfully: %s", data.get("id"))
                    return Home(
                        id=data.get("id", ""),
                        name=data.get("name", name),
                        url=data.get("url", ""),
                    )
                
                text = await response.text()
                _LOGGER.error("Failed to create home: %s %s", response.status, text)
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to create home: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in create_home: %s", e)
            raise
        raise RuntimeError("Failed to create home")

    async def rename_home(self, home: Home, new_name: str) -> bool:
        """
        Rename an existing home.

        Args:
            home (Home): The home to rename.
            new_name (str): New name for the home.

        Returns:
            bool: True if successful.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}"
        payload = {"name": new_name}

        session = await self.client.get_client()
        try:
            headers = {
                **self.client.headers,
                "Content-Type": "application/json; charset=UTF-8",
            }
            async with session.patch(url, headers=headers, json=payload) as response:
                if response.status in (200, 204):
                    _LOGGER.info("Home %s renamed to: %s", home.id, new_name)
                    return True
                
                text = await response.text()
                _LOGGER.error("Failed to rename home: %s %s", response.status, text)
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to rename home: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in rename_home: %s", e)
            raise
        return False

    async def delete_home(self, home: Home) -> bool:
        """
        Delete a home.

        Args:
            home (Home): The home to delete.

        Returns:
            bool: True if successful.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}"

        session = await self.client.get_client()
        try:
            async with session.delete(url, headers=self.client.headers) as response:
                if response.status == 204:
                    _LOGGER.info("Home %s deleted successfully.", home.id)
                    return True
                
                text = await response.text()
                _LOGGER.error("Failed to delete home: %s %s", response.status, text)
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to delete home: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in delete_home: %s", e)
            raise
        return False

    async def switch_home(self, home: Home) -> bool:
        """
        Switch to/select a home as active.

        Args:
            home (Home): The home to switch to.

        Returns:
            bool: True if successful.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}"

        session = await self.client.get_client()
        try:
            async with session.put(url, headers=self.client.headers) as response:
                if response.status in (200, 204):
                    _LOGGER.info("Switched to home: %s", home.id)
                    return True
                
                text = await response.text()
                _LOGGER.error("Failed to switch home: %s %s", response.status, text)
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to switch home: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in switch_home: %s", e)
            raise
        return False

    # =========================================================================
    # HOME INVITE OPERATIONS
    # =========================================================================

    async def get_invites(self, home: Home) -> List[HomeInvite]:
        """
        Get all invitations for a home.

        Args:
            home (Home): The home to get invites for.

        Returns:
            List[HomeInvite]: List of home invitations.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/invites"

        session = await self.client.get_client()
        try:
            async with session.get(url, headers=self.client.headers) as response:
                response.raise_for_status()
                data = await response.json()
                invites = [
                    HomeInvite.from_dict(invite)
                    for invite in data.get("item", [])
                ]
                _LOGGER.info("Found %d invites for home %s", len(invites), home.id)
                return invites
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to get invites: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in get_invites: %s", e)
            raise

    async def send_invite(
        self,
        home: Home,
        email: str,
        label: str,
        role: HomeInviteRole = HomeInviteRole.MEMBER,
    ) -> bool:
        """
        Send a home invitation.

        Args:
            home (Home): The home to invite to.
            email (str): Email address of the invitee.
            label (str): Display name for the invitee.
            role (HomeInviteRole): Role to assign (default: MEMBER).

        Returns:
            bool: True if successful.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/invites"
        payload = {
            "email": email,
            "label": label,
            "role": role.value,
        }

        session = await self.client.get_client()
        try:
            headers = {
                **self.client.headers,
                "Content-Type": "application/json; charset=UTF-8",
            }
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status in (200, 201, 204):
                    _LOGGER.info("Invite sent to %s for home %s", email, home.id)
                    return True
                
                text = await response.text()
                _LOGGER.error("Failed to send invite: %s %s", response.status, text)
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to send invite: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in send_invite: %s", e)
            raise
        return False

    async def accept_invite(
        self, home: Home, invite_token: str, email: str
    ) -> bool:
        """
        Accept a home invitation.

        Args:
            home (Home): The home being invited to.
            invite_token (str): The invitation token.
            email (str): Email address of the user accepting.

        Returns:
            bool: True if successful.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/invites/{invite_token}"
        payload = {"email": email}

        session = await self.client.get_client()
        try:
            headers = {
                **self.client.headers,
                "Content-Type": "application/json; charset=UTF-8",
            }
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status in (200, 204):
                    _LOGGER.info("Invite %s accepted for home %s", invite_token, home.id)
                    return True
                
                text = await response.text()
                _LOGGER.error("Failed to accept invite: %s %s", response.status, text)
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to accept invite: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in accept_invite: %s", e)
            raise
        return False

    async def resend_invite(self, home: Home, invite_token: str) -> bool:
        """
        Resend a home invitation.

        Args:
            home (Home): The home the invite belongs to.
            invite_token (str): The invitation token to resend.

        Returns:
            bool: True if successful.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/invites/{invite_token}"

        session = await self.client.get_client()
        try:
            async with session.put(url, headers=self.client.headers) as response:
                if response.status in (200, 204):
                    _LOGGER.info("Invite %s resent for home %s", invite_token, home.id)
                    return True
                
                text = await response.text()
                _LOGGER.error("Failed to resend invite: %s %s", response.status, text)
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to resend invite: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in resend_invite: %s", e)
            raise
        return False

    async def update_invite_label(
        self, home: Home, invite_token: str, new_label: str
    ) -> bool:
        """
        Update the label of a home invitation.

        Args:
            home (Home): The home the invite belongs to.
            invite_token (str): The invitation token.
            new_label (str): New label for the invite.

        Returns:
            bool: True if successful.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/invites/{invite_token}"
        payload = {"label": new_label}

        session = await self.client.get_client()
        try:
            headers = {
                **self.client.headers,
                "Content-Type": "application/json; charset=UTF-8",
            }
            async with session.patch(url, headers=headers, json=payload) as response:
                if response.status in (200, 204):
                    _LOGGER.info(
                        "Invite %s label updated to: %s", invite_token, new_label
                    )
                    return True
                
                text = await response.text()
                _LOGGER.error(
                    "Failed to update invite label: %s %s", response.status, text
                )
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to update invite label: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in update_invite_label: %s", e)
            raise
        return False

    async def delete_invite(self, home: Home, invite_token: str) -> bool:
        """
        Delete/reject a home invitation.

        Args:
            home (Home): The home the invite belongs to.
            invite_token (str): The invitation token to delete.

        Returns:
            bool: True if successful.

        Raises:
            aiohttp.ClientResponseError: If the HTTP request fails.
        """
        await self.client.ensure_token_valid()
        url = f"{self.config.base_url}/api/homes/{home.id}/invites/{invite_token}"

        session = await self.client.get_client()
        try:
            async with session.delete(url, headers=self.client.headers) as response:
                if response.status == 204:
                    _LOGGER.info("Invite %s deleted from home %s", invite_token, home.id)
                    return True
                
                text = await response.text()
                _LOGGER.error("Failed to delete invite: %s %s", response.status, text)
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Failed to delete invite: %s %s", e.status, e.message)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in delete_invite: %s", e)
            raise
        return False
