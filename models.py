"""
Data models for the PetsSeries application.

This module defines the data structures used throughout the PetsSeries client,
including users, homes, meals, devices, consumers, mode devices, and various event types.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


@dataclass
class User:
    """
    Represents a user in the PetsSeries system.

    Attributes:
        sub (str): Subject identifier.
        name (str): Full name of the user.
        given_name (str): Given name of the user.
        picture (Optional[str]): URL to the user's picture.
        locale (Optional[str]): Locale of the user.
        email (str): Email address of the user.
    """

    sub: str
    name: str
    given_name: str
    picture: Optional[str]
    locale: Optional[str]
    email: str


@dataclass
class Home:
    """
    Represents a home associated with a user.

    Attributes:
        id (str): Unique identifier for the home.
        name (str): Name of the home.
        shared (bool): Indicates if the home is shared.
        number_of_devices (int): Number of devices in the home.
        external_id (str): External identifier for the home.
        number_of_activities (int): Number of activities associated with the home.
    """

    id: str
    name: str
    shared: bool
    number_of_devices: int
    external_id: str
    number_of_activities: int

    def get_home_id(self) -> str:
        """Retrieve the home's unique identifier."""
        return self.id

    def get_home_name(self) -> str:
        """Retrieve the home's name."""
        return self.name


@dataclass
class Meal:
    # pylint: disable=too-many-instance-attributes
    """
    Represents a meal scheduled in the PetsSeries system.

    Attributes:
        id (str): Unique identifier for the meal.
        name (str): Name of the meal.
        portion_amount (float): Amount of the portion.
        feed_time (str): Scheduled feeding time.
        repeat_days (List[str]): Days when the meal repeats.
        device_id (str): Identifier of the device associated with the meal.
        enabled (bool): Indicates if the meal is enabled.
        url (str): URL endpoint for the meal.
    """

    id: str
    name: str
    portion_amount: float
    feed_time: str
    repeat_days: List[str]
    device_id: str
    enabled: bool
    url: str


@dataclass
class Device:
    # pylint: disable=too-many-instance-attributes
    """
    Represents a device in the PetsSeries system.

    Attributes:
        id (str): Unique identifier for the device.
        name (str): Name of the device.
        product_ctn (str): Product CTN of the device.
        product_id (str): Product ID of the device.
        external_id (str): External identifier for the device.
        url (str): URL endpoint for the device.
        settings_url (str): URL endpoint for the device settings.
        subscription_url (str): URL endpoint for device subscriptions.
    """

    id: str
    name: str
    product_ctn: str
    product_id: str
    external_id: str
    url: str
    settings_url: str
    subscription_url: str

    def get_device_id(self) -> str:
        """Retrieve the device's unique identifier."""
        return self.id

    def get_device_name(self) -> str:
        """Retrieve the device's name."""
        return self.name


@dataclass
class Consumer:
    """
    Represents a consumer in the PetsSeries system.

    Attributes:
        id (str): Unique identifier for the consumer.
        country_code (str): Country code of the consumer.
        url (str): URL endpoint for the consumer.
    """

    id: str
    country_code: str
    url: str


@dataclass
class ModeDevice:
    """
    Represents a mode device in the PetsSeries system.

    Attributes:
        id (str): Unique identifier for the mode device.
        name (str): Name of the mode device.
        settings (Dict[str, Dict[str, any]]): Settings associated with the mode device.
    """

    id: str
    name: str
    settings: Dict[str, Dict[str, any]]


class EventType(Enum):
    """Enum for event types in the PetsSeries system."""

    MOTION_DETECTED = "motion_detected"
    MEAL_DISPENSED = "meal_dispensed"
    MEAL_UPCOMING = "meal_upcoming"
    FOOD_LEVEL_LOW = "food_level_low"


@dataclass
class Event:
    """
    Base class for events in the PetsSeries system.

    Attributes:
        id (str): Unique identifier for the event.
        type (str): Type of the event.
        source (str): Source of the event.
        time (str): Timestamp of the event.
        url (str): URL endpoint for the event.
    """

    id: str
    type: EventType
    source: str
    time: str
    url: str

    def __repr__(self) -> str:
        """Return a string representation of the event."""
        return f"type={self.type} time={self.time}"

    @classmethod
    def get_event_types(cls) -> List[EventType]:
        """Retrieve the event types."""
        return list(EventType)


@dataclass
class MotionEvent(Event):
    # pylint: disable=too-many-instance-attributes
    """
    Represents a motion detected event in the PetsSeries system.

    Attributes:
        cluster_id (Optional[str]): Cluster identifier.
        metadata (Optional[dict]): Additional metadata.
        thumbnail_key (Optional[str]): Thumbnail key.
        device_id (Optional[str]): Device identifier.
        device_name (Optional[str]): Device name.
        thumbnail_url (Optional[str]): URL to the thumbnail.
        product_ctn (Optional[str]): Product CTN of the device.
        device_external_id (Optional[str]): External identifier of the device.
    """

    cluster_id: Optional[str]
    metadata: Optional[dict]
    thumbnail_key: Optional[str]
    device_id: Optional[str]
    device_name: Optional[str]
    thumbnail_url: Optional[str]
    product_ctn: Optional[str]
    device_external_id: Optional[str]

    def __repr__(self) -> str:
        """Return a string representation of the motion event."""
        base_repr = super().__repr__()
        return f"{base_repr} device_id={self.device_id} device_name={self.device_name}"


@dataclass
class MealDispensedEvent(Event):
    # pylint: disable=too-many-instance-attributes
    """
    Represents a meal dispensed event in the PetsSeries system.

    Attributes:
        cluster_id (Optional[str]): Cluster identifier.
        metadata (Optional[dict]): Additional metadata.
        meal_name (Optional[str]): Name of the meal.
        device_id (Optional[str]): Device identifier.
        meal_url (Optional[str]): URL to the meal.
        meal_amount (Optional[float]): Amount of the meal.
        device_name (Optional[str]): Device name.
        device_external_id (Optional[str]): External identifier of the device.
        product_ctn (Optional[str]): Product CTN of the device.
    """

    cluster_id: Optional[str]
    metadata: Optional[dict]
    meal_name: Optional[str]
    device_id: Optional[str]
    meal_url: Optional[str]
    meal_amount: Optional[float]
    device_name: Optional[str]
    device_external_id: Optional[str]
    product_ctn: Optional[str]


@dataclass
class MealUpcomingEvent(Event):
    # pylint: disable=too-many-instance-attributes
    """
    Represents an upcoming meal event in the PetsSeries system.

    Attributes:
        cluster_id (Optional[str]): Cluster identifier.
        metadata (Optional[dict]): Additional metadata.
        meal_name (Optional[str]): Name of the meal.
        device_id (Optional[str]): Device identifier.
        meal_url (Optional[str]): URL to the meal.
        meal_amount (Optional[float]): Amount of the meal.
        device_name (Optional[str]): Device name.
        device_external_id (Optional[str]): External identifier of the device.
        product_ctn (Optional[str]): Product CTN of the device.
    """

    cluster_id: Optional[str]
    metadata: Optional[dict]
    meal_name: Optional[str]
    device_id: Optional[str]
    meal_url: Optional[str]
    meal_amount: Optional[float]
    device_name: Optional[str]
    device_external_id: Optional[str]
    product_ctn: Optional[str]

    def __repr__(self) -> str:
        """Return a string representation of the meal upcoming event."""
        base_repr = super().__repr__()
        return f"{base_repr} meal_name={self.meal_name}"


@dataclass
class FoodLevelLowEvent(Event):
    """
    Represents a low food level event in the PetsSeries system.

    Attributes:
        cluster_id (Optional[str]): Cluster identifier.
        metadata (Optional[dict]): Additional metadata.
        device_id (Optional[str]): Device identifier.
        device_name (Optional[str]): Device name.
        product_ctn (Optional[str]): Product CTN of the device.
        device_external_id (Optional[str]): External identifier of the device.
    """

    cluster_id: Optional[str]
    metadata: Optional[dict]
    device_id: Optional[str]
    device_name: Optional[str]
    product_ctn: Optional[str]
    device_external_id: Optional[str]

    def __repr__(self) -> str:
        """Return a string representation of the food level low event."""
        base_repr = super().__repr__()
        return f"{base_repr} device_id={self.device_id} device_name={self.device_name}"
