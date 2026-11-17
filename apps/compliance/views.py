import logging
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.compliance.models import AMLCheck
from apps.compliance.serializers import (
    AMLAddressCheckSerializer,
    AMLCheckSerializer,
)
from apps.integrations.ranex.client import RanexClient
from apps.integrations.ranex.exceptions import RanexError

logger = logging.getLogger(__name__)


class AMLAddressCheckView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=AMLAddressCheckSerializer,
        responses={201: AMLCheckSerializer},
        tags=["AML"],
    )
    def post(self, request):
        serializer = AMLAddressCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        asset_network = serializer.validated_data["asset_network"]
        address = serializer.validated_data["address"]

        check = AMLCheck.objects.create(
            user=request.user,
            asset_network=asset_network,
            kind=AMLCheck.Kind.ADDRESS,
            address=address,
            status=AMLCheck.Status.PENDING,
            decision=AMLCheck.Decision.PENDING,
        )

        try:
            result = RanexClient().screen_address(
                network=asset_network.network.ranex_network_code,
                address=address,
            )

            # Проверяем вложенную структуру Ranex перед завершением проверки.
            if not isinstance(result, dict):
                raise ValueError("Invalid Ranex response")
            risk = result.get("risk")
            if not isinstance(risk, dict):
                raise ValueError("Missing Ranex risk data")
            errors = risk.get("errors")
            if not isinstance(errors, list) or errors:
                raise ValueError("Ranex risk errors or invalid errors field")
            risk_info = risk.get("riskInfo")
            if not isinstance(risk_info, dict):
                raise ValueError("Missing Ranex riskInfo")
            raw_score = risk_info.get("risk")
            if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float, Decimal)):
                raise ValueError("Invalid Ranex risk score type")
            try:
                risk_score = Decimal(str(raw_score))
            except InvalidOperation as exc:
                raise ValueError("Invalid Ranex risk score") from exc
            if not risk_score.is_finite() or risk_score < 0 or risk_score >= Decimal("1000000"):
                raise ValueError("Ranex risk score out of supported range")

            # Не сохраняем непроверенный полный ответ провайдера:
            # он может содержать лишние или чувствительные данные.
            # Не одобряем адрес без подтверждённой схемы Ranex.
            check.status = AMLCheck.Status.COMPLETED
            check.decision = AMLCheck.Decision.REVIEW
            check.risk_score = risk_score
            check.screened_at = timezone.now()
            check.save(update_fields=[
                "status",
                "decision",
                "risk_score",
                "screened_at",
                "updated_at",
            ])

            logger.info(
                "AML screening completed; manual review required. check_id=%s",
                check.id,
            )

            return Response(
                AMLCheckSerializer(check).data,
                status=status.HTTP_201_CREATED,
            )

        except (RanexError, ValueError):
            logger.exception(
                "Ranex AML screening failed. check_id=%s",
                check.id,
            )

            check.status = AMLCheck.Status.FAILED
            check.decision = AMLCheck.Decision.PENDING
            check.error_message = "Provider screening failed or returned invalid data"
            check.save(update_fields=[
                "status",
                "decision",
                "error_message",
                "updated_at",
            ])

            return Response(
                {
                    "id": str(check.id),
                    "status": "failed",
                    "decision": "pending",
                    "detail": "AML-провайдер временно недоступен или отклонил запрос.",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )


class AMLCheckListView(generics.ListAPIView):
    serializer_class = AMLCheckSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AMLCheck.objects.filter(
            user=self.request.user,
            kind=AMLCheck.Kind.ADDRESS,
        )


class AMLCheckDetailView(generics.RetrieveAPIView):
    serializer_class = AMLCheckSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return AMLCheck.objects.filter(
            user=self.request.user,
            kind=AMLCheck.Kind.ADDRESS,
        )
