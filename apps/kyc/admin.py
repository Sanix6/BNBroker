from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import KYCVerification

@admin.register(KYCVerification)
class KYCVerificationAdmin(ModelAdmin):
    list_display = ("user","provider","status","external_applicant_id","verified_at","created_at")
    list_filter = ("status",)
    search_fields = ("user__email","external_applicant_id")
    list_per_page = 30

