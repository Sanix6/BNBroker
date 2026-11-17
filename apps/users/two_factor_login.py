import hashlib
import secrets

from datetime import timedelta

from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone

from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import AnonRateThrottle

from rest_framework_simplejwt.tokens import RefreshToken

from drf_spectacular.utils import extend_schema

from .models import (
    UserTwoFactor,
    TwoFactorLoginChallenge,
    UserLoginHistory,
)
from .two_factor_service import verify_totp, TwoFactorError


class LoginThrottle(AnonRateThrottle):
    rate = "10/hour"


class SecureLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )


class VerifyLoginSerializer(serializers.Serializer):
    challenge_token = serializers.CharField()
    code = serializers.RegexField(regex=r"^\d{6}$")


def issue_tokens(user, mfa_verified=False):
    config = UserTwoFactor.objects.filter(user=user).first()

    refresh = RefreshToken.for_user(user)

    refresh["auth_version"] = (
        config.auth_version if config else 0
    )
    refresh["mfa_verified"] = bool(mfa_verified)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def record_login(user, request):
    UserLoginHistory.objects.create(
        user=user,
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get(
            "HTTP_USER_AGENT", ""
        )[:512],
        successful=True,
    )


class SecureLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginThrottle]

    @extend_schema(
        tags=["Authentication / 2FA"],
        summary="Вход с поддержкой Google Authenticator",
        request=SecureLoginSerializer,
        responses={200: None},
    )
    def post(self, request):
        serializer = SecureLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request=request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )

        if not user or not user.is_active or not user.is_email_verified:
            return Response(
                {"detail": "Неверный email или пароль"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        config = UserTwoFactor.objects.filter(user=user).first()

        if config and config.enabled:
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(
                raw_token.encode()
            ).hexdigest()

            TwoFactorLoginChallenge.objects.create(
                user=user,
                token_hash=token_hash,
                expires_at=timezone.now() + timedelta(minutes=5),
            )

            return Response({
                "requires_2fa": True,
                "challenge_token": raw_token,
                "expires_in": 300,
            })

        tokens = issue_tokens(user, mfa_verified=False)
        record_login(user, request)

        return Response({
            "requires_2fa": False,
            **tokens,
        })


class SecureLoginVerifyView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginThrottle]

    @extend_schema(
        tags=["Authentication / 2FA"],
        summary="Подтвердить код Google Authenticator при входе",
        request=VerifyLoginSerializer,
        responses={200: None},
    )
    @transaction.atomic
    def post(self, request):
        serializer = VerifyLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_token = serializer.validated_data["challenge_token"]
        token_hash = hashlib.sha256(
            raw_token.encode()
        ).hexdigest()

        challenge = (
            TwoFactorLoginChallenge.objects
            .select_for_update()
            .select_related("user")
            .filter(token_hash=token_hash)
            .first()
        )

        if (
            not challenge
            or challenge.used_at is not None
            or challenge.expires_at <= timezone.now()
            or challenge.attempts >= 5
        ):
            return Response(
                {"detail": "Запрос на вход недействителен"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        challenge.attempts += 1
        challenge.save(update_fields=["attempts"])

        try:
            valid = verify_totp(
                challenge.user,
                serializer.validated_data["code"],
            )
        except TwoFactorError:
            valid = False

        if not valid:
            return Response(
                {"detail": "Неверный код Google Authenticator"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        challenge.used_at = timezone.now()
        challenge.save(update_fields=["used_at"])

        tokens = issue_tokens(
            challenge.user,
            mfa_verified=True,
        )

        record_login(challenge.user, request)

        return Response({
            "requires_2fa": False,
            **tokens,
        })
