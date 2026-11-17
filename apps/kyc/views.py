
import logging

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .models import KYCVerification
from .serializers import (
    KYCSerializer,
    KYCMeSerializer,
    KYCStartSerializer,
    KYCStartResponseSerializer,
)
from .services import start_kyc, refresh_kyc_status

logger = logging.getLogger(__name__)


class KYCStartThrottle(UserRateThrottle):
    rate = "3/hour"


class KYCMeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["KYC Verification"],
        summary="Получить статус верификации",
        responses={200: KYCMeSerializer},
    )
    def get(self, request):
        record = (
            KYCVerification.objects
            .filter(user=request.user)
            .first()
        )

        if record is None:
            return Response({
                "status": "not_started",
                "verification": None,
            })

        return Response({
            "status": record.status,
            "verification": KYCSerializer(record).data,
        })


class KYCStartView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [KYCStartThrottle]

    @extend_schema(
        tags=["KYC Verification"],
        summary="Начать верификацию через Ranex",
        request=KYCStartSerializer,
        responses={200: KYCStartResponseSerializer},
    )
    def post(self, request):
        user = request.user

        if not user.is_email_verified:
            return Response(
                {"detail": "Сначала подтвердите email"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.account_type != "individual":
            return Response(
                {"detail": "Для юридических лиц требуется отдельный процесс KYC"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = (
            KYCVerification.objects
            .filter(user=user)
            .first()
        )

        if existing and existing.status == "approved":
            return Response(
                {"detail": "Верификация уже пройдена"},
                status=status.HTTP_409_CONFLICT,
            )

        if existing and existing.status == "pending":
            return Response(
                {"detail": "Верификация уже находится на рассмотрении"},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = KYCStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        applicant_data = {
            "email": user.email,
            "firstName": data["first_name"],
            "lastName": data["last_name"],
        }

        if data.get("phone"):
            applicant_data["phone"] = data["phone"]

        try:
            record, session = start_kyc(
                user=user,
                applicant_data=applicant_data,
            )
        except Exception:
            logger.exception(
                "KYC start failed for user %s",
                user.pk,
            )
            return Response(
                {"detail": "Не удалось запустить верификацию"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        verification_url = (
            session.get("verificationUrl")
            or session.get("applicantLink")
            or session.get("url")
        )

        if (
            not isinstance(verification_url, str)
            or not verification_url.startswith("https://")
        ):
            return Response(
                {"detail": "Ranex не вернул корректную ссылку"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({
            "verification": KYCSerializer(record).data,
            "verification_url": verification_url,
        })


class KYCRefreshView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [KYCStartThrottle]

    @extend_schema(
        tags=["KYC Verification"],
        summary="Обновить статус KYC из Ranex",
        responses={200: KYCSerializer},
    )
    def post(self, request):
        record = (
            KYCVerification.objects
            .filter(user=request.user)
            .first()
        )

        if record is None:
            return Response(
                {"detail": "Верификация не начата"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if record.status == "approved":
            return Response(KYCSerializer(record).data)

        try:
            record = refresh_kyc_status(record=record)
        except Exception:
            logger.exception(
                "KYC status refresh failed for %s",
                request.user.pk,
            )
            return Response(
                {"detail": "Не удалось получить статус Ranex"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(KYCSerializer(record).data)
