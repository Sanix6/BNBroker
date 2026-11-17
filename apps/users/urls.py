from django.urls import path
from .two_factor_login import SecureLoginView, SecureLoginVerifyView
from .two_factor_refresh import SecureTokenRefreshView
from .views import RegisterView, VerifyEmailView, ResendEmailView, LoginView, MeView
from .password_reset import (
    PasswordResetRequestView,
    PasswordResetVerifyView,
    PasswordResetConfirmView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('resend-code/', ResendEmailView.as_view(), name='resend-code'),
    path('login/', SecureLoginView.as_view(), name='login'),
    path('login/verify-2fa/', SecureLoginVerifyView.as_view(), name='login-verify-2fa'),
    path('refresh/', SecureTokenRefreshView.as_view(), name='token-refresh'),
    path('me/', MeView.as_view(), name='me'),
    path("password-reset/request/", PasswordResetRequestView.as_view()),
    path("password-reset/verify/", PasswordResetVerifyView.as_view()),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view()),
]
