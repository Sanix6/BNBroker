import base64
import io

import pyotp
import qrcode

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from .models import UserTwoFactor
from .two_factor_crypto import encrypt_totp_secret


class TwoFactorThrottle(UserRateThrottle):
    scope = "two_factor"

    def get_rate(self):
        return "5/hour"


class TwoFactorSetupSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )


class TwoFactorStatusResponseSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    setup_pending = serializers.BooleanField()


class TwoFactorSetupResponseSerializer(serializers.Serializer):
    secret = serializers.CharField()
    otpauth_url = serializers.CharField()
    qr_code = serializers.CharField()


class TwoFactorStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Security / 2FA"],
        summary="Статус Google Authenticator",
        responses={200: TwoFactorStatusResponseSerializer},
    )
    def get(self, request):
        obj = UserTwoFactor.objects.filter(
            user=request.user
        ).first()

        return Response({
            "enabled": bool(obj and obj.enabled),
            "setup_pending": bool(
                obj
                and obj.encrypted_pending_secret
                and obj.pending_created_at
                and obj.pending_created_at
                > timezone.now() - timedelta(minutes=10)
            ),
        })


class TwoFactorSetupView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [TwoFactorThrottle]

    @extend_schema(
        tags=["Security / 2FA"],
        summary="Получить QR-код Google Authenticator",
        request=TwoFactorSetupSerializer,
        responses={200: TwoFactorSetupResponseSerializer},
    )
    @transaction.atomic
    def post(self, request):
        serializer = TwoFactorSetupSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        if not request.user.check_password(
            serializer.validated_data["current_password"]
        ):
            return Response(
                {"detail": "Неверный пароль"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        obj, _ = UserTwoFactor.objects.select_for_update().get_or_create(
            user=request.user
        )

        if obj.enabled:
            return Response(
                {"detail": "2FA уже подключена"},
                status=status.HTTP_409_CONFLICT,
            )

        secret = pyotp.random_base32()

        obj.encrypted_pending_secret = encrypt_totp_secret(secret)
        obj.pending_created_at = timezone.now()
        obj.save(update_fields=[
            "encrypted_pending_secret",
            "pending_created_at",
        ])

        totp = pyotp.TOTP(secret)

        uri = totp.provisioning_uri(
            name=request.user.email,
            issuer_name="BNBroker",
        )

        image = qrcode.make(uri)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        qr_base64 = base64.b64encode(
            buffer.getvalue()
        ).decode("ascii")

        response = Response({
            "secret": secret,
            "otpauth_url": uri,
            "qr_code": "data:image/png;base64," + qr_base64,
        })

        response["Cache-Control"] = "no-store"
        response["Pragma"] = "no-cache"

        return response


class TwoFactorConfirmSerializer(serializers.Serializer):
    code = serializers.RegexField(
        regex=r"^\d{6}$",
        max_length=6,
    )


class TwoFactorConfirmView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [TwoFactorThrottle]

    @extend_schema(
        tags=["Security / 2FA"],
        summary="Подтвердить Google Authenticator",
        request=TwoFactorConfirmSerializer,
        responses={200: None},
    )
    @transaction.atomic
    def post(self, request):
        serializer = TwoFactorConfirmSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        obj = UserTwoFactor.objects.select_for_update().filter(
            user=request.user
        ).first()

        if not obj or not obj.encrypted_pending_secret:
            return Response(
                {"detail": "Сначала выполните настройку 2FA"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if obj.enabled:
            return Response(
                {"detail": "2FA уже подключена"},
                status=status.HTTP_409_CONFLICT,
            )

        if (
            not obj.pending_created_at
            or obj.pending_created_at
            < timezone.now() - timedelta(minutes=10)
        ):
            return Response(
                {"detail": "Время настройки истекло"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .two_factor_crypto import decrypt_totp_secret

        secret = decrypt_totp_secret(
            obj.encrypted_pending_secret
        )

        code = serializer.validated_data["code"]

        if not pyotp.TOTP(secret).verify(
            code,
            valid_window=1,
        ):
            return Response(
                {"detail": "Неверный код Google Authenticator"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        import time
        from .two_factor_login import issue_tokens

        totp = pyotp.TOTP(secret)
        current_step = int(time.time()) // totp.interval

        matched_step = next(
            (
                step
                for step in (
                    current_step - 1,
                    current_step,
                    current_step + 1,
                )
                if pyotp.utils.strings_equal(
                    totp.at(step * totp.interval),
                    code,
                )
            ),
            None,
        )

        if matched_step is None:
            return Response(
                {"detail": "Код устарел. Введите новый код."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        obj.encrypted_secret = obj.encrypted_pending_secret
        obj.encrypted_pending_secret = ""
        obj.pending_created_at = None
        obj.enabled = True
        obj.confirmed_at = timezone.now()
        obj.last_used_step = matched_step
        obj.failed_attempts = 0
        obj.locked_until = None
        obj.auth_version += 1

        obj.save(update_fields=[
            "encrypted_secret",
            "encrypted_pending_secret",
            "pending_created_at",
            "enabled",
            "confirmed_at",
            "last_used_step",
            "failed_attempts",
            "locked_until",
            "auth_version",
        ])

        tokens = issue_tokens(
            request.user,
            mfa_verified=True,
        )

        response = Response({
            "verified": True,
            "enabled": True,
            "detail": "Двухфакторная аутентификация включена",
            **tokens,
        })
        response["Cache-Control"] = "no-store"
        return response
