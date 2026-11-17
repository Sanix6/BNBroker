from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    path(
        "api/v1/security/2fa/",
        include("apps.users.two_factor_urls"),
    ),

    path("api/v1/aml/", include("apps.compliance.urls")),

    path("admin/workspace/", include("core.workspace_urls")),
    path("admin/", admin.site.urls),

    # API
    path("api/v1/auth/", include("apps.users.urls")),
    path("api/v1/kyc/", include("apps.kyc.urls")),
    path('api/v1/exchange/',include('apps.exchange.urls')),

    # OpenAPI / Swagger
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    
]
