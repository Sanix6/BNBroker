from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import BlockchainNetwork, Cryptocurrency, CryptoNetwork, CryptoAddress

@admin.register(BlockchainNetwork)
class BlockchainNetworkAdmin(ModelAdmin):
    list_display = ("code","name","ranex_network_code","is_active")
    list_filter = ("is_active",)
    search_fields = ("code","name")
    list_per_page = 30

@admin.register(Cryptocurrency)
class CryptocurrencyAdmin(ModelAdmin):
    list_display = ("symbol","name","decimals","is_active","sort_order")
    list_filter = ("is_active",)
    search_fields = ("symbol","name")
    list_per_page = 30

@admin.register(CryptoNetwork)
class CryptoNetworkAdmin(ModelAdmin):
    list_display = ("asset","network","deposit_enabled","withdrawal_enabled","aml_screening_required","is_active")
    list_filter = ("is_active","aml_screening_required","network")
    search_fields = ("asset__symbol","network__code")
    list_per_page = 30

@admin.register(CryptoAddress)
class CryptoAddressAdmin(ModelAdmin):
    list_display = ("address","asset_network","purpose","user","is_active","created_at")
    list_filter = ("purpose","is_active","asset_network__network")
    search_fields = ("address","user__email")
    list_per_page = 30

