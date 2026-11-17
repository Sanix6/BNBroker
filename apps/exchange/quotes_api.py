"""POST creates a user-owned 30-minute quote from an operator-managed rate."""
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import ExchangeDirection, ExchangeQuote, ExchangeRate
from .quote_math import QuoteAmountError, calculate_amounts
from .serializers import QuoteSerializer
from .views import QuotesView


class QuoteCreateSerializer(serializers.Serializer):
    direction_id = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(
        max_digits=30, decimal_places=12,
        min_value=Decimal('0.000000000001'),
    )
    amount_side = serializers.ChoiceField(
        choices=('from', 'to'), required=False, default='from',
        help_text='from: amount being sent, to: amount customer wishes to receive',
    )


class QuoteListCreateView(QuotesView):
    """GET keeps existing quote listing. POST snapshots current manual rate."""

    @extend_schema(request=QuoteCreateSerializer, responses={201: QuoteSerializer}, tags=['Exchange'])
    def post(self, request, *args, **kwargs):
        incoming = QuoteCreateSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        value = incoming.validated_data

        with transaction.atomic():
            # Avoid select_related() to nullable network FKs here: PostgreSQL
            # cannot SELECT ... FOR UPDATE the nullable side of an OUTER JOIN.
            direction = (ExchangeDirection.objects.select_for_update()
                .filter(pk=value['direction_id']).first())
            if direction is None or not direction.is_active:
                raise ValidationError({'direction_id': 'Направление обмена недоступно'})
            if {direction.from_kind, direction.to_kind} != {'fiat', 'crypto'}:
                raise ValidationError({'direction_id': 'Для направления нет ручного курса RUB'})

            # Match the same network eligibility rules as GET /directions/.
            from .direction_api import active_directions
            if not active_directions().filter(pk=direction.pk).exists():
                raise ValidationError({'direction_id': 'Валюта или сеть сейчас недоступна'})

            current = (ExchangeRate.objects.select_for_update()
                .filter(direction_id=direction.pk).first())
            if current is None or not current.is_active or current.rate <= 0:
                raise ValidationError({'direction_id': 'Активный курс для направления не установлен'})

            crypto_network = (direction.to_asset_network if direction.from_kind == 'fiat'
                              else direction.from_asset_network)
            try:
                fiat_amount, crypto_amount = calculate_amounts(
                    from_kind=direction.from_kind,
                    to_kind=direction.to_kind,
                    rate=current.rate,
                    amount=value['amount'],
                    amount_side=value['amount_side'],
                    crypto_decimals=crypto_network.asset.decimals,
                )
            except QuoteAmountError as exc:
                raise ValidationError({'amount': str(exc)}) from exc

            quote = ExchangeQuote(
                user=request.user,
                side=(ExchangeQuote.Side.BUY if direction.from_kind == 'fiat'
                      else ExchangeQuote.Side.SELL),
                asset_network=crypto_network,
                fiat_currency='RUB',
                fiat_amount=fiat_amount,
                crypto_amount=crypto_amount,
                rate=current.rate,  # immutable snapshot for this quote
                expires_at=timezone.now() + timedelta(minutes=30),
            )
            try:
                quote.full_clean()
            except DjangoValidationError as exc:
                raise ValidationError({'amount': exc.messages}) from exc
            quote.save()

        return Response(QuoteSerializer(quote).data, status=status.HTTP_201_CREATED)
