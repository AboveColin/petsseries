#!/usr/bin/env python3
"""
Example script to obtain Tuya device credentials (localKey, deviceId, IP)
using Philips OAuth credentials.

Usage:
    # Using existing tokens (if you have tokens.json):
    python get_device_credentials.py
    
    # Using a specific access token:
    python get_device_credentials.py --token "your_access_token_here"
    
    # Specify your country dial code (e.g. 1=US, 44=UK, 31=NL):
    python get_device_credentials.py --country 1  # For US
    
    # Specify region (default is eu):
    python get_device_credentials.py --region us
"""

import argparse
import asyncio
import json
import logging
import sys
from typing import List, Dict

from petsseries import (
    PetsSeriesClient,
    get_tuya_credentials_from_philips,
    AuthManager,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
_LOGGER = logging.getLogger(__name__)


def display_credentials(credentials: List[Dict]) -> None:
    """Display device credentials in a formatted way."""
    print(f"\nFound {len(credentials)} device(s) with Tuya credentials:\n")
    
    for i, device in enumerate(credentials, 1):
        print(f"Device {i}:")
        print(f"  Name:       {device.get('name', 'N/A')}")
        print(f"  Device ID:  {device.get('device_id', 'N/A')}")
        print(f"  Local Key:  {device.get('local_key', 'N/A')}")
        print(f"  IP Address: {device.get('ip', 'N/A') or 'Not available'}")
        print(f"  Product ID: {device.get('product_id', 'N/A')}")
        print(f"  UUID:       {device.get('uuid', 'N/A')}")
        print(f"  MAC:        {device.get('mac', 'N/A')}")
        print(f"  Category:   {device.get('category', 'N/A')}")
        print(f"  Online:     {device.get('is_online', 'N/A')}")
        print()
    
    # Generate usage examples
    print("=" * 60)
    print("USAGE EXAMPLES")
    print("=" * 60)
    
    print("\n1. Using with tinytuya:")
    for device in credentials:
        if device.get("local_key") and device.get("device_id"):
            ip = device.get("ip") or "<device_ip>"
            print(f"\n# {device.get('name', 'Device')}")
            print("import tinytuya")
            print(f"device = tinytuya.Device(")
            print(f"    dev_id='{device['device_id']}',")
            print(f"    address='{ip}',  # You may need to find this on your network")
            print(f"    local_key='{device['local_key']}',")
            print(f"    version=3.4")
            print(f")")
            print("status = device.status()")
            print("print(status)")
            break
    
    print("\n2. Using with Home Assistant:")
    print("\nAdd these to your configuration.yaml under 'tuya:' section:")
    for device in credentials[:2]:  # Show max 2 examples
        if device.get("local_key") and device.get("device_id"):
            print(f"\n  - host: <device_ip>  # Find this on your network")
            print(f"    device_id: {device['device_id']}")
            print(f"    local_key: {device['local_key']}")
            print(f"    friendly_name: {device.get('name', 'Device')}")
            print(f"    protocol_version: \"3.4\"")


async def get_credentials_from_client() -> List[Dict]:
    """Get credentials using PetsSeriesClient."""
    client = PetsSeriesClient()
    
    try:
        await client.initialize()
        
        # Get Philips ID token
        if not client.auth.id_token:
            _LOGGER.error("No ID token available. Please authenticate first.")
            return []
        
        # Get Tuya credentials
        credentials, error = await get_tuya_credentials_from_philips(
            client.auth.id_token,
            country_code="1",  # your country dial code
            region="eu"
        )
        
        if error:
            _LOGGER.error(f"Failed to get Tuya credentials: {error}")
            return []
        
        return credentials
        
    finally:
        await client.close()


async def get_credentials_with_token(token: str, country: str, region: str) -> List[Dict]:
    """Get credentials using a specific token."""
    credentials, error = await get_tuya_credentials_from_philips(
        token,
        country_code=country,
        region=region
    )
    
    if error:
        _LOGGER.error(f"Failed to get Tuya credentials: {error}")
        return []
    
    return credentials


async def main():
    parser = argparse.ArgumentParser(
        description="Get Tuya device credentials using Philips OAuth"
    )
    parser.add_argument(
        "--token",
        help="Philips access token or ID token to use directly"
    )
    parser.add_argument(
        "--country",
        default="1",
        help="Country dial code (e.g. 1=US, 44=UK, 31=NL)"
    )
    parser.add_argument(
        "--region",
        default="eu",
        choices=["eu", "us", "cn", "in"],
        help="Tuya API region (default: eu)"
    )
    parser.add_argument(
        "--output",
        help="Save credentials to JSON file"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Get credentials
    if args.token:
        _LOGGER.info(f"Using provided token for region {args.region}")
        credentials = await get_credentials_with_token(
            args.token, 
            args.country, 
            args.region
        )
    else:
        _LOGGER.info("Using PetsSeriesClient with existing authentication")
        credentials = await get_credentials_from_client()
    
    if not credentials:
        print("\nNo devices found or failed to retrieve credentials.")
        print("\nTroubleshooting tips:")
        print("1. Make sure you have valid Philips OAuth tokens")
        print("2. Try different country codes (1 for US, 31 for NL, 44 for UK)")
        print("3. Try different regions (eu, us, cn, in)")
        print("4. Check if your devices show up in the Philips Pet Series app")
        return
    
    # Display results
    display_credentials(credentials)
    
    # Save to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(credentials, f, indent=2)
        print(f"\nCredentials saved to: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())