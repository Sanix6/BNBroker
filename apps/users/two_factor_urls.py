from django.urls import path
from .two_factor_views import TwoFactorConfirmView

from .two_factor_views import (
    TwoFactorStatusView,
    TwoFactorSetupView,
)

urlpatterns = [
    path(
        "confirm/",
        TwoFactorConfirmView.as_view(),
        name="two-factor-confirm",
    ),
    path(
        "status/",
        TwoFactorStatusView.as_view(),
        name="two-factor-status",
    ),
    path(
        "setup/",
        TwoFactorSetupView.as_view(),
        name="two-factor-setup",
    ),
]
