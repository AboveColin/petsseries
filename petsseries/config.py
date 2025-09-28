"""
This module contains the configuration for the PetsSeries system.
"""

from dataclasses import dataclass


@dataclass
class Config:
    """
    Represents the configuration for the PetsSeries system.
    """

    base_url: str = "https://petseries.prd.nbx.iot.versuni.com"
    user_info_url: str = (
        "https://cdc.accounts.home.id/oidc/op/v1.0/4_JGZWlP8eQHpEqkvQElolbA/userinfo"
    )
    consumer_url: str = base_url + "/api/consumer"
    homes_url: str = base_url + "/api/homes"
    token_url: str = (
        "https://cdc.accounts.home.id/oidc/op/v1.0/4_JGZWlP8eQHpEqkvQElolbA/token"
    )
