import uuid
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

POSITIVE = MinValueValidator(0.00000001)

class ExchangeQuote(models.Model):
    class Side(models.TextChoices):
        BUY = 'buy', 'Покупка криптовалюты'
        SELL = 'sell', 'Продажа криптовалюты'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='exchange_quotes')
    side = models.CharField(max_length=4, choices=Side.choices)
    asset_network = models.ForeignKey('crypto.CryptoNetwork', on_delete=models.PROTECT)
    fiat_currency = models.CharField(max_length=3, default='RUB')
    fiat_amount = models.DecimalField(max_digits=24, decimal_places=2, validators=[POSITIVE])
    crypto_amount = models.DecimalField(max_digits=30, decimal_places=12, validators=[POSITIVE])
    rate = models.DecimalField(max_digits=30, decimal_places=12, validators=[POSITIVE], help_text='Единиц фиата за 1 единицу криптовалюты')
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_valid(self):
        return timezone.now() < self.expires_at

    def __str__(self):
        return f'{self.side} {self.crypto_amount} {self.asset_network}'

class ExchangeOrder(models.Model):
    class Status(models.TextChoices):
        AWAITING_PAYMENT = 'awaiting_payment', 'Ожидает оплату'
        PAYMENT_REVIEW = 'payment_review', 'Проверка оплаты'
        PAID = 'paid', 'Оплата подтверждена'
        PROCESSING = 'processing', 'Исполняется'
        COMPLETED = 'completed', 'Завершена'
        CANCELLED = 'cancelled', 'Отменена'
        REJECTED = 'rejected', 'Отклонена'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='exchange_orders')
    quote = models.OneToOneField(ExchangeQuote, on_delete=models.PROTECT, related_name='order')
    wallet_address = models.CharField(max_length=255)
    wallet_memo = models.CharField(max_length=255, blank=True)
    aml_check = models.ForeignKey('compliance.AMLCheck', on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.AWAITING_PAYMENT, db_index=True)
    payment_instructions = models.TextField(blank=True, help_text='Реквизиты, заполненные оператором')
    payment_reference = models.CharField(max_length=128, blank=True)
    txid = models.CharField(max_length=255, blank=True)
    operator_comment = models.TextField(blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.id} ({self.status})'

class PaymentReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(ExchangeOrder, on_delete=models.PROTECT, related_name='receipts')
    file = models.FileField(upload_to='exchange/receipts/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

class ExchangeReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(ExchangeOrder, on_delete=models.PROTECT, related_name='report')
    document = models.FileField(upload_to='exchange/reports/%Y/%m/')
    created_at = models.DateTimeField(auto_now_add=True)


class ExchangeDirection(models.Model):
    """Operator-managed directed pair. RUB is the currently supported fiat endpoint."""
    class Kind(models.TextChoices):
        FIAT = 'fiat', 'Фиат'
        CRYPTO = 'crypto', 'Криптовалюта'

    from_kind = models.CharField(max_length=6, choices=Kind.choices, default=Kind.FIAT)
    from_asset_network = models.ForeignKey(
        'crypto.CryptoNetwork', on_delete=models.PROTECT, null=True, blank=True,
        related_name='exchange_directions_from', verbose_name='Отдаёт: сеть криптовалюты',
    )
    to_kind = models.CharField(max_length=6, choices=Kind.choices, default=Kind.CRYPTO)
    to_asset_network = models.ForeignKey(
        'crypto.CryptoNetwork', on_delete=models.PROTECT, null=True, blank=True,
        related_name='exchange_directions_to', verbose_name='Получает: сеть криптовалюты',
    )
    is_active = models.BooleanField(default=False, db_index=True, verbose_name='Доступно')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Направление обмена'
        verbose_name_plural = 'Направления обмена'
        ordering = ('id',)
        constraints = [
            models.UniqueConstraint(
                fields=['from_kind', 'from_asset_network', 'to_kind', 'to_asset_network'],
                name='exchange_direction_unique_pair',
                nulls_distinct=False,
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        errors = {}
        for side in ('from', 'to'):
            kind = getattr(self, f'{side}_kind')
            network_id = getattr(self, f'{side}_asset_network_id')
            if kind == self.Kind.FIAT and network_id is not None:
                errors[f'{side}_asset_network'] = 'Для RUB сеть должна быть пустой.'
            if kind == self.Kind.CRYPTO and network_id is None:
                errors[f'{side}_asset_network'] = 'Выберите криптовалюту и сеть.'
        if self.from_kind == self.to_kind == self.Kind.FIAT:
            errors['to_kind'] = 'RUB → RUB не является направлением обмена.'
        if (self.from_kind == self.to_kind == self.Kind.CRYPTO and
                self.from_asset_network_id is not None and
                self.from_asset_network_id == self.to_asset_network_id):
            errors['to_asset_network'] = 'Нельзя обменивать актив на самого себя в той же сети.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        left = 'RUB' if self.from_kind == self.Kind.FIAT else str(self.from_asset_network)
        right = 'RUB' if self.to_kind == self.Kind.FIAT else str(self.to_asset_network)
        return f'{left} → {right}'

# === BNBroker: operator-managed manual exchange rates ===
from decimal import Decimal
from django.core.exceptions import ValidationError


class ExchangeRate(models.Model):
    """Current operator-entered RUB price per one crypto unit, for a direction.

    This is an editable rate catalogue, NOT a client quote. Existing quotes
    must keep their historical snapshot and must not change when this changes.
    """

    direction = models.OneToOneField(
        'exchange.ExchangeDirection',
        related_name='manual_rate',
        on_delete=models.PROTECT,
        verbose_name='Направление обмена',
    )
    rate = models.DecimalField(
        'Курс (RUB за 1 единицу криптовалюты)',
        max_digits=30,
        decimal_places=12,
        validators=[MinValueValidator(Decimal('0.000000000001'))],
        help_text='Например, 95.50 RUB за 1 USDT. Для покупки и продажи отдельные направления.',
    )
    is_active = models.BooleanField('Курс активен', default=False, db_index=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='+',
        verbose_name='Последнее изменение',
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Ручной курс обмена'
        verbose_name_plural = 'Ручные курсы обмена'
        ordering = ('direction_id',)

    def clean(self):
        super().clean()
        if self.direction_id:
            d = self.direction
            if {d.from_kind, d.to_kind} != {'fiat', 'crypto'}:
                raise ValidationError({
                    'direction': 'Для этого тарифа выберите направление RUB ↔ криптовалюта.'
                })

    def __str__(self):
        return f'{self.direction}: {self.rate} RUB'


class ExchangeRateChange(models.Model):
    """Immutable-by-admin rate change journal."""

    direction = models.ForeignKey(
        'exchange.ExchangeDirection',
        on_delete=models.PROTECT,
        related_name='rate_change_events',
        verbose_name='Направление',
    )
    old_rate = models.DecimalField('Старый курс', max_digits=30, decimal_places=12, null=True, blank=True)
    new_rate = models.DecimalField('Новый курс', max_digits=30, decimal_places=12)
    old_active = models.BooleanField('Раньше активен', null=True, blank=True)
    new_active = models.BooleanField('Теперь активен')
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='Изменил',
    )
    changed_at = models.DateTimeField('Когда', default=timezone.now, db_index=True)

    class Meta:
        verbose_name = 'Изменение ручного курса'
        verbose_name_plural = 'История изменения курсов'
        ordering = ('-changed_at',)

    def __str__(self):
        return f'{self.direction} — {self.changed_at:%d.%m.%Y %H:%M}'

