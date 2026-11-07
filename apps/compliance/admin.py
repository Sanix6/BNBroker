from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import AMLCheck

@admin.register(AMLCheck)
class AMLCheckAdmin(ModelAdmin):
    list_display = ("kind","asset_network","status","decision","risk_score","created_at")
    list_filter = ("kind","status","decision")
    search_fields = ("address","txid","provider_check_id")
    list_per_page = 30

