from django.conf import settings
from django.utils import timezone
from apps.kyc.models import KYCVerification
from apps.integrations.ranex_compliance.client import RanexComplianceClient


def start_kyc(*, user, applicant_data):
    if not user.is_active:
        raise ValueError('Неактивный пользователь')
    level = settings.RANEX_COMPLIANCE_LEVEL_NAME
    record = KYCVerification.objects.create(user=user, level_name=level)
    client = RanexComplianceClient()
    try:
        payload = dict(applicant_data)
        payload['externalUserId'] = str(user.pk)
        applicant = client.create_applicant(payload)
        session = client.create_verification(str(user.pk), level_name=level)
        record.external_applicant_id = str(applicant.get('id') or applicant.get('applicantId') or '')[:128]
        record.external_check_id = str(session.get('id') or session.get('sessionId') or '')[:128]
        record.status = KYCVerification.Status.PENDING
        record.save(update_fields=['external_applicant_id','external_check_id','status','updated_at'])
        return record, session
    except Exception:
        record.status = KYCVerification.Status.ERROR
        record.save(update_fields=['status','updated_at'])
        raise


def refresh_kyc_status(*, record):
    response = RanexComplianceClient().get_status(str(record.user_id))
    status = str(response.get('reviewStatus') or response.get('status') or '').lower()
    answer = str(response.get('reviewAnswer') or '').upper()
    if status in {'completed', 'approved'} and answer in {'GREEN', 'APPROVED'}:
        record.status = KYCVerification.Status.APPROVED
        record.verified_at = timezone.now()
    elif status in {'completed', 'rejected'} and answer in {'RED', 'REJECTED'}:
        record.status = KYCVerification.Status.REJECTED
    else:
        record.status = KYCVerification.Status.PENDING
    record.save(update_fields=['status','verified_at','updated_at'])
    return record
