from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.kyc.models import KYCVerification
from apps.compliance.models import AMLCheck
from .models import ExchangeQuote, ExchangeOrder, PaymentReceipt, ExchangeReport
from .serializers import (QuoteSerializer, OrderCreateSerializer, OrderSerializer,
                          PaymentSerializer, ReceiptUploadSerializer, ReceiptSerializer, ReportSerializer)

class DirectionsView(APIView):
    """Public fiat/crypto directions based on enabled network operations."""
    permission_classes = [AllowAny]

    def get(self, request):
        from django.db.models import Q
        from apps.crypto.models import CryptoNetwork

        networks = CryptoNetwork.objects.filter(
            Q(deposit_enabled=True) | Q(withdrawal_enabled=True),
            is_active=True, asset__is_active=True, network__is_active=True,
        ).select_related('asset', 'network').order_by(
            'asset__symbol', 'network__code', 'pk'
        )
        result = []
        for item in networks:
            common = {
                'asset_network_id': item.pk,
                'network': item.network.code,
            }
            if item.withdrawal_enabled:
                result.append({**common, 'id': f'{item.pk}:buy',
                               'from_currency': 'RUB', 'to_currency': item.asset.symbol})
            if item.deposit_enabled:
                result.append({**common, 'id': f'{item.pk}:sell',
                               'from_currency': item.asset.symbol, 'to_currency': 'RUB'})
        return Response(result)


class QuotesView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = QuoteSerializer
    def get_queryset(self):
        return ExchangeQuote.objects.filter(user=self.request.user, expires_at__gt=timezone.now()).order_by('-created_at')

class OrdersView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    def get_queryset(self):
        return ExchangeOrder.objects.filter(user=self.request.user).select_related('quote')

class OrderCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=OrderCreateSerializer, responses={201: OrderSerializer}, tags=['Exchange'])
    def post(self, request):
        s = OrderCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if not KYCVerification.objects.filter(user=request.user, status=KYCVerification.Status.APPROVED).exists():
            raise PermissionDenied('Необходимо пройти KYC')
        with transaction.atomic():
            quote = get_object_or_404(ExchangeQuote.objects.select_for_update(), pk=d['quote_id'], user=request.user)
            if not quote.is_valid:
                raise ValidationError({'quote_id': 'Срок действия курса истёк'})
            if ExchangeOrder.objects.filter(quote=quote).exists():
                raise ValidationError({'quote_id': 'Котировка уже использована'})
            if not quote.asset_network.is_active or not quote.asset_network.network.is_active or not quote.asset_network.asset.is_active:
                raise ValidationError('Валюта или сеть отключена')
            if quote.side == 'buy' and not quote.asset_network.withdrawal_enabled:
                raise ValidationError('Вывод по этой сети отключён')
            if quote.side == 'sell' and not quote.asset_network.deposit_enabled:
                raise ValidationError('Приём по этой сети отключён')
            check = None
            if quote.asset_network.aml_screening_required:
                if not d.get('aml_check_id'):
                    raise ValidationError({'aml_check_id': 'Требуется проверка кошелька Ranex'})
                check = get_object_or_404(AMLCheck, pk=d['aml_check_id'], user=request.user,
                    asset_network=quote.asset_network, kind=AMLCheck.Kind.ADDRESS,
                    address=d['wallet_address'], status=AMLCheck.Status.COMPLETED,
                    decision=AMLCheck.Decision.APPROVED)
            order = ExchangeOrder.objects.create(user=request.user, quote=quote,
                wallet_address=d['wallet_address'], wallet_memo=d.get('wallet_memo', ''), aml_check=check)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    def get_queryset(self):
        return ExchangeOrder.objects.filter(user=self.request.user).select_related('quote')

class PaymentView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentSerializer
    def get_queryset(self):
        return ExchangeOrder.objects.filter(user=self.request.user)

class ReceiptUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request=ReceiptUploadSerializer, responses={201: ReceiptSerializer}, tags=['Exchange'])
    def post(self, request, pk):
        s = ReceiptUploadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        f = s.validated_data['file']
        if f.size > 5 * 1024 * 1024:
            raise ValidationError({'file': 'Максимальный размер 5 МБ'})
        if f.content_type not in {'image/jpeg', 'image/png', 'application/pdf'}:
            raise ValidationError({'file': 'Разрешены только JPEG, PNG, PDF'})
        with transaction.atomic():
            order = get_object_or_404(ExchangeOrder.objects.select_for_update(), pk=pk, user=request.user)
            if order.status not in {ExchangeOrder.Status.AWAITING_PAYMENT, ExchangeOrder.Status.PAYMENT_REVIEW}:
                raise ValidationError('Для этой заявки загрузка квитанции недоступна')
            receipt = PaymentReceipt.objects.create(order=order, file=f)
            order.status = ExchangeOrder.Status.PAYMENT_REVIEW
            order.save(update_fields=['status', 'updated_at'])
        return Response(ReceiptSerializer(receipt).data, status=status.HTTP_201_CREATED)

class PaymentConfirmationView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(request=None, responses={200: OrderSerializer}, tags=['Exchange'])
    def post(self, request, pk):
        with transaction.atomic():
            order = get_object_or_404(ExchangeOrder.objects.select_for_update(), pk=pk, user=request.user)
            if order.status not in {ExchangeOrder.Status.AWAITING_PAYMENT, ExchangeOrder.Status.PAYMENT_REVIEW}:
                raise ValidationError('Нельзя подтвердить оплату в текущем статусе')
            order.status = ExchangeOrder.Status.PAYMENT_REVIEW
            order.save(update_fields=['status', 'updated_at'])
        return Response(OrderSerializer(order).data)

class ReportView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(responses={200: ReportSerializer}, tags=['Exchange'])
    def get(self, request, pk):
        order = get_object_or_404(ExchangeOrder, pk=pk, user=request.user, status=ExchangeOrder.Status.COMPLETED)
        report = get_object_or_404(ExchangeReport, order=order)
        return Response(ReportSerializer(report).data)
