""" 
Helper function to create an SSL context using certifi's CA bundle in a separate thread.
"""

import asyncio
import ssl
import logging

import certifi

_LOGGER = logging.getLogger(__name__)


async def create_ssl_context() -> ssl.SSLContext:
    """Create an SSL context using certifi's CA bundle in a separate thread."""
    return await asyncio.to_thread(ssl.create_default_context, cafile=certifi.where())
