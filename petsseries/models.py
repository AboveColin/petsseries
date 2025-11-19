"""
Data models for the PetsSeries application.

This module defines the data structures used throughout the PetsSeries client,
including users, homes, meals, devices, consumers, mode devices, and various event types.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


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
class Home:  # pylint: disable=too-many-instance-attributes
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
    # Legacy fields (may not be present in new API)
    shared: bool = False
    number_of_devices: int = 0
    external_id: str = ""
    number_of_activities: int = 0

    # New API fields
    url: str = ""
    devices_url: str = ""
    events_url: str = ""
    invites_url: str = ""
    time_zone: Optional[str] = None
    active_mode: Optional[str] = None
    modes: Optional[List[Dict[str, Any]]] = None
    members: Optional[List[Dict[str, Any]]] = None
    vendor_ids: Optional[Dict[str, Any]] = None

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
        repeat_days (List[int]): Days when the meal repeats.
        device_id (str): Identifier of the device associated with the meal.
        enabled (bool): Indicates if the meal is enabled.
        url (str): URL endpoint for the meal.
    """

    id: str
    name: str
    portion_amount: float
    feed_time: str
    repeat_days: List[int]
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
    product_ctn: Optional[str] = None
    product_id: Optional[str] = None
    vendor_id: Optional[str] = None
    external_id: Optional[str] = None
    url: str = ""
    settings_url: str = ""
    subscription_url: Optional[str] = None

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
    language: Optional[str] = None
    identities: Optional[Dict[str, Any]] = None
    identities_url: Optional[str] = None
    installations: Optional[List[Dict[str, Any]]] = None
    installations_url: Optional[str] = None


@dataclass
class ModeDevice:
    """
    Represents a mode device in the PetsSeries system.

    Attributes:
        id (str): Unique identifier for the mode device.
        name (str): Name of the mode device.
    settings (Dict[str, Dict[str, Any]]): Settings associated with the mode device.
    """

    id: str
    name: str
    settings: Dict[str, Dict[str, Any]]


class EventType(Enum):
    """Enum for event types in the PetsSeries system."""

    MOTION_DETECTED = "motion_detected"
    MEAL_DISPENSED = "meal_dispensed"
    MEAL_UPCOMING = "meal_upcoming"
    FOOD_LEVEL_LOW = "food_level_low"
    MEAL_ENABLED = "meal_enabled"
    FILTER_REPLACEMENT_DUE = "filter_replacement_due"
    FOOD_OUTLET_STUCK = "food_outlet_stuck"
    DEVICE_ONLINE = "device_online"
    DEVICE_OFFLINE = "device_offline"


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
    type: str
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


@dataclass
class MealEnabledEvent(Event):
    # pylint: disable=too-many-instance-attributes
    """
    Represents a meal enabled event in the PetsSeries system.

    Attributes:
        cluster_id (Optional[str]): Cluster identifier.
        metadata (Optional[dict]): Additional metadata.
        meal_amount (Optional[float]): Amount of the meal.
        meal_url (Optional[str]): URL to the meal.
        device_external_id (Optional[str]): External identifier of the device.
        product_ctn (Optional[str]): Product CTN of the device.
        meal_time (Optional[str]): Time the meal is enabled.
        device_id (Optional[str]): Device identifier.
        device_name (Optional[str]): Device name.
        meal_repeat_days (Optional[List[int]]): Days the meal repeats.
    """

    cluster_id: Optional[str]
    metadata: Optional[dict]
    meal_amount: Optional[float]
    meal_url: Optional[str]
    device_external_id: Optional[str]
    product_ctn: Optional[str]
    meal_time: Optional[str]
    device_id: Optional[str]
    device_name: Optional[str]
    meal_repeat_days: Optional[List[int]]

    def __repr__(self) -> str:
        """Return a string representation of the meal enabled event."""
        base_repr = super().__repr__()
        return (
            f"{base_repr} "
            f"meal_amount={self.meal_amount} "
            f"meal_time={self.meal_time} "
            f"device_id={self.device_id} "
            f"device_name={self.device_name}"
        )


@dataclass
class FilterReplacementDueEvent(Event):
    """
    Represents a filter replacement due event in the PetsSeries system.

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
        """Return a string representation of the filter replacement due event."""
        base_repr = super().__repr__()
        return f"{base_repr} device_id={self.device_id} device_name={self.device_name}"


@dataclass
class FoodOutletStuckEvent(Event):
    """
    Represents a food outlet stuck event in the PetsSeries system.

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
        """Return a string representation of the food outlet stuck event."""
        base_repr = super().__repr__()
        return f"{base_repr} device_id={self.device_id} device_name={self.device_name}"


@dataclass
class DeviceOnlineEvent(Event):
    """
    Represents a device online event in the PetsSeries system.

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
        """Return a string representation of the device online event."""
        base_repr = super().__repr__()
        return f"{base_repr} device_id={self.device_id} device_name={self.device_name}"


@dataclass
class DeviceOfflineEvent(Event):
    """
    Represents a device offline event in the PetsSeries system.

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
        """Return a string representation of the device offline event."""
        base_repr = super().__repr__()
        return f"{base_repr} device_id={self.device_id} device_name={self.device_name}"
