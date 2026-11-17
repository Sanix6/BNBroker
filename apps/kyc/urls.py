from .kyb import KYBStartView
from .webhook import RanexWebhookView

from django.urls import path

from .views import (
    KYCMeView,
    KYCStartView,
    KYCRefreshView,
)

urlpatterns = [
    path("ranex/webhook/", RanexWebhookView.as_view(), name="ranex-kyc-webhook"),
    path("legal/start/", KYBStartView.as_view(), name="kyb-start"),
    path("me/", KYCMeView.as_view(), name="kyc-me"),
    path("start/", KYCStartView.as_view(), name="kyc-start"),
    path("refresh/", KYCRefreshView.as_view(), name="kyc-refresh"),
]
