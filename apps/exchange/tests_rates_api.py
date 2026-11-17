"""API tests run ONLY against Django's separate TEST database.

Run: python manage.py test apps.exchange.tests_rates_api --verbosity 2
No Ranex or other external network calls.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.crypto.models import BlockchainNetwork, Cryptocurrency, CryptoNetwork
from apps.exchange.direction_api import ExchangeDirectionsView
from apps.exchange.models import ExchangeDirection, ExchangeQuote, ExchangeRate
from apps.exchange.quotes_api import QuoteListCreateView
from apps.users.models import User


class ManualRatesAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email='quotes-test@example.test', password='correct-dummy-test-secret')
        cls.asset = Cryptocurrency.objects.create(symbol='USDT', name='Tether', decimals=6)
        cls.blockchain = BlockchainNetwork.objects.create(code='trc20', name='Tron')
        cls.network = CryptoNetwork.objects.create(
            asset=cls.asset, network=cls.blockchain,
            deposit_enabled=True, withdrawal_enabled=True, is_active=True,
            aml_screening_required=False,
        )
        cls.buy = ExchangeDirection.objects.create(
            from_kind='fiat', to_kind='crypto',
            to_asset_network=cls.network, is_active=True,
        )
        cls.sell = ExchangeDirection.objects.create(
            from_kind='crypto', from_asset_network=cls.network,
            to_kind='fiat', is_active=True,
        )
        cls.buy_rate = ExchangeRate.objects.create(direction=cls.buy, rate=Decimal('95.50'), is_active=True)
        cls.sell_rate = ExchangeRate.objects.create(direction=cls.sell, rate=Decimal('94.20'), is_active=True)

    def setUp(self):
        self.factory = APIRequestFactory()

    def directions(self):
        return ExchangeDirectionsView.as_view()(self.factory.get('/api/v1/exchange/directions/'))

    def create_quote(self, **payload):
        request = self.factory.post('/api/v1/exchange/quotes/', payload, format='json')
        force_authenticate(request, user=self.user)
        return QuoteListCreateView.as_view()(request)

    def test_directions_have_independent_buy_and_sell_rates(self):
        response = self.directions()
        self.assertEqual(response.status_code, 200)
        pairs = {row['id']: row for row in response.data}
        self.assertEqual(pairs[self.buy.pk]['rate'], '95.500000000000')
        self.assertEqual(pairs[self.sell.pk]['rate'], '94.200000000000')
        self.assertEqual(pairs[self.buy.pk]['rate_unit'], 'RUB/USDT')
        self.assertEqual(pairs[self.sell.pk]['rate_unit'], 'RUB/USDT')
        self.assertTrue(pairs[self.buy.pk]['is_active'])
        self.assertEqual(pairs[self.buy.pk]['quote_validity_seconds'], 1800)
        self.assertEqual(pairs[self.sell.pk]['network'], 'trc20')

    def test_unpriced_or_disabled_rate_is_unavailable(self):
        self.buy_rate.is_active = False
        self.buy_rate.save(update_fields=['is_active'])
        response = self.directions()
        pair = next(x for x in response.data if x['id'] == self.buy.pk)
        self.assertFalse(pair['is_active'])
        self.assertIsNone(pair['rate'])
        create = self.create_quote(direction_id=self.buy.pk, amount='955.00')
        self.assertEqual(create.status_code, 400)
        self.assertEqual(ExchangeQuote.objects.count(), 0)

        self.buy_rate.delete()
        response = self.directions()
        pair = next(x for x in response.data if x['id'] == self.buy.pk)
        self.assertIsNone(pair['rate'])

    def test_quote_buy_and_30_minute_expiry(self):
        before = timezone.now()
        response = self.create_quote(direction_id=self.buy.pk, amount='955.00', amount_side='from')
        after = timezone.now()
        self.assertEqual(response.status_code, 201, response.data)
        quote = ExchangeQuote.objects.get()
        self.assertEqual(quote.side, 'buy')
        self.assertEqual(quote.fiat_amount, Decimal('955.00'))
        self.assertEqual(quote.crypto_amount, Decimal('10.000000'))
        self.assertEqual(quote.rate, Decimal('95.50'))
        self.assertGreaterEqual(quote.expires_at, before + timedelta(minutes=30))
        self.assertLessEqual(quote.expires_at, after + timedelta(minutes=30))

        self.buy_rate.rate = Decimal('105.00')
        self.buy_rate.save(update_fields=['rate'])
        quote.refresh_from_db()
        self.assertEqual(quote.rate, Decimal('95.50'))
        self.assertEqual(quote.fiat_amount, Decimal('955.00'))

    def test_quote_sell_from_crypto(self):
        response = self.create_quote(direction_id=self.sell.pk, amount='10', amount_side='from')
        self.assertEqual(response.status_code, 201, response.data)
        quote = ExchangeQuote.objects.get()
        self.assertEqual(quote.side, 'sell')
        self.assertEqual(quote.fiat_amount, Decimal('942.00'))
        self.assertEqual(quote.crypto_amount, Decimal('10'))

    def test_quote_reverse_calculation(self):
        response = self.create_quote(direction_id=self.buy.pk, amount='5', amount_side='to')
        self.assertEqual(response.status_code, 201, response.data)
        quote = ExchangeQuote.objects.get()
        self.assertEqual(quote.crypto_amount, Decimal('5'))
        self.assertEqual(quote.fiat_amount, Decimal('477.50'))

    def test_invalid_precision_and_zero(self):
        response = self.create_quote(direction_id=self.buy.pk, amount='1.001')
        self.assertEqual(response.status_code, 400)
        response = self.create_quote(direction_id=self.sell.pk, amount='1.1234567')
        self.assertEqual(response.status_code, 400)
        response = self.create_quote(direction_id=self.buy.pk, amount='0')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ExchangeQuote.objects.exists())

    def test_blocked_direction_cannot_create_quote(self):
        self.buy.is_active = False
        self.buy.save(update_fields=['is_active'])
        response = self.create_quote(direction_id=self.buy.pk, amount='955')
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_quote_post_rejected(self):
        request = self.factory.post('/api/v1/exchange/quotes/',
                                    {'direction_id': self.buy.pk, 'amount': '100.00'}, format='json')
        response = QuoteListCreateView.as_view()(request)
        self.assertIn(response.status_code, (401, 403))

    def test_existing_get_quotes_is_preserved(self):
        request = self.factory.get('/api/v1/exchange/quotes/')
        force_authenticate(request, user=self.user)
        response = QuoteListCreateView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.data), [])
