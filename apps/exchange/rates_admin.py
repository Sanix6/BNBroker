"""Django Unfold management for manual operator rates + immutable audit list."""
from django.contrib import admin
from django.db import transaction
from unfold.admin import ModelAdmin
from .models import ExchangeRate, ExchangeRateChange


@admin.register(ExchangeRate)
class ExchangeRateAdmin(ModelAdmin):
    list_display = ('direction', 'rate', 'is_active', 'updated_at', 'updated_by')
    list_display_links = ('direction',)
    list_editable = ('rate', 'is_active')
    list_filter = ('is_active', 'direction__from_kind', 'direction__to_kind')
    search_fields = (
        'direction__from_asset_network__asset__symbol',
        'direction__to_asset_network__asset__symbol',
        'direction__from_asset_network__network__code',
        'direction__to_asset_network__network__code',
    )
    readonly_fields = ('updated_at', 'created_at', 'updated_by')
    list_select_related = ('direction', 'updated_by')
    list_per_page = 40
    ordering = ('direction_id',)
    save_on_top = True

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            fields.append('direction')
        return tuple(fields)

    def has_delete_permission(self, request, obj=None):
        return False

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        previous = None
        if change:
            previous = (
                ExchangeRate.objects.select_for_update()
                .filter(pk=obj.pk)
                .values('rate', 'is_active')
                .first()
            )

        obj.updated_by = request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)

        if (previous is None
                or previous['rate'] != obj.rate
                or previous['is_active'] != obj.is_active):
            ExchangeRateChange.objects.create(
                direction=obj.direction,
                old_rate=previous['rate'] if previous else None,
                new_rate=obj.rate,
                old_active=previous['is_active'] if previous else None,
                new_active=obj.is_active,
                changed_by=request.user,
            )


@admin.register(ExchangeRateChange)
class ExchangeRateChangeAdmin(ModelAdmin):
    list_display = (
        'changed_at', 'direction', 'old_rate', 'new_rate',
        'old_active', 'new_active', 'changed_by',
    )
    list_filter = ('changed_at', 'new_active')
    search_fields = (
        'direction__from_asset_network__asset__symbol',
        'direction__to_asset_network__asset__symbol',
        'changed_by__email',
    )
    list_select_related = ('direction', 'changed_by')
    ordering = ('-changed_at',)
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
