# tuya_cloud.py

"""
Tuya Cloud API integration for retrieving device credentials.

This module provides functionality to authenticate with Tuya Cloud using Philips OAuth tokens
and retrieve device information including localKey, deviceId, and IP addresses.
"""

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from typing import Dict, List, Optional, Tuple

import aiohttp

from .exceptions import PetsSeriesAPIError, PetsSeriesNetworkError
from .native_signer import NativeTuyaSigner
from .tuya_mobile import TuyaMobileClient

_LOGGER = logging.getLogger(__name__)


class TuyaCloudClient:
    """Client for interacting with Tuya Cloud API to retrieve device credentials."""
    
    # Tuya API configuration for Philips integration
    CLIENT_ID = "7gqdt8hrgamaxeksxchg"
    CLIENT_SECRET = "55v8jwqadnkpmdxtr4ep9yxefm7csgr7"
    
    # Default session parameters
    DEFAULT_CH_KEY = "93cff209"  # From successful requests
    
    # BMP secrets extracted from the app's asset files
    BMP_SECRETS = {
        "fixed_key": "088c9fb102bd6e7b68e5e789d8907c74",  # SHA256 of fixed_key.bmp pixel data
        "t_s": "d7a600416c69cb4ad1190f3195954d6e"          # SHA256 of t_s.bmp pixel data
    }
    
    # Regional API endpoints
    API_ENDPOINTS = {
        "eu": "https://a1.tuyaeu.com/api.json",
        "us": "https://a1.tuyaus.com/api.json",
        "cn": "https://a1.tuyacn.com/api.json",
        "in": "https://a1.tuyain.com/api.json",
    }
    
    def __init__(self, region: str = "eu", ch_key: Optional[str] = None, signer: Optional[NativeTuyaSigner] = None):
        """
        Initialize the Tuya Cloud Client.
        
        Args:
            region: API region (eu, us, cn, in)
            ch_key: Channel key (optional, will use default if not provided)
        """
        self.region = region
        self.base_url = self.API_ENDPOINTS.get(region, self.API_ENDPOINTS["eu"])
        self.session_id = None
        self.user_id = None
        self.ch_key = ch_key or self.DEFAULT_CH_KEY
        self.signer = signer
        self._session = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
    
    def _md5_hex(self, s: str) -> str:
        """Calculate MD5 hash of string."""
        return hashlib.md5(s.encode('utf-8')).hexdigest()
    
    def _sha256_hex(self, s: str) -> str:
        """Calculate SHA256 hash of string."""
        return hashlib.sha256(s.encode('utf-8')).hexdigest()
    
    def _get_app_certificate_sha256(self) -> str:
        """Generate app certificate SHA256 hash for Philips app."""
        # This represents the Philips app's signing certificate hash
        cert_data = f"philips_pet_series_{self.CLIENT_ID}".encode()
        return hashlib.sha256(cert_data).hexdigest()
    
    def _generate_signature_key(self) -> str:
        """
        Generate the complete Tuya signature key using the format:
        [app_certificate_sha256]_[bmp_secret]_[app_secret]
        """
        cert_hash = self._get_app_certificate_sha256()
        bmp_secret = self.BMP_SECRETS["fixed_key"] + self.BMP_SECRETS["t_s"]
        return f"{cert_hash}_{bmp_secret}_{self.CLIENT_SECRET}"
    
    def _get_post_data_digest(self, post_data_str: str) -> str:
        """
        Calculate post data digest using Tuya's specific algorithm.
        MD5 hash with byte swapping: ABCD -> BADC
        """
        if not post_data_str:
            return ""
        
        m = self._md5_hex(post_data_str)
        if len(m) != 32:
            return m
        
        # Swap bytes: A B C D -> B A D C
        return m[8:16] + m[0:8] + m[24:32] + m[16:24]
    
    def _sign_request(self, params: Dict, post_data_str: Optional[str] = None) -> str:
        """
        Sign API request using Tuya's signature algorithm.
        
        Args:
            params: Request parameters
            post_data_str: JSON string of business parameters
            
        Returns:
            Request signature
        """
        # Keys that participate in signing
        sign_keys = {
            'a', 'v', 'lat', 'lon', 'lang', 'deviceId', 'appVersion', 
            'ttid', 'isH5', 'h5Token', 'os', 'clientId', 'postData', 
            'time', 'requestId', 'et', 'n4h5', 'sid', 'chKey', 'sp',
            'channel', 'osSystem', 'nd', 'sdkVersion', 'bizDM', 'platform',
            'timeZoneId', 'cp', 'deviceCoreVersion', 'bizData'
        }
        
        sign_map = {}
        for k, v in params.items():
            if k in sign_keys:
                sign_map[k] = str(v)
        
        if post_data_str:
            sign_map['postData'] = self._get_post_data_digest(post_data_str)
        
        # Sort keys and build signature string
        sorted_keys = sorted(sign_map.keys())
        sign_parts = []
        for k in sorted_keys:
            val = sign_map.get(k)
            if val is not None:
                sign_parts.append(f"{k}={val}")
        
        merged = "||".join(sign_parts)
        
        # Generate the proper signature key with BMP secrets
        if self.signer:
            return self.signer.sign(merged)
        signature_key = self._generate_signature_key()
        
        # Use HMAC-SHA256 with the complete signature key
        return hmac.new(
            signature_key.encode('utf-8'),
            merged.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def _call_api(self, action: str, business_params: Optional[Dict] = None) -> Dict:
        """
        Call Tuya API endpoint.
        
        Args:
            action: API action to call
            business_params: Business parameters for the API call
            
        Returns:
            API response data
            
        Raises:
            PetsSeriesAPIError: If API call fails
        """
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        ts = str(int(time.time()))
        unique_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        
        # Base parameters that work for both authentication and API calls
        params = {
            "a": action,
            "v": "1.0",
            "clientId": self.CLIENT_ID,
            "deviceId": unique_id,
            "os": "Android",
            "time": ts,
            "requestId": request_id,
            "ttid": "android",
            "et": "3",
            "appVersion": "2.1.0",
            "lang": os.environ.get("PETSERIES_TUYA_LANG") or "en",
        }
        
        # Add additional parameters for WebRTC config calls
        if action == "smartlife.m.rtc.config.get":
            params.update({
                "channel": "sdk",
                "chKey": self.ch_key,
                "osSystem": "14",
                "nd": "1",
                "sdkVersion": "6.7.0",
                "bizDM": "ipc",
                "platform": "android",
                "timeZoneId": os.environ.get("PETSERIES_TUYA_TIMEZONE") or "UTC",
                "cp": "gzip",
                "deviceCoreVersion": "6.7.0",
                "bizData": json.dumps({
                    "brand": "android",
                    "customDomainSupport": "1",
                    "nd": "1",
                    "sdkInt": "34"
                }, separators=(',', ':'))
            })
        
        if self.session_id:
            params["sid"] = self.session_id
        
        post_data_str = None
        if business_params:
            post_data_str = json.dumps(business_params, separators=(',', ':'))
            params["postData"] = post_data_str
        
        signature = self._sign_request(params, post_data_str)
        params["sign"] = signature
        
        headers = {
            "User-Agent": "Ty-SDK/3.14.0 (Android; 10; Pixel 4)",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        try:
            async with self._session.post(
                self.base_url, 
                data=params, 
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                result = await response.json()
                
                if not result.get("success", False):
                    error_msg = result.get("errorMsg", "Unknown error")
                    error_code = result.get("errorCode", "")
                    _LOGGER.error(f"Tuya API error: {error_code} - {error_msg}")
                    raise PetsSeriesAPIError(f"Tuya API error: {error_msg}")
                
                return result.get("result", {})
        
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Network error calling Tuya API: {e}")
            raise PetsSeriesNetworkError(f"Failed to call Tuya API: {e}")
        except json.JSONDecodeError as e:
            _LOGGER.error(f"Failed to parse Tuya API response: {e}")
            raise PetsSeriesAPIError(f"Invalid response from Tuya API: {e}")
    
    async def login_with_philips_token(
        self, 
        id_token: str, 
        country_code: str = "1"
    ) -> bool:
        """
        Login to Tuya using Philips OAuth ID token.
        
        Args:
            id_token: Philips OAuth ID token
            country_code: Country dial code (e.g. "1" US, "44" UK, "31" NL)
            
        Returns:
            True if login successful
            
        Raises:
            PetsSeriesAPIError: If login fails
        """
        business_params = {
            "countryCode": country_code,
            "accessToken": id_token,
            "type": "jwt",
            "extraInfo": json.dumps({"platform": "PhilipsDA"}, separators=(',', ':')),
            "extInfo": json.dumps({"group": 1}, separators=(',', ':'))
        }
        
        _LOGGER.info("Attempting Tuya login with Philips token...")
        result = await self._call_api("thing.m.user.third.login", business_params)
        
        self.session_id = result.get("sid")
        self.user_id = result.get("uid")
        
        if not self.session_id:
            raise PetsSeriesAPIError("Failed to get session ID from Tuya login")
        
        _LOGGER.info(f"Successfully logged in to Tuya. User ID: {self.user_id}")
        return True
    
    async def get_webrtc_config(self, device_id: str) -> Dict:
        """
        Get WebRTC configuration for a camera device, including localKey.
        
        This is the method the Philips app actually uses to get camera credentials.
        The response includes localKey, p2pConfig, and all necessary connection info.
        
        Args:
            device_id: Tuya device ID
            
        Returns:
            WebRTC configuration including localKey
            
        Raises:
            PetsSeriesAPIError: If not logged in or API call fails
        """
        if not self.session_id:
            raise PetsSeriesAPIError("Not logged in to Tuya. Call login_with_philips_token first.")
        
        business_params = {
            "devId": device_id
        }
        
        _LOGGER.info(f"Getting WebRTC config for device {device_id}...")
        result = await self._call_api("smartlife.m.rtc.config.get", business_params)
        
        return result
    
    async def get_device_list(self) -> List[Dict]:
        """
        Get list of devices from Tuya.
        
        Returns:
            List of device information dictionaries
            
        Raises:
            PetsSeriesAPIError: If not logged in or API call fails
        """
        if not self.session_id:
            raise PetsSeriesAPIError("Not logged in to Tuya. Call login_with_philips_token first.")
        
        _LOGGER.info("Fetching device list from Tuya...")
        result = await self._call_api("thing.m.device.list.token", {})
        
        devices = result.get("devices", [])
        _LOGGER.info(f"Found {len(devices)} devices")
        
        return devices
    
    async def get_device_keys(self, device_ids: List[str]) -> Dict[str, str]:
        """
        Get local keys for devices.
        
        Args:
            device_ids: List of device IDs to get keys for
            
        Returns:
            Dictionary mapping device ID to local key
            
        Raises:
            PetsSeriesAPIError: If not logged in or API call fails
        """
        if not self.session_id:
            raise PetsSeriesAPIError("Not logged in to Tuya. Call login_with_philips_token first.")
        
        if not device_ids:
            return {}
        
        _LOGGER.info(f"Fetching local keys for {len(device_ids)} devices...")
        
        # The API might support batch requests
        business_params = {
            "devIds": device_ids
        }
        
        try:
            result = await self._call_api("thing.m.device.key.get", business_params)
            
            # Parse result - format may vary
            keys = {}
            if isinstance(result, dict):
                for dev_id, info in result.items():
                    if isinstance(info, dict) and 'localKey' in info:
                        keys[dev_id] = info['localKey']
                    elif isinstance(info, str):
                        # Sometimes the API returns the key directly
                        keys[dev_id] = info
            elif isinstance(result, list):
                # Alternative format
                for item in result:
                    if isinstance(item, dict) and 'devId' in item and 'localKey' in item:
                        keys[item['devId']] = item['localKey']
            
            _LOGGER.info(f"Retrieved {len(keys)} local keys")
            return keys
            
        except PetsSeriesAPIError:
            # If batch fails, try individual requests
            _LOGGER.warning("Batch key request failed, trying individual requests...")
            keys = {}
            for device_id in device_ids:
                try:
                    result = await self._call_api("thing.m.device.key.get", {"devId": device_id})
                    if 'localKey' in result:
                        keys[device_id] = result['localKey']
                except Exception as e:
                    _LOGGER.error(f"Failed to get key for device {device_id}: {e}")
            
            return keys
    
    async def get_device_credentials_with_webrtc(self, device_ids: List[str]) -> List[Dict]:
        """
        Get device credentials using WebRTC config endpoint.
        
        This is the method the Philips app uses to get camera credentials including localKey.
        
        Args:
            device_ids: List of Tuya device IDs to get credentials for
            
        Returns:
            List of device credential dictionaries with:
            - device_id: Tuya device ID
            - local_key: Local encryption key
            - p2p_config: P2P configuration for camera streaming
            - webrtc_config: Complete WebRTC configuration
            
        Raises:
            PetsSeriesAPIError: If not logged in or API calls fail
        """
        credentials = []
        
        for device_id in device_ids:
            try:
                _LOGGER.info(f"Getting WebRTC config for device {device_id}...")
                webrtc_config = await self.get_webrtc_config(device_id)
                
                cred = {
                    "device_id": device_id,
                    "local_key": webrtc_config.get("localKey", ""),
                    "p2p_config": webrtc_config.get("p2pConfig", {}),
                    "webrtc_config": webrtc_config
                }
                
                if cred["local_key"]:
                    _LOGGER.info(f"Successfully retrieved localKey for device {device_id}")
                else:
                    _LOGGER.warning(f"No localKey found for device {device_id}")
                
                credentials.append(cred)
                
            except Exception as e:
                _LOGGER.error(f"Failed to get credentials for device {device_id}: {e}")
                # Still add entry with error info
                credentials.append({
                    "device_id": device_id,
                    "local_key": "",
                    "error": str(e)
                })
        
        return credentials
    
    async def get_device_credentials(self) -> List[Dict]:
        """
        Get complete device credentials including local keys.
        
        Returns:
            List of device credential dictionaries with:
            - device_id: Tuya device ID
            - local_key: Local encryption key
            - name: Device name
            - product_id: Product identifier
            - uuid: Device UUID
            - mac: MAC address
            - ip: IP address (if available)
            - is_online: Online status
            - category: Device category
            
        Raises:
            PetsSeriesAPIError: If not logged in or API calls fail
        """
        # Get device list
        devices = await self.get_device_list()
        
        if not devices:
            return []
        
        # Extract device IDs
        device_ids = [d.get("devId", d.get("id", "")) for d in devices]
        device_ids = [d for d in device_ids if d]  # Filter empty
        
        # Get local keys
        local_keys = await self.get_device_keys(device_ids)
        
        # Combine information
        credentials = []
        for device in devices:
            device_id = device.get("devId", device.get("id", ""))
            if not device_id:
                continue
            
            cred = {
                "device_id": device_id,
                "local_key": local_keys.get(device_id, ""),
                "name": device.get("name", ""),
                "product_id": device.get("productId", ""),
                "uuid": device.get("uuid", ""),
                "mac": device.get("mac", ""),
                "ip": device.get("ip", ""),
                "is_online": device.get("isOnline", False),
                "category": device.get("category", ""),
            }
            
            credentials.append(cred)
        
        return credentials


async def get_tuya_credentials_from_philips(
    philips_id_token: str,
    tuya_device_ids: List[str],
    country_code: str = "1",
    region: str = "eu",
    ch_key: Optional[str] = None
) -> Tuple[List[Dict], Optional[str]]:
    """
    Get Tuya device credentials using Philips OAuth token and WebRTC config endpoint.
    
    This uses the actual method the Philips app uses to retrieve localKeys.
    
    Args:
        philips_id_token: Philips OAuth ID token
        tuya_device_ids: List of Tuya device IDs (from Philips API vendor_id)
        country_code: Country dial code (e.g. "1" US, "44" UK, "31" NL)
        region: Tuya API region (eu, us, cn, in)
        ch_key: Channel key (optional, will use default if not provided)
        
    Returns:
        Tuple of (credentials_list, error_message)
        If successful, error_message is None
        If failed, credentials_list is empty and error_message contains the error
    """
    try:
        signer = None
        try:
            signer = NativeTuyaSigner.from_environment()
        except Exception as exc:
            _LOGGER.debug("Native Tuya signer is not configured: %s", exc)
        if signer is None:
            return [], "native Tuya signer is not configured"
        async with aiohttp.ClientSession() as session:
            client = TuyaMobileClient(signer, session)
            await client.login_with_philips_token(philips_id_token, country_code)
            return await client.get_local_keys(tuya_device_ids), None
            
    except Exception as e:
        _LOGGER.error("Failed to get Tuya credentials: %s", e)
        return [], str(e)


async def tuya_mobile_action_from_philips(
    philips_id_token: str,
    action: str,
    payload: Dict[str, Any],
    country_code: str = "1",
) -> Dict[str, Any]:
    """Execute an app-compatible Tuya mobile action with a Philips token."""
    signer = NativeTuyaSigner.from_environment()
    async with aiohttp.ClientSession() as session:
        client = TuyaMobileClient(signer, session)
        await client.login_with_philips_token(philips_id_token, country_code)
        return await client._call(action, payload)


async def get_tuya_credentials_from_philips_legacy(
    philips_id_token: str,
    country_code: str = "1",
    region: str = "eu"
) -> Tuple[List[Dict], Optional[str]]:
    """
    Legacy function to get Tuya device credentials using standard device list API.
    
    This method doesn't work for getting localKeys but is kept for compatibility.
    
    Args:
        philips_id_token: Philips OAuth ID token
        country_code: Country dial code (e.g. "1" US, "44" UK, "31" NL)
        region: Tuya API region (eu, us, cn, in)
        
    Returns:
        Tuple of (credentials_list, error_message)
        If successful, error_message is None
        If failed, credentials_list is empty and error_message contains the error
    """
    try:
        async with TuyaCloudClient(region=region) as client:
            # Login with Philips token
            await client.login_with_philips_token(philips_id_token, country_code)
            
            # Get device credentials
            credentials = await client.get_device_credentials()
            
            return credentials, None
            
    except Exception as e:
        _LOGGER.error("Failed to get Tuya credentials: %s", e)
        return [], str(e)
