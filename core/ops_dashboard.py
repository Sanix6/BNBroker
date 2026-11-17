"""Restricted Unfold dashboard: reads existing data, never mutates orders."""
from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone

from apps.users.models import User
from apps.exchange.models import ExchangeOrder, ExchangeQuote, ExchangeDirection, ExchangeRate
from apps.kyc.models import KYCVerification


def dashboard_callback(request, context):
    now = timezone.now()
    user = request.user
    can_orders = user.has_perm('exchange.view_exchangeorder')
    can_rates = user.has_perm('exchange.view_exchangerate')
    can_kyc = user.has_perm('kyc.view_kycverification')
    can_users = user.has_perm('users.view_user')

    values = {
        'can_orders': can_orders,
        'can_rates': can_rates,
        'can_kyc': can_kyc,
        'can_users': can_users,
        'report_generated_at': now,
        'admin_rates_url': reverse('bnb_ops_rates') if can_rates else '',
        'admin_rate_add_url': reverse('bnb_ops_rates') if user.has_perm('exchange.add_exchangerate') else '',
        'admin_directions_url': reverse('bnb_ops_directions') if user.has_perm('exchange.view_exchangedirection') else '',
        'admin_orders_url': reverse('bnb_ops_orders') if can_orders else '',
        'admin_kyc_url': reverse('bnb_ops_applicants') if can_kyc else '',
        'admin_users_url': reverse('bnb_ops_users') if can_users else '',
    }

    if can_orders:
        qs = ExchangeOrder.objects.select_related('user', 'quote', 'quote__asset_network')
        # These are outstanding unpaid orders past their quote expiry;
        # they are NOT silently marked expired by this read-only dashboard.
        values.update({
            'orders_total': qs.count(),
            'orders_today': qs.filter(created_at__date=timezone.localdate()).count(),
            'orders_waiting': qs.filter(status='awaiting_payment').count(),
            'orders_review': qs.filter(status='payment_review').count(),
            'orders_processing': qs.filter(status__in=['paid', 'processing']).count(),
            'orders_completed': qs.filter(status='completed').count(),
            'orders_overdue': qs.filter(status='awaiting_payment', quote__expires_at__lte=now).count(),
            'orders_recent': list(qs.order_by('-created_at')[:10]),
            'quotes_active': ExchangeQuote.objects.filter(expires_at__gt=now).count(),
        })

        # Completed RUB gross volume, not profit or revenue.
        total = qs.filter(status='completed').aggregate(total=Sum('quote__fiat_amount'))['total']
        values['completed_fiat_amount'] = total or 0

        start = timezone.localdate() - timedelta(days=6)
        grouped = (
            qs.filter(created_at__date__gte=start)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(total=Count('pk'))
            .order_by('day')
        )
        map_days = {row['day']: row['total'] for row in grouped}
        daily = [{'label': (start + timedelta(days=i)).strftime('%d.%m'),
                  'count': map_days.get(start + timedelta(days=i), 0)} for i in range(7)]
        highest = max([1] + [day['count'] for day in daily])
        for day in daily:
            day['percent'] = max(5, round(day['count'] * 100 / highest)) if day['count'] else 0
        values['orders_chart'] = daily

    if can_rates:
        values.update({
            'rates_total': ExchangeRate.objects.count(),
            'rates_active': ExchangeRate.objects.filter(is_active=True).count(),
            'directions_active': ExchangeDirection.objects.filter(is_active=True).count(),
            'rates_recent': list(ExchangeRate.objects.select_related('direction', 'updated_by').order_by('-updated_at')[:8]),
        })

    if can_users:
        values.update({
            'users_total': User.objects.count(),
            'users_individual': User.objects.filter(account_type='individual').count(),
            'users_legal': User.objects.filter(account_type='legal').count(),
            'users_new_today': User.objects.filter(date_joined__date=timezone.localdate()).count(),
        })

    if can_kyc:
        values.update({
            'kyc_pending': KYCVerification.objects.filter(status='pending').count(),
            'kyc_error': KYCVerification.objects.filter(status='error').count(),
            'kyc_approved': KYCVerification.objects.filter(status='approved').count(),
            'kyc_recent': list(KYCVerification.objects.select_related('user').order_by('-created_at')[:8]),
        })

    context.update(values)
    return context
