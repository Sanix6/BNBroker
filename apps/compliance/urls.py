from django.urls import path

from apps.compliance.views import (
    AMLAddressCheckView,
    AMLCheckDetailView,
    AMLCheckListView,
)

urlpatterns = [
    path(
        "address/check/",
        AMLAddressCheckView.as_view(),
        name="aml-address-check",
    ),
    path(
        "checks/",
        AMLCheckListView.as_view(),
        name="aml-check-list",
    ),
    path(
        "checks/<uuid:id>/",
        AMLCheckDetailView.as_view(),
        name="aml-check-detail",
    ),
]
