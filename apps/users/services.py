import secrets
from datetime import timedelta
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from .models import EmailVerificationCode

def send_verification_code(user):
    now = timezone.now()
    last = EmailVerificationCode.objects.filter(user=user).first()
    if last and last.created_at > now - timedelta(seconds=60):
        raise ValueError('Повторная отправка доступна через 60 секунд')
    code = f'{secrets.randbelow(1_000_000):06d}'
    record = EmailVerificationCode.objects.create(user=user, code_hash=make_password(code),
                                                   expires_at=now + timedelta(minutes=10))
    try:
        message = EmailMultiAlternatives('Подтверждение Email — Xchange', f'Ваш код: {code}. Действует 10 минут.', settings.DEFAULT_FROM_EMAIL, [user.email])
        message.attach_alternative(render_to_string('users/verification_email.html', {'code': code}), 'text/html')
        message.send(fail_silently=False)
    except Exception:
        record.delete()
        raise
