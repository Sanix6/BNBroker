from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def get_cipher():
    key = getattr(settings, "TOTP_ENCRYPTION_KEY", "")

    if not key:
        raise ImproperlyConfigured(
            "TOTP_ENCRYPTION_KEY is not configured"
        )

    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            "Invalid TOTP_ENCRYPTION_KEY"
        ) from exc


def encrypt_totp_secret(secret: str) -> str:
    if not secret:
        raise ValueError("Empty TOTP secret")

    return get_cipher().encrypt(
        secret.encode("utf-8")
    ).decode("ascii")


def decrypt_totp_secret(encrypted_secret: str) -> str:
    if not encrypted_secret:
        raise ValueError("Empty encrypted TOTP secret")

    try:
        return get_cipher().decrypt(
            encrypted_secret.encode("ascii")
        ).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Unable to decrypt TOTP secret"
        ) from exc
