"""
This module contains the configuration for the PetsSeries system.
"""

from dataclasses import dataclass

from .backends import HOMEID, PET_SERIES


@dataclass
class Config:
    """
    Represents the configuration for the PetsSeries system.
    """

    # API Endpoints. base_url is the Pet Series app's backend; homeid_base_url
    # is the backend of feeders set up in the Philips HomeID app.
    base_url: str = PET_SERIES.base_url
    homeid_base_url: str = HOMEID.base_url
    user_info_url: str = (
        "https://cdc.accounts.home.id/oidc/op/v1.0/4_JGZWlP8eQHpEqkvQElolbA/userinfo"
    )
    consumer_url: str = base_url + "/api/consumer"
    homes_url: str = base_url + "/api/homes"
    token_url: str = (
        "https://cdc.accounts.home.id/oidc/op/v1.0/4_JGZWlP8eQHpEqkvQElolbA/token"
    )

    # OIDC/PKCE Configuration (for the Philips app)
    oidc_discovery_url: str = "https://cdc.accounts.home.id/oidc/op/v1.0/4_JGZWlP8eQHpEqkvQElolbA/.well-known/openid-configuration"
    oidc_client_id: str = "fYMYYYljq3cVMI8YGo0mBrhs"
    oidc_redirect_uri: str = "paw://login"
    oidc_scope: str = "openid profile email account_write DI.AccountProfile.read DI.AccountProfile.write"

    # SAP CDC OTP login configuration used by the browser and mobile clients.
    cdc_base_url: str = "https://cdc.accounts.home.id"
    authui_base_url: str = "https://www.accounts.home.id"
    cdc_api_key: str = "4_JGZWlP8eQHpEqkvQElolbA"

    def base_url_for(self, backend: str) -> str:
        """Return the base URL of one backend (a key from petsseries.backends)."""
        if backend == HOMEID.key:
            return self.homeid_base_url
        return self.base_url

    def home_url(self, home) -> str:
        """Return the URL of a home on its own backend, without a trailing slash."""
        return f"{self.base_url_for(home.backend)}/api/homes/{home.id}"
