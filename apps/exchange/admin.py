from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from unfold.admin import ModelAdmin
from .models import ExchangeQuote, ExchangeOrder, PaymentReceipt, ExchangeReport

@admin.register(ExchangeQuote)
class ExchangeQuoteAdmin(ModelAdmin):
    list_display = ('id', 'user', 'side', 'asset_network', 'fiat_amount', 'crypto_amount', 'rate', 'expires_at')
    list_filter = ('side', 'fiat_currency')
    readonly_fields = ('id', 'user', 'side', 'asset_network', 'fiat_currency', 'fiat_amount', 'crypto_amount', 'rate', 'expires_at', 'created_at')
    def has_add_permission(self, request):
        return False

class ExchangeOrderAdminForm(forms.ModelForm):
    class Meta:
        model = ExchangeOrder
        fields = '__all__'

    def clean(self):
        data = super().clean()
        if not self.instance.pk:
            return data
        old = ExchangeOrder.objects.get(pk=self.instance.pk)
        new_status = data.get('status', old.status)
        transitions = {
            'awaiting_payment': {'payment_review', 'cancelled', 'rejected'},
            'payment_review': {'paid', 'cancelled', 'rejected'},
            'paid': {'processing'},
            'processing': {'completed', 'rejected'},
            'completed': set(), 'cancelled': set(), 'rejected': set(),
        }
        if new_status != old.status and new_status not in transitions.get(old.status, set()):
            raise ValidationError('Недопустимый переход статуса заявки')
        if new_status == 'completed' and not data.get('txid'):
            raise ValidationError('Для завершения требуется TxID')
        return data

@admin.register(ExchangeOrder)
class ExchangeOrderAdmin(ModelAdmin):
    form = ExchangeOrderAdminForm
    list_display = ('id', 'user', 'status', 'created_at', 'completed_at')
    list_filter = ('status',)
    search_fields = ('user__email', 'id', 'txid')
    readonly_fields = ('id', 'user', 'quote', 'wallet_address', 'wallet_memo', 'aml_check', 'created_at', 'updated_at', 'paid_at', 'completed_at')
    def has_add_permission(self, request):
        return False
    def save_model(self, request, obj, form, change):
        if change:
            old = ExchangeOrder.objects.get(pk=obj.pk)
            if old.status != obj.status:
                if obj.status == 'paid':
                    obj.paid_at = timezone.now()
                if obj.status == 'completed':
                    obj.completed_at = timezone.now()
        super().save_model(request, obj, form, change)

@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(ModelAdmin):
    list_display = ('id', 'order', 'uploaded_at')
    readonly_fields = ('id', 'order', 'file', 'uploaded_at')
    def has_add_permission(self, request):
        return False

@admin.register(ExchangeReport)
class ExchangeReportAdmin(ModelAdmin):
    list_display = ('id', 'order', 'created_at')
    def has_add_permission(self, request):
        return False


from .models import ExchangeDirection


@admin.register(ExchangeDirection)
class ExchangeDirectionAdmin(ModelAdmin):
    list_display = ('id', 'from_kind', 'from_asset_network', 'to_kind', 'to_asset_network', 'is_active')
    list_display_links = ('id',)
    list_editable = ('is_active',)
    list_filter = ('is_active', 'from_kind', 'to_kind')
    list_select_related = ('from_asset_network', 'to_asset_network')
    autocomplete_fields = ()
    fields = ('from_kind', 'from_asset_network', 'to_kind', 'to_asset_network', 'is_active')
    actions = ('enable_selected', 'disable_selected')

    @admin.action(description='Включить выбранные направления')
    def enable_selected(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'Включено: {count}')

    @admin.action(description='Отключить выбранные направления')
    def disable_selected(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'Отключено: {count}')

# Register manual rates and audit in Django Unfold
from . import rates_admin
