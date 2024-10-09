![PyPI - Downloads](https://img.shields.io/pypi/dm/petsseries)
![PyPI - Downloads](https://img.shields.io/pypi/dd/petsseries)

# Unofficial PetsSeries API Client

_Disclaimer: This is an unofficial Python client for the PetsSeries API. It is not affiliated with, endorsed by, or in any way connected to the official PetsSeries, Versuni or Philips companies._

## Introduction
The Unofficial PetsSeries API Client is a Python library designed to interact with the PetsSeries backend services. It provides asynchronous methods to manage user information, homes, devices, meals, events, and more. This client handles authentication, token refreshing, and provides a convenient interface for integrating PetsSeries functionalities into your Python applications.

## Features
- **Authentication Management:** Handles access and refresh tokens, including automatic refreshing when expired.
- **Comprehensive API Coverage:** Methods to interact with user info, homes, devices, meals, events, and device settings.
- **Schedule Management:** Methods to manage schedules
- **Food Dispenser Control:** Methods to control food dispensers (Requires Tuya)
- **Event Parsing:** Automatically parses different event types into structured Python objects.

## Features to be Added
- **Camera Feed Access:** Methods to access the camera feed

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

## Tuya Integration (Optional)

The client also supports integration with Tuya devices, which is required for controlling features such as food dispensers. To enable this, you will need to provide the following:

- client_id: This can be found in the PetsSeries app's device screen.

- ip: The ip of the device.

- local_key: You can extract this from the device using a rooted phone and running frida-trace as shown below:
    
```bash 
frida-trace -H 127.0.0.1:27042 --decorate -j '*!*encodeString*'  -f com.versuni.petsseries. -o <a folder location to save frida_trace outputs to a local file>
```
Then, search for the localKey in the logs.


### Example Initialization with Tokens and Tuya Credentials

```python
import asyncio
from petsseries import PetsSeriesClient

async def main():
    client = PetsSeriesClient(
        access_token="your_access_token_here",
        refresh_token="your_refresh
        tuya_credentials={"client_id": "CLIENT_ID", "ip": "IP_ADDRESS", "local_key": "LOCAL_KEY"}
    )
    await client.initialize()
    # Your code here

asyncio.run(main())
```

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

### Get Meals
```python
for home in homes:
    meals = await client.get_meals(home)
    for meal in meals:
        print(meal)
```

#### Create Meal
```python
# Define the meal details
meal_name = "Dinner"
portion_amount = 10  # 1 - 20 portions
feed_time = datetime.combine(datetime.today(), time(hour=18, minute=30))  # 6:30 PM
repeat_days = [1, 2, 3, 4, 5, 6, 7]  # Every day of the week

# Create a Meal instance
meal = Meal(
    id="",  # ID will be assigned by the server
    name=meal_name,
    portion_amount=portion_amount,
    feed_time=feed_time,
    repeat_days=repeat_days,
    device_id=device.id,
    enabled=True,
    url=""  # URL will be assigned by the server
)

try:
    created_meal = await client.create_meal(home, meal)
    print(f"Meal '{created_meal.name}' created successfully with ID: {created_meal.id}")
    print(f"Feed Time: {created_meal.feed_time}")
    print(f"Portion Amount: {created_meal.portion_amount}")
    print(f"Repeat Days: {created_meal.repeat_days}")
    print(f"Device ID: {created_meal.device_id}")
    print(f"Enabled: {created_meal.enabled}")
    print(f"Meal URL: {created_meal.url}")
except Exception as e:
    print(f"An error occurred while creating the meal: {e}")
```

#### Update Meal
```python
# Fetch homes
homes = await client.get_homes()
home = homes[0]  # Select the first home for example

# Fetch meals
meals = await client.get_meals(home)
meal_to_update = meals[0]  # Select the first meal for example

# Modify the meal details
meal_to_update.name = "Updated Meal Name"
meal_to_update.portion_amount = 3
meal_to_update.feed_time = time(13, 30)  # Update to 1:30 PM

# Update the meal
updated_meal = await client.update_meal(home, meal_to_update)
print(f"Meal updated: {updated_meal}")
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

### Usage with Tuya Integration
#### Set Motion Sensitivity
Sets the motion sensitivity level on the Tuya device.

```python
success = await client.set_motion_sensitivity("1")
if success:
    print("Motion sensitivity set successfully.")
```
Parameters:

value (str): Sensitivity level ("0", "1", or "2").
Returns:

bool: True if the operation was successful, False otherwise.
#### Get Motion Sensitivity
Retrieves the current motion sensitivity setting of the Tuya device.

```python
sensitivity = await client.get_motion_sensitivity()
if sensitivity:
    print(f"Current motion sensitivity: {sensitivity['motion_sensitivity']}")
```
Returns:

Optional[Dict[str, Any]]: The current motion sensitivity if successful, else None.

#### Get Night Vision Level
Sets the night vision level on the Tuya device.

```python
success = await client.set_nightvision_level("2")
if success:
    print("Night vision level set successfully.")
```
Parameters:

value (str): Night vision level ("0", "1", or "2").
Returns:

bool: True if the operation was successful, False otherwise.

#### Get Night Vision Level
Retrieves the current night vision setting of the Tuya device.

```python
nightvision = await client.get_nightvision_level()
if nightvision:
    print(f"Current night vision level: {nightvision['nightvision']}")
```
Returns:

Optional[Dict[str, Any]]: The current night vision level if successful, else None.

#### Toggle Motion Switch
Flips the motion switch on the Tuya device.

```python
success = await client.set_motion_switch()
if success:
    print("Motion switch toggled successfully.")
```
Returns:

bool: True if the operation was successful, False otherwise.

#### Get Motion Switch Status
Retrieves the current status of the motion switch on the Tuya device.

```python
motion_switch = await client.get_motion_switch()
if motion_switch:
    print(f"Motion switch is {'on' if motion_switch['motion_switch'] else 'off'}.")
```
Returns:

Optional[Dict[str, Any]]: The current motion switch status if successful, else None.

#### Set Anti-Flicker Level
Sets the anti-flicker level on the Tuya device.

```python
success = await client.set_anti_flicker_level("1")
if success:
    print("Anti-flicker level set successfully.")
```
Parameters:

value (str): Anti-flicker level ("0", "1", or "2").
Returns:

bool: True if the operation was successful, False otherwise.

#### Get Anti-Flicker Level
Retrieves the current anti-flicker setting of the Tuya device.

```python
anti_flicker = await client.get_anti_flicker_level()
if anti_flicker:
    print(f"Current anti-flicker level: {anti_flicker['anti_flicker']}")
```
Returns:

Optional[Dict[str, Any]]: The current anti-flicker level if successful, else None.

#### Set Feed Number
Sets the number of feeds on the Tuya device.

```python
success = await client.feed_num(5)
if success:
    print("Feed number set successfully.")
```
Parameters:

value (int): Number of feeds (0 to 20).
Returns:

bool: True if the operation was successful, False otherwise.

#### Set Device Volume
Sets the device volume on the Tuya device.

```python
success = await client.set_device_volume(75)
if success:
    print("Device volume set successfully.")
```
Parameters:

value (int): Volume level (1 to 100).
Returns:

bool: True if the operation was successful, False otherwise.

#### Get Device Volume
Retrieves the current volume setting of the Tuya device.

```python
device_volume = await client.get_device_volume()
if device_volume:
    print(f"Current device volume: {device_volume['device_volume']}")
```
Returns:

Optional[Dict[str, Any]]: The current device volume if successful, else None.

#### Set Food Weight
Sets the food weight in grams on the Tuya device.

```python
success = await client.set_food_weight(50)
if success:
    print("Food weight set successfully.")
```
Parameters:

value (int): Food weight (0 to 100).
Returns:

bool: True if the operation was successful, False otherwise.

#### Get Food Weight
Retrieves the current food weight setting of the Tuya device.

```python
food_weight = await client.get_food_weight()
if food_weight:
    print(f"Current food weight: {food_weight['food_weight']} grams")
```
Returns:

Optional[Dict[str, Any]]: The current food weight if successful, else None.

These Tuya methods enhance the functionality of the PetsSeries API Client by allowing granular control over Tuya-integrated devices. Ensure that you have properly initialized the TuyaClient with the necessary credentials before attempting to use these methods.

#### Example Initialization with Tuya Features:

```python
    import asyncio
    from petsseries import PetsSeriesClient

    async def main():
        client = PetsSeriesClient(
            access_token="your_access_token_here",
            refresh_token="your_refresh_token_here",
            tuya_credentials={
                "client_id": "YOUR_CLIENT_ID",
                "ip": "DEVICE_IP_ADDRESS",
                "local_key": "YOUR_LOCAL_KEY"
            }
        )
        await client.initialize()
        
        # Example: Set and get motion sensitivity
        await client.set_motion_sensitivity("1")
        sensitivity = await client.get_motion_sensitivity()
        print(f"Motion Sensitivity: {sensitivity}")

    asyncio.run(main())
```

## Contributing
Contributions are more than welcome!


__Disclaimer:__ This project is not affiliated with PetsSeries or Versuni. It is developed independently and is intended for personal use. Use it responsibly and respect the terms of service of the official PetsSeries API.
