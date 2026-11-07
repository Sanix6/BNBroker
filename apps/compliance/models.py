import uuid
from django.conf import settings
from django.db import models

class AMLCheck(models.Model):
    class Kind(models.TextChoices):
        ADDRESS = "address", "Проверка адреса"
        TRANSACTION = "transaction", "Проверка TxID"
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        COMPLETED = "completed", "Завершена"
        FAILED = "failed", "Ошибка"
    class Decision(models.TextChoices):
        PENDING = "pending", "Не принято"
        APPROVED = "approved", "Одобрено"
        REVIEW = "manual_review", "Ручная проверка"
        BLOCKED = "blocked", "Заблокировано"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="crypto_aml_checks")
    asset_network = models.ForeignKey("crypto.CryptoNetwork", on_delete=models.PROTECT, related_name="aml_checks")
    crypto_address = models.ForeignKey("crypto.CryptoAddress", on_delete=models.SET_NULL, null=True, blank=True, related_name="aml_checks")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    address = models.CharField(max_length=255, blank=True)
    txid = models.CharField(max_length=255, blank=True)
    provider = models.CharField(max_length=20, default="ranex", editable=False)
    provider_check_id = models.CharField(max_length=128, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    decision = models.CharField(max_length=20, choices=Decision.choices, default=Decision.PENDING, db_index=True)
    risk_score = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    risk_category = models.CharField(max_length=100, blank=True)
    provider_payload = models.JSONField(default=dict, blank=True, help_text="Очищенный ответ Ranex без токенов и лишних ПД")
    error_message = models.TextField(blank=True)
    screened_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        verbose_name = "AML-проверка"
        verbose_name_plural = "AML-проверки"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["kind","status","created_at"], name="aml_kind_status_created_idx")]
        constraints = [models.CheckConstraint(condition=(models.Q(kind="address", address__gt="", txid="") | models.Q(kind="transaction", txid__gt="", address="")), name="aml_address_or_txid_required")]
        
    def __str__(self): return f"{self.kind}: {self.address or self.txid}"
