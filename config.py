"""
This module contains the configuration for the PetsSeries system.
"""

from dataclasses import dataclass


@dataclass
class Config:
    """
    Represents the configuration for the PetsSeries system.
    """

    base_url: str = "https://petsseries-backend.prod.eu-hs.iot.versuni.com"
    user_info_url: str = (
        "https://cdc.accounts.home.id/oidc/op/v1.0/4_JGZWlP8eQHpEqkvQElolbA/userinfo"
    )
    consumer_url: str = (
        "https://nbx-discovery.prod.eu-hs.iot.versuni.com/api/petsseries/consumer"
    )
    homes_url: str = base_url + "/api/v1/home-management/available-homes"
    token_url: str = (
        "https://cdc.accounts.home.id/oidc/op/v1.0/4_JGZWlP8eQHpEqkvQElolbA/token"
    )
