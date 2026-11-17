from rest_framework import serializers
from .models import ExchangeQuote, ExchangeOrder, PaymentReceipt, ExchangeReport

class QuoteSerializer(serializers.ModelSerializer):
    is_valid = serializers.BooleanField(read_only=True)
    class Meta:
        model = ExchangeQuote
        fields = ['id', 'side', 'asset_network', 'fiat_currency', 'fiat_amount', 'crypto_amount', 'rate', 'expires_at', 'is_valid', 'created_at']
        read_only_fields = fields

class OrderCreateSerializer(serializers.Serializer):
    quote_id = serializers.UUIDField()
    wallet_address = serializers.CharField(max_length=255, trim_whitespace=True)
    wallet_memo = serializers.CharField(max_length=255, required=False, allow_blank=True)
    aml_check_id = serializers.UUIDField(required=False)

class OrderSerializer(serializers.ModelSerializer):
    quote = QuoteSerializer(read_only=True)
    class Meta:
        model = ExchangeOrder
        fields = ['id', 'quote', 'wallet_address', 'wallet_memo', 'status', 'payment_reference', 'txid', 'created_at', 'updated_at', 'paid_at', 'completed_at']
        read_only_fields = fields

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeOrder
        fields = ['id', 'status', 'payment_instructions', 'payment_reference']
        read_only_fields = fields

class ReceiptUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

class ReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentReceipt
        fields = ['id', 'uploaded_at']
        read_only_fields = fields

class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeReport
        fields = ['id', 'created_at']
        read_only_fields = fields
