from decimal import Decimal, InvalidOperation
from django.utils import timezone
from apps.compliance.models import AMLCheck
from apps.integrations.ranex.client import RanexClient
from apps.integrations.ranex.constants import RanexNetwork


def screen_crypto_address(*, asset_network, address, user=None, crypto_address=None):
    network = (asset_network.network.ranex_network_code or asset_network.network.code).strip().lower()
    if network not in RanexNetwork.SUPPORTED:
        raise ValueError(f"Сеть {network} не поддерживается клиентом Ranex")
    if not asset_network.is_active or not asset_network.aml_screening_required:
        raise ValueError("AML-проверка отключена для данной пары")
    address = (address or '').strip()
    if not address or len(address) > 255:
        raise ValueError("Укажите корректный адрес")
    if crypto_address and (crypto_address.asset_network_id != asset_network.pk or crypto_address.address != address):
        raise ValueError("Криптоадрес не соответствует выбранной сети")
    check = AMLCheck.objects.create(
        user=user, asset_network=asset_network, crypto_address=crypto_address,
        kind=AMLCheck.Kind.ADDRESS, address=address,
        status=AMLCheck.Status.PENDING, decision=AMLCheck.Decision.PENDING,
    )
    try:
        response = RanexClient().screen_address(network=network, address=address)
        risk_info = (response.get('risk') or {}).get('riskInfo') or {}
        score = risk_info.get('risk')
        try:
            score = Decimal(str(score)) if score is not None else None
        except (InvalidOperation, TypeError, ValueError):
            score = None
        reported = risk_info.get('reported') or {}
        check.risk_score = score
        check.risk_category = str(reported.get('name') or '')[:100]
        check.provider_check_id = str(response.get('id') or response.get('screeningId') or '')[:128]
        check.provider_payload = {'network': network, 'risk_category': check.risk_category}
        check.status = AMLCheck.Status.COMPLETED
        check.decision = AMLCheck.Decision.REVIEW
        check.screened_at = timezone.now()
        check.save()
        return check
    except Exception as exc:
        check.status = AMLCheck.Status.FAILED
        check.error_message = exc.__class__.__name__
        check.save(update_fields=['status','error_message','updated_at'])
        raise
