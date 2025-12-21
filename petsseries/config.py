"""
This module contains the configuration for the PetsSeries system.
"""

from dataclasses import dataclass


@dataclass
class Config:
    """
    Represents the configuration for the PetsSeries system.
    """

    # API Endpoints
    base_url: str = "https://petseries.prd.nbx.iot.versuni.com"
    user_info_url: str = (
        "https://cdc.accounts.home.id/oidc/op/v1.0/4_JGZWlP8eQHpEqkvQElolbA/userinfo"
    )
    consumer_url: str = base_url + "/api/consumer"
    homes_url: str = base_url + "/api/homes"
    token_url: str = (
        "https://cdc.accounts.home.id/oidc/op/v1.0/4_JGZWlP8eQHpEqkvQElolbA/token"
    )

    # OIDC/PKCE Configuration (from decompiled Philips app AuthUtils.java)
    oidc_discovery_url: str = "https://cdc.accounts.home.id/oidc/op/v1.0/4_JGZWlP8eQHpEqkvQElolbA/.well-known/openid-configuration"
    oidc_client_id: str = "fYMYYYljq3cVMI8YGo0mBrhs"
    oidc_redirect_uri: str = "paw://login"
    oidc_scope: str = "openid profile email account_write DI.AccountProfile.read DI.AccountProfile.write"
