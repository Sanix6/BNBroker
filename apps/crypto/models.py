import uuid
from django.core.validators import MinValueValidator
from django.db import models

class BlockchainNetwork(models.Model):
    code = models.SlugField(max_length=32, unique=True, verbose_name="Код сети")
    name = models.CharField(max_length=100, verbose_name="Название сети")
    chain_id = models.CharField(max_length=80, blank=True, verbose_name="Chain ID")
    explorer_url = models.URLField(blank=True, verbose_name="Block explorer")
    ranex_network_code = models.CharField(max_length=80, blank=True, verbose_name="Код сети в Ranex")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = "Блокчейн-сеть"
        verbose_name_plural = "Блокчейн-сети"
        ordering = ["name"]
    def __str__(self): return f"{self.name} ({self.code})"

class Cryptocurrency(models.Model):
    symbol = models.CharField(max_length=20, unique=True, verbose_name="Тикер")
    name = models.CharField(max_length=100, verbose_name="Название")
    icon = models.ImageField(upload_to="crypto/icons/", blank=True, null=True)
    decimals = models.PositiveSmallIntegerField(default=8)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = "Криптовалюта"
        verbose_name_plural = "Криптовалюты"
        ordering = ["sort_order", "symbol"]
    def __str__(self): return self.symbol

class CryptoNetwork(models.Model):
    asset = models.ForeignKey(Cryptocurrency, on_delete=models.PROTECT, related_name="networks")
    network = models.ForeignKey(BlockchainNetwork, on_delete=models.PROTECT, related_name="assets")
    token_contract = models.CharField(max_length=255, blank=True, verbose_name="Контракт токена")
    min_confirmations = models.PositiveSmallIntegerField(default=1)
    deposit_enabled = models.BooleanField(default=False)
    withdrawal_enabled = models.BooleanField(default=False)
    aml_screening_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    class Meta:
        verbose_name = "Криптовалюта в сети"
        verbose_name_plural = "Криптовалюты по сетям"
        constraints = [models.UniqueConstraint(fields=["asset","network"], name="unique_crypto_asset_network")]
    def __str__(self): return f"{self.asset.symbol} / {self.network.code}"

class CryptoAddress(models.Model):
    class Purpose(models.TextChoices):
        CUSTOMER = "customer", "Адрес клиента"
        COMPANY = "company", "Адрес компании"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.PROTECT, null=True, blank=True, related_name="crypto_addresses")
    asset_network = models.ForeignKey(CryptoNetwork, on_delete=models.PROTECT, related_name="addresses")
    address = models.CharField(max_length=255)
    memo = models.CharField(max_length=255, blank=True, verbose_name="Memo / Tag")
    purpose = models.CharField(max_length=16, choices=Purpose.choices, default=Purpose.CUSTOMER)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    
    class Meta:
        verbose_name = "Криптоадрес"
        verbose_name_plural = "Криптоадреса"
        indexes = [models.Index(fields=["address"], name="crypto_address_lookup_idx")]
        constraints = [models.UniqueConstraint(fields=["asset_network","address","memo","purpose"], name="unique_crypto_address_scope")]
    def __str__(self): return f"{self.asset_network}: {self.address[:18]}…"
