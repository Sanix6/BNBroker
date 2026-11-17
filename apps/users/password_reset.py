
import secrets
import hashlib
import hmac
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .models import User, EmailVerificationCode
from .serializers import (
    PasswordResetRequestSerializer,
    PasswordResetVerifySerializer,
    PasswordResetConfirmSerializer,
)

logger = logging.getLogger(__name__)

RESET_PREFIX = "reset:"
RESET_SALT = "bnbroker-password-reset-v1"


class PasswordResetThrottle(AnonRateThrottle):
    rate = "5/hour"


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class ResetTokenSerializer(serializers.Serializer):
    reset_token = serializers.CharField()
    expires_in = serializers.IntegerField()


def password_fingerprint(user):
    return hmac.new(
        settings.SECRET_KEY.encode(),
        user.password.encode(),
        hashlib.sha256,
    ).hexdigest()


def invalid_code():
    return Response(
        {"detail": "Неверный или истёкший код"},
        status=400,
    )


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetThrottle]

    @extend_schema(
        tags=["Password Reset"],
        request=PasswordResetRequestSerializer,
        responses={200: DetailSerializer},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()

        response = {
            "detail": (
                "Если email зарегистрирован, "
                "код восстановления будет отправлен"
            )
        }

        user = User.objects.filter(
            email__iexact=email,
            is_active=True,
        ).first()

        if user is None:
            return Response(response)

        now = timezone.now()

        latest = EmailVerificationCode.objects.filter(
            user=user,
            code_hash__startswith=RESET_PREFIX,
        ).first()

        if latest and latest.created_at > now - timedelta(seconds=60):
            return Response(response)

        code = f"{secrets.randbelow(1_000_000):06d}"

        record = EmailVerificationCode.objects.create(
            user=user,
            code_hash=RESET_PREFIX + make_password(code),
            expires_at=now + timedelta(minutes=10),
        )

        try:
            send_mail(
                subject="BNBroker — восстановление пароля",
                message=(
                    f"Ваш код: {code}\n"
                    "Код действителен 10 минут.\n"
                    "Если вы не запрашивали сброс, "
                    "проигнорируйте письмо."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception:
            record.delete()
            logger.exception("Password reset email delivery failed")
            return Response(response)

        EmailVerificationCode.objects.filter(
            user=user,
            code_hash__startswith=RESET_PREFIX,
            used_at__isnull=True,
        ).exclude(pk=record.pk).update(used_at=timezone.now())

        return Response(response)


class PasswordResetVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetThrottle]

    @extend_schema(
        tags=["Password Reset"],
        request=PasswordResetVerifySerializer,
        responses={
            200: ResetTokenSerializer,
            400: DetailSerializer,
        },
    )
    def post(self, request):
        serializer = PasswordResetVerifySerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()
        code = serializer.validated_data["code"]

        with transaction.atomic():
            user = User.objects.filter(
                email__iexact=email,
                is_active=True,
            ).first()

            if not user:
                return invalid_code()

            record = (
                EmailVerificationCode.objects
                .select_for_update()
                .filter(
                    user=user,
                    code_hash__startswith=RESET_PREFIX,
                )
                .first()
            )

            now = timezone.now()

            if (
                not record
                or record.used_at is not None
                or record.expires_at <= now
                or record.attempts >= 5
            ):
                return invalid_code()

            record.attempts += 1
            record.save(update_fields=["attempts"])

            if not check_password(
                code,
                record.code_hash[len(RESET_PREFIX):],
            ):
                return invalid_code()

            record.used_at = now
            record.save(update_fields=["used_at"])

            token = signing.dumps(
                {
                    "uid": str(user.pk),
                    "rid": record.pk,
                    "pwd": password_fingerprint(user),
                },
                salt=RESET_SALT,
            )

        return Response({
            "reset_token": token,
            "expires_in": 300,
        })


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetThrottle]

    @extend_schema(
        tags=["Password Reset"],
        request=PasswordResetConfirmSerializer,
        responses={
            200: DetailSerializer,
            400: DetailSerializer,
        },
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        try:
            payload = signing.loads(
                data["reset_token"],
                salt=RESET_SALT,
                max_age=300,
            )
        except (signing.BadSignature, signing.SignatureExpired):
            return Response(
                {"detail": "Токен недействителен или истёк"},
                status=400,
            )

        with transaction.atomic():
            user = (
                User.objects
                .select_for_update()
                .filter(
                    pk=payload.get("uid"),
                    is_active=True,
                )
                .first()
            )

            if user is None:
                return Response(
                    {"detail": "Токен недействителен"},
                    status=400,
                )

            record = (
                EmailVerificationCode.objects
                .select_for_update()
                .filter(
                    pk=payload.get("rid"),
                    user=user,
                    code_hash__startswith=RESET_PREFIX,
                    used_at__isnull=False,
                )
                .first()
            )

            if (
                record is None
                or record.attempts > 5
                or not hmac.compare_digest(
                    str(payload.get("pwd", "")),
                    password_fingerprint(user),
                )
            ):
                return Response(
                    {"detail": "Токен недействителен"},
                    status=400,
                )

            validate_password(data["new_password"], user=user)

            user.set_password(data["new_password"])
            user.save(update_fields=["password"])

        return Response({
            "detail": "Пароль успешно изменён"
        })
