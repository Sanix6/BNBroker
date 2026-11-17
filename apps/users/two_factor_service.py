import time
from datetime import timedelta

import pyotp

from django.db import transaction
from django.utils import timezone

from .models import UserTwoFactor
from .two_factor_crypto import decrypt_totp_secret


class TwoFactorError(Exception):
    pass


def verify_totp(user, code):
    if not isinstance(code, str) or not (
        len(code) == 6 and code.isascii() and code.isdigit()
    ):
        raise TwoFactorError("Неверный формат кода")

    with transaction.atomic():
        config = (
            UserTwoFactor.objects
            .select_for_update()
            .filter(user=user)
            .first()
        )

        if not config or not config.enabled:
            raise TwoFactorError("2FA не подключена")

        now = timezone.now()

        if config.locked_until and config.locked_until > now:
            raise TwoFactorError(
                "Слишком много попыток. Повторите позже."
            )

        secret = decrypt_totp_secret(
            config.encrypted_secret
        )

        totp = pyotp.TOTP(secret)
        current_step = int(time.time()) // totp.interval

        matched_step = None

        for step in (
            current_step - 1,
            current_step,
            current_step + 1,
        ):
            if step <= config.last_used_step:
                continue

            if pyotp.utils.strings_equal(
                totp.at(step * totp.interval),
                code,
            ):
                matched_step = step
                break

        if matched_step is None:
            config.failed_attempts += 1

            if config.failed_attempts >= 5:
                config.locked_until = (
                    now + timedelta(minutes=15)
                )
                config.failed_attempts = 0

            config.save(update_fields=[
                "failed_attempts",
                "locked_until",
            ])

            return False

        config.last_used_step = matched_step
        config.failed_attempts = 0
        config.locked_until = None

        config.save(update_fields=[
            "last_used_step",
            "failed_attempts",
            "locked_until",
        ])

        return True
