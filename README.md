# Unofficial PetsSeries API Client

_Disclaimer: This is an unofficial Python client for the PetsSeries API. It is not affiliated with, endorsed by, or in any way connected to the official PetsSeries, Versuni or Philips companies._

## Introduction
The Unofficial PetsSeries API Client is a Python library designed to interact with the PetsSeries backend services. It provides asynchronous methods to manage user information, homes, devices, meals, events, and more. This client handles authentication, token refreshing, and provides a convenient interface for integrating PetsSeries functionalities into your Python applications.

## Features
- **Authentication Management:** Handles access and refresh tokens, including automatic refreshing when expired.
- **Comprehensive API Coverage:** Methods to interact with user info, homes, devices, meals, events, and device settings.
- **Event Parsing:** Automatically parses different event types into structured Python objects.
- **Easy Integration:** Simple initialization and usage patterns for quick integration into projects.

## Features to be Added
- **Schedule Management:** Methods to manage schedules
- **Camera Feed Access:** Methods to access camera feeds
- **Food Dispenser Control:** Methods to control food dispensers

(feel free to PR if you manage to implement any of these features)

## Installation
Ensure you have Python 3.10 or higher installed. You can install the package using pip:

```bash
pip install -r requirements.txt
```

## Authentication
This client uses OAuth2 tokens (access_token and refresh_token) to authenticate with the PetsSeries API. Follow the steps below to obtain and set up your tokens.

### Obtaining Tokens
1. Login via Web Interface:

    - Navigate to [PetsSeries Appliance Login](https://www.home.id/find-appliance).
    - Select a PetsSeries product (Starts with PAW) and log in with your credentials.

2. Retrieve Tokens:

    - After logging in, you will be redirected to a "Thanks for your purchase" screen.
    - Open your browser's developer tools (usually by pressing F12 or Ctrl+Shift+I).
    - Go to the Application tab and inspect the cookies.
    - Locate and copy the cc-access-token and cc-refresh-token from the cookies.

3. Provide Tokens to the Client:

    - You can provide the access_token and refresh_token when initializing the client. These tokens will be saved to tokens.json for future use.

### Example Initialization with Tokens
```python
import asyncio
from petsseries import PetsSeriesClient

async def main():
    client = PetsSeriesClient(
        access_token="your_access_token_here",
        refresh_token="your_refresh_token_here"
    )
    await client.initialize()
    # Your code here

asyncio.run(main())
```
After the first run, the tokens will be saved automatically, and you won't need to provide them again unless they are invalidated.

## Usage
### Initialization
Initialize the PetsSeriesClient with optional access_token and refresh_token. If tokens are not provided, ensure that tokens.json exists with valid tokens.

```python
import asyncio
from petsseries import PetsSeriesClient

async def initialize_client():
    async with PetsSeriesClient() as client:
        await client.initialize()
        # Use the client for API calls

asyncio.run(initialize_client())
```
### Fetching Data
The client provides various methods to fetch data from the PetsSeries API.

#### Get User Info
```python
user = await client.get_user_info()
print(user.name, user.email)
```
#### Get Homes
```python
homes = await client.get_homes()
for home in homes:
    print(home.name)
```

#### Get Devices
```python
for home in homes:
    devices = await client.get_devices(home)
    for device in devices:
        print(device.name, device.id)
```
### Get Events
```python
from datetime import datetime
from pytz import timezone

from_date = datetime(2024, 9, 27, tzinfo=timezone("Europe/Amsterdam"))
to_date = datetime(2024, 9, 28, tzinfo=timezone("Europe/Amsterdam"))

events = await client.get_events(home, from_date, to_date)
for event in events:
    print(event)
```

### Managing Devices
You can manage device settings such as powering devices on/off and toggling motion notifications.

#### Device Power
```python
result = await client.power_on_device(home, device_id)
if result:
    print("Device powered on successfully.")

result = await client.power_off_device(home, device_id)
if result:
    print("Device powered off successfully.")

result = await client.toggle_device_power(home, device_id)
if result:
    print("Device power toggled successfully.")
```
#### Motion Notifications
```python
result = await client.enable_motion_notifications(home, device_id)
if result:
    print("Motion notifications enabled successfully.")

result = await client.disable_motion_notifications(home, device_id)
if result:
    print("Motion notifications disabled successfully.")

result = await client.toggle_motion_notifications(home, device_id)
if result:
    print("Motion notifications toggled successfully.")
```

### Example
Here's a complete example demonstrating how to initialize the client, fetch user info, homes, devices, and manage device settings.

```python
import asyncio
from petsseries import PetsSeriesClient

async def main():
    async with PetsSeriesClient(
        access_token="your_access_token_here",
        refresh_token="your_refresh_token_here"
    ) as client:
        await client.initialize()
        
        # Fetch user info
        user = await client.get_user_info()
        print(f"User: {user.name} ({user.email})")
        
        # Fetch homes
        homes = await client.get_homes()
        for home in homes:
            print(f"Home: {home.name}")
            
            # Fetch devices in home
            devices = await client.get_devices(home)
            for device in devices:
                print(f"Device: {device.name} (ID: {device.id})")
                
                # Power off device
                success = await client.power_off_device(home, device.id)
                if success:
                    print(f"{device.name} powered off.")
                
                # Toggle motion notifications
                success = await client.toggle_motion_notifications(home, device.id)
                if success:
                    print(f"Motion notifications toggled for {device.name}.")
                
                from_date = dt.datetime(2021, 9, 27, tzinfo=dt.timezone(dt.timedelta(hours=2)))
                to_date = dt.datetime(2100, 9, 28, tzinfo=dt.timezone(dt.timedelta(hours=2)))
                print(from_date, to_date)

                events = await client.get_events(home, from_date, to_date)
                # Possible eventTypes are: ["motion_detected", "meal_dispensed", "meal_upcoming", "food_level_low"]
                for event in events:
                    if event.type == "meal_dispensed":
                        logger.info(f"Event: {event}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Contributing
Contributions are more than welcome!


__Disclaimer:__ This project is not affiliated with PetsSeries or Versuni. It is developed independently and is intended for personal use. Use it responsibly and respect the terms of service of the official PetsSeries API.
