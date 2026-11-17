"""Authenticated password change for BNBroker (no email reset token required)."""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .models import (
    EmailVerificationCode,
    TwoFactorLoginChallenge,
    User,
    UserTwoFactor,
)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        write_only=True, trim_whitespace=False, max_length=4096,
    )
    new_password = serializers.CharField(
        write_only=True, trim_whitespace=False, max_length=4096,
    )
    confirm_password = serializers.CharField(
        write_only=True, trim_whitespace=False, max_length=4096,
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Пароли не совпадают",
            })
        return attrs


class PasswordChangeResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class PasswordChangeThrottle(UserRateThrottle):
    def get_rate(self):
        return "5/hour"


class PasswordChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [PasswordChangeThrottle]

    @extend_schema(
        tags=["Authentication"],
        summary="Смена пароля с подтверждением текущего",
        description=(
            "Для авторизованного пользователя. После смены пароля старые "
            "access/refresh JWT отзываются. Войдите заново."
        ),
        request=PasswordChangeSerializer,
        responses={200: PasswordChangeResponseSerializer},
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # User row lock serializes concurrent password changes for one account.
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)

            if not user.check_password(data["current_password"]):
                raise serializers.ValidationError({
                    "current_password": "Неверный текущий пароль",
                })

            if user.check_password(data["new_password"]):
                raise serializers.ValidationError({
                    "new_password": "Новый пароль должен отличаться от текущего",
                })

            try:
                validate_password(data["new_password"], user=user)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({
                    "new_password": exc.messages,
                }) from exc

            user.set_password(data["new_password"])
            user.save(update_fields=["password", "updated_at"])

            # The project's secure access and refresh flows both check
            # auth_version, so this revokes all previously issued JWTs.
            security, _ = (
                UserTwoFactor.objects.select_for_update().get_or_create(
                    user=user,
                )
            )
            security.auth_version += 1
            security.save(update_fields=["auth_version"])

            # Invalidate unfinished login challenges and password-reset codes.
            now = timezone.now()
            TwoFactorLoginChallenge.objects.filter(
                user=user, used_at__isnull=True,
            ).update(used_at=now)
            EmailVerificationCode.objects.filter(
                user=user,
                used_at__isnull=True,
                code_hash__startswith="reset:",
            ).update(used_at=now)

        response = Response(
            {"detail": "Пароль успешно изменён. Войдите заново."},
            status=status.HTTP_200_OK,
        )
        response["Cache-Control"] = "no-store"
        response["Pragma"] = "no-cache"
        return response
