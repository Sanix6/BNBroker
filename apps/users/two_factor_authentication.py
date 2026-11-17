from rest_framework.exceptions import AuthenticationFailed

from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import UserTwoFactor


def validate_security_claims(user, token):
    config = UserTwoFactor.objects.filter(
        user=user
    ).only(
        "enabled",
        "auth_version",
    ).first()

    current_version = config.auth_version if config else 0
    token_version = token.get("auth_version", 0)

    if (
        type(token_version) is not int
        or token_version != current_version
    ):
        raise AuthenticationFailed(
            "Сессия устарела. Войдите заново.",
            code="session_revoked",
        )

    if config and config.enabled:
        if token.get("mfa_verified") is not True:
            raise AuthenticationFailed(
                "Требуется двухфакторная аутентификация.",
                code="mfa_required",
            )


class TwoFactorJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)

        validate_security_claims(
            user,
            validated_token,
        )

        return user
