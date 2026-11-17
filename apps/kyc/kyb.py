"""KYB launch endpoint. Webhook decisions are handled in a separate patch."""
import logging
from django.conf import settings
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.integrations.ranex_compliance.client import RanexComplianceClient
from apps.integrations.ranex_compliance.exceptions import RanexComplianceResponseError
from .models import KYCVerification
from .serializers import KYCSerializer, KYCStartResponseSerializer

logger = logging.getLogger(__name__)


class KYBStartSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=255)
    registration_number = serializers.CharField(max_length=128)
    legal_form = serializers.CharField(max_length=128, required=False)
    incorporation_date = serializers.DateField(required=False)
    registered_address = serializers.CharField(max_length=512, required=False)
    country = serializers.CharField(max_length=100, required=False)
    phone = serializers.CharField(max_length=32, required=False)


class KYBStartThrottle(UserRateThrottle):
    rate = "3/hour"


class KYBStartView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [KYBStartThrottle]

    @extend_schema(
        tags=["KYC Verification"],
        summary="Начать KYB юридического лица через Ranex",
        request=KYBStartSerializer,
        responses={200: KYCStartResponseSerializer},
    )
    def post(self, request):
        user = request.user
        if not user.is_active or not user.is_email_verified:
            return Response({"detail": "Подтвердите email"}, status=403)
        if user.account_type != "legal":
            return Response({"detail": "KYB доступен только юридическим лицам"}, status=400)
        serializer = KYBStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        existing = KYCVerification.objects.filter(user=user).first()
        if existing and existing.status in ("approved", "pending"):
            return Response({"detail": "Верификация уже начата или завершена"}, status=409)

        data = serializer.validated_data
        level = settings.RUNEX_CATEGORY_KYB_LEVEL
        applicant_payload = {
            "externalUserId": str(user.pk),
            "type": "company",
            "verificationLevelName": level,
            "companyName": data["company_name"],
            "taxId": data["registration_number"],
            "email": user.email,
        }
        for source, target in (
            ("legal_form", "legalForm"),
            ("registered_address", "registeredAddress"),
            ("country", "country"),
            ("phone", "phone"),
        ):
            if data.get(source):
                applicant_payload[target] = data[source]
        if data.get("incorporation_date"):
            applicant_payload["incorporationDate"] = data["incorporation_date"].isoformat()

        # No network calls under a database lock.
        try:
            client = RanexComplianceClient()
            try:
                applicant = client.create_applicant(applicant_payload)
            except RanexComplianceResponseError as exc:
                if exc.status_code != 409:
                    raise
                applicant = client.get_applicant(str(user.pk))
            verification = client.create_verification(str(user.pk), level_name=level)
            sdk_link = verification.get("sdkLink") or {}
            if not isinstance(sdk_link, dict):
                sdk_link = {}
            url = (verification.get("url") or verification.get("verificationUrl")
                   or sdk_link.get("url"))
            applicant_id = applicant.get("id") or applicant.get("applicantId")
            if not isinstance(url, str) or not url.startswith("https://") or not applicant_id:
                raise ValueError("Ranex не вернул ссылку или applicant ID")
        except Exception:
            logger.exception("KYB start failed for user %s", user.pk)
            return Response({"detail": "Не удалось запустить KYB"}, status=502)

        with transaction.atomic():
            # Serialize writes for this user and do not override a completed check.
            type(user).objects.select_for_update().get(pk=user.pk)
            latest = KYCVerification.objects.filter(user=user).first()
            if latest and latest.status in ("approved", "pending"):
                return Response({"detail": "Статус проверки изменился, обновите страницу"}, status=409)
            record = KYCVerification.objects.create(
                user=user, level_name=level, status=KYCVerification.Status.PENDING,
                external_applicant_id=str(applicant_id)[:128],
                external_check_id=str(verification.get("id") or verification.get("sessionId") or "")[:128],
            )
        return Response({"verification": KYCSerializer(record).data, "verification_url": url})
