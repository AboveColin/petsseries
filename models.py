# petsseries/models.py

from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    sub: str
    name: str
    given_name: str
    picture: Optional[str]
    locale: Optional[str]
    email: str


@dataclass
class Home:
    id: str
    name: str
    shared: bool
    numberOfDevices: int
    externalId: str
    numberOfActivities: int

    def get_home_id(self):
        return self.id
    
    def get_home_name(self):
        return self.name
        
        
@dataclass
class Meal:
    id: str
    name: str
    portionAmount: float
    feedTime: str
    repeatDays: list
    deviceId: str
    enabled: bool
    url: str


@dataclass
class Device:
    id: str
    name: str
    productCtn: str
    productId: str
    externalId: str
    url: str
    settingsUrl: str
    subscriptionUrl: str
    
    def get_device_id(self):
        return self.id
    
    def get_device_name(self):
        return self.name


@dataclass
class Consumer:
    id: str
    countryCode: str
    url: str


@dataclass
class ModeDevice:
    id: str
    name: str
    settings: dict


@dataclass
class Event:
    id: str
    type: str
    source: str
    time: str
    url: str

    EventTypes = ["motion_detected", "meal_dispensed", "meal_upcoming", "food_level_low"]

    def __repr__(self) -> str:
        return f"type={self.type} time={self.time}"


@dataclass
class MotionEvent(Event):
    clusterId: Optional[str]
    metadata: Optional[dict]
    thumbnailKey: Optional[str]
    deviceId: Optional[str]
    deviceName: Optional[str]
    thumbnailUrl: Optional[str]
    productCtn: Optional[str]
    deviceExternalId: Optional[str]

    def __repr__(self) -> str:
        return super().__repr__() + f" self.deviceId={self.deviceId} self.deviceName={self.deviceName}"


@dataclass
class MealDispensedEvent(Event):
    clusterId: Optional[str]
    metadata: Optional[dict]
    mealName: Optional[str]
    deviceId: Optional[str]
    mealUrl: Optional[str]
    mealAmount: Optional[float]
    deviceName: Optional[str]
    deviceExternalId: Optional[str]
    productCtn: Optional[str]


@dataclass
class MealUpcomingEvent(Event):
    clusterId: Optional[str]
    metadata: Optional[dict]
    mealName: Optional[str]
    deviceId: Optional[str]
    mealUrl: Optional[str]
    mealAmount: Optional[float]
    deviceName: Optional[str]
    deviceExternalId: Optional[str]
    productCtn: Optional[str]

    def __repr__(self) -> str:
        return super().__repr__() + f" self.mealName={self.mealName}"


@dataclass
class FoodLevelLowEvent(Event):
    clusterId: Optional[str]
    metadata: Optional[dict]
    deviceId: Optional[str]
    deviceName: Optional[str]
    productCtn: Optional[str]
    deviceExternalId: Optional[str]

    def __repr__(self) -> str:
        return super().__repr__() + f" self.deviceId={self.deviceId} self.deviceName={self.deviceName}"
