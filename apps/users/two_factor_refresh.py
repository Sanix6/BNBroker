from rest_framework import serializers

from rest_framework_simplejwt.serializers import (
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, UserTwoFactor
from .two_factor_authentication import validate_security_claims


class SecureTokenRefreshSerializer(TokenRefreshSerializer):

    def validate(self, attrs):
        try:
            token = RefreshToken(attrs["refresh"])
            user_id = token.get("user_id")

            if not user_id:
                raise serializers.ValidationError(
                    "Недействительный refresh-токен"
                )

            user = User.objects.filter(
                pk=user_id,
                is_active=True,
                is_email_verified=True,
            ).first()

            if not user:
                raise serializers.ValidationError(
                    "Пользователь недоступен"
                )

            validate_security_claims(user, token)

        except Exception as exc:
            from rest_framework.exceptions import AuthenticationFailed
            from rest_framework_simplejwt.exceptions import TokenError

            if isinstance(
                exc,
                (AuthenticationFailed, TokenError, ValueError, TypeError),
            ):
                raise serializers.ValidationError(
                    "Сессия недействительна. Войдите заново."
                ) from exc

            raise

        return super().validate(attrs)


class SecureTokenRefreshView(TokenRefreshView):
    serializer_class = SecureTokenRefreshSerializer
