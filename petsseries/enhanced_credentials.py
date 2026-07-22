"""
Enhanced device credentials retrieval using Philips authentication.

This module provides a streamlined way to get device information including
Tuya deviceId from Philips API, with localKey retrieval attempted from Tuya.
"""

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Tuple

from .api import PetsSeriesClient
from .exceptions import PetsSeriesAPIError
from .tuya_cloud import TuyaCloudClient, get_tuya_credentials_from_philips

_LOGGER = logging.getLogger(__name__)


async def get_device_info_from_philips(client: PetsSeriesClient) -> List[Dict]:
    """
    Get device information from Philips API including Tuya deviceId.

    Args:
        client: An initialized PetsSeriesClient instance

    Returns:
        List of device information with Tuya deviceIds
    """
    devices_info = []

    try:
        # Get all homes
        homes = await client.get_homes()

        for home in homes:
            # Get devices for each home
            devices = await client.get_devices(home)

            for device in devices:
                device_info = {
                    "philips_id": device.id,
                    "name": device.name,
                    "tuya_device_id": device.vendor_id,  # This is the Tuya deviceId
                    "product_ctn": device.product_ctn,
                    "product_id": device.product_id,
                    "home_id": home.id,
                    "home_name": home.name,
                }
                devices_info.append(device_info)

        return devices_info

    except Exception as e:
        _LOGGER.error(f"Failed to get device info from Philips: {e}")
        raise


async def get_complete_device_credentials(
    email_code: Optional[str] = None,
    email: Optional[str] = None,
    tokens_file: str = "tokens.json",
    country_code: str = "1",
    tuya_region: str = "eu"
) -> Tuple[List[Dict], Optional[str]]:
    """
    Get complete device credentials including Tuya localKey if possible.

    This function:
    1. Authenticates with Philips (using email code or saved tokens)
    2. Gets device list from Philips API (includes Tuya deviceId as vendorId)
    3. Attempts to get Tuya credentials (localKey) using the Philips token
    4. Combines all information

    Args:
        email: Account email used when requesting an OTP
        email_code: Optional 6-digit code from email for authentication
        tokens_file: Path to save/load authentication tokens
        country_code: Country dial code (e.g. "1" US, "44" UK, "31" NL)
        tuya_region: Tuya API region (eu, us, cn, in)

    Returns:
        Tuple of (credentials_list, error_message)
        If successful, error_message is None

    Example:
        >>> credentials, error = await get_complete_device_credentials(email_code="123456")
        >>> if not error:
        ...     for device in credentials:
        ...         print(f"Device: {device['name']}")
        ...         print(f"  Tuya Device ID: {device['tuya_device_id']}")
        ...         print(f"  Local Key: {device.get('local_key', 'Not available')}")
    """
    client = PetsSeriesClient(token_file=tokens_file)

    try:
        # Initialize client (handle authentication)
        if email_code:
            if not email:
                return [], "email is required when email_code is supplied"
            await client.auth.login_with_email_code(email, email_code)
            await client.auth.save_tokens()
            await client.initialize()
        else:
            # Use existing tokens
            await client.initialize()

        # Get device info from Philips
        _LOGGER.info("Fetching device information from Philips API...")
        philips_devices = await get_device_info_from_philips(client)

        if not philips_devices:
            return [], "No devices found in your Philips account"

        _LOGGER.info(f"Found {len(philips_devices)} devices from Philips")

        # Try to get Tuya credentials
        tuya_credentials: List[Dict] = []
        tuya_error = None

        if client.auth.id_token:
            _LOGGER.info("Attempting to fetch Tuya credentials...")
            tuya_credentials, tuya_error = await get_tuya_credentials_from_philips(
                client.auth.id_token,
                [device["tuya_device_id"] for device in philips_devices if device.get("tuya_device_id")],
                country_code=country_code,
                region=tuya_region
            )

            if tuya_error:
                _LOGGER.warning(f"Could not fetch Tuya credentials: {tuya_error}")

        # Combine Philips and Tuya information
        combined_credentials = []
        tuya_by_id = {cred['device_id']: cred for cred in tuya_credentials}

        for philips_device in philips_devices:
            tuya_device_id = philips_device['tuya_device_id']
            tuya_info = tuya_by_id.get(tuya_device_id, {})

            combined = {
                **philips_device,
                'local_key': tuya_info.get('local_key', ''),
                'ip': tuya_info.get('ip', ''),
                'mac': tuya_info.get('mac', ''),
                'uuid': tuya_info.get('uuid', ''),
                'is_online': tuya_info.get('is_online', False),
                'category': tuya_info.get('category', ''),
            }

            combined_credentials.append(combined)

        # Prepare return message
        if tuya_error and not tuya_credentials:
            error_msg = (
                f"Retrieved device IDs from Philips but could not get localKeys from Tuya: {tuya_error}. "
                "You'll need to obtain localKeys manually (see documentation)."
            )
        else:
            error_msg = None

        return combined_credentials, error_msg

    finally:
        await client.close()


async def save_credentials_to_file(
    credentials: List[Dict],
    output_file: str = "device_credentials.json"
) -> None:
    """
    Save device credentials to a JSON file.

    Args:
        credentials: List of device credential dictionaries
        output_file: Path to save the credentials
    """
    with open(output_file, 'w') as f:
        json.dump(credentials, f, indent=2)
    _LOGGER.info(f"Saved {len(credentials)} device credentials to {output_file}")


def format_credentials_for_display(credentials: List[Dict]) -> str:
    """
    Format credentials for human-readable display.

    Args:
        credentials: List of device credential dictionaries

    Returns:
        Formatted string for display
    """
    output = []
    output.append(f"\nFound {len(credentials)} device(s):\n")

    for i, device in enumerate(credentials, 1):
        output.append(f"Device {i}: {device.get('name', 'Unknown')}")
        output.append(f"  Philips ID:     {device.get('philips_id', 'N/A')}")
        output.append(f"  Tuya Device ID: {device.get('tuya_device_id', 'N/A')}")
        output.append(f"  Local Key:      {device.get('local_key') or 'Not available - see notes below'}")
        output.append(f"  IP Address:     {device.get('ip') or 'Not available'}")
        output.append(f"  Product:        {device.get('product_ctn', 'N/A')}")
        output.append(f"  Online:         {device.get('is_online', 'Unknown')}")
        output.append(f"  Home:           {device.get('home_name', 'N/A')}")
        output.append("")

    # Add notes if any device is missing localKey
    if any(not device.get('local_key') for device in credentials):
        output.append("-" * 60)
        output.append("NOTE: Some devices are missing localKey.")
        output.append("To obtain localKeys manually, you can:")
        output.append("  1. Use the Tuya IoT Platform (https://iot.tuya.com)")
        output.append("  2. Run tinytuya wizard: python -m tinytuya wizard")
        output.append("  3. Extract via the mobile API")
        output.append("-" * 60)

    return "\n".join(output)


# Convenience function for command-line usage
async def main():
    """Example usage of the enhanced credentials retrieval."""
    import sys

    # Check if email code is provided as argument
    email_code = sys.argv[1] if len(sys.argv) > 1 else None

    print("Philips Pet Series - Device Credentials Retrieval")
    print("=" * 50)

    if not email_code and not os.path.exists("tokens.json"):
        print("\nUsage:")
        print("  python enhanced_credentials.py [EMAIL_CODE]")
        print("\nFirst time: provide the 6-digit code from your email")
        print("Subsequent runs: just run without arguments to use saved tokens")
        return

    credentials, error = await get_complete_device_credentials(
        email_code=email_code,
        country_code="1",  # your country dial code
        tuya_region="eu"
    )

    if credentials:
        print(format_credentials_for_display(credentials))

        # Save to file
        await save_credentials_to_file(credentials, "device_credentials.json")

        if error:
            print(f"\n⚠️  Warning: {error}")
    else:
        print(f"\n❌ Error: {error}")


if __name__ == "__main__":
    import os
    asyncio.run(main())
