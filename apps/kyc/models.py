import uuid
from django.conf import settings
from django.db import models

class KYCVerification(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Не начато"
        PENDING = "pending", "На проверке"
        APPROVED = "approved", "Одобрено"
        REJECTED = "rejected", "Отклонено"
        EXPIRED = "expired", "Истекло"
        ERROR = "error", "Ошибка"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="kyc_verifications")
    provider = models.CharField(max_length=20, default="ranex", editable=False)
    external_applicant_id = models.CharField(max_length=128, blank=True, db_index=True)
    external_check_id = models.CharField(max_length=128, blank=True, db_index=True)
    level_name = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED, db_index=True)
    review_reason = models.TextField(blank=True)
    provider_payload = models.JSONField(default=dict, blank=True, help_text="Ответ провайдера; не хранить здесь документы, секреты и лишние ПД")
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = "Проверка KYC"
        verbose_name_plural = "Проверки KYC"
        ordering = ["-created_at"]
    def __str__(self): return f"{self.user_id}: {self.status}"
