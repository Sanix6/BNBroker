"""Ranex Compliance webhook, adapted from WTP signature verification.

Provider contract: X-Webhook-Signature: t=<unix-ms>,v1=<hex-hmac>;
HMAC-SHA256(base64-decoded 32-byte secret, timestamp + b'.' + raw body).
"""
import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import KYCVerification

logger = logging.getLogger(__name__)
EVENTS = {
    "applicantReviewed", "applicantAwaitingOperatorReview", "applicantOnHold",
    "applicantWorkflowFailed", "applicantExpired", "applicantPending",
}


class SignatureError(ValueError):
    pass


class WebhookConfigurationError(RuntimeError):
    pass


def verify_signature(body: bytes, header: str) -> None:
    secret = settings.RUNEX_KYC_WEBHOOK_SECRET
    if not secret:
        raise WebhookConfigurationError("Missing Ranex webhook secret")
    try:
        parts = dict(part.strip().split("=", 1) for part in header.split(",") if "=" in part)
        stamp, digest = parts["t"], parts["v1"]
        if not stamp.isascii() or not stamp.isdigit():
            raise ValueError("Invalid timestamp")
        if len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
            raise ValueError("Invalid digest")
        if abs(int(time.time() * 1000) - int(stamp)) > 300_000:
            raise ValueError("Expired timestamp")
        key = base64.b64decode(secret, validate=True)
        if len(key) != 32:
            raise ValueError("Invalid key length")
    except (KeyError, ValueError, TypeError) as exc:
        raise SignatureError("Invalid signature") from exc
    expected = hmac.new(key, stamp.encode("ascii") + b"." + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, digest.lower()):
        raise SignatureError("Invalid signature")


def event_datetime(payload):
    ms = payload.get("createdAtMs")
    if isinstance(ms, bool):
        raise ValueError("Invalid event time")
    if isinstance(ms, (int, float)):
        try:
            return datetime.fromtimestamp(ms / 1000, tz=dt_timezone.utc)
        except (ValueError, OverflowError, OSError) as exc:
            raise ValueError("Invalid event time") from exc
    value = payload.get("createdAt")
    parsed = parse_datetime(value) if isinstance(value, str) else None
    if parsed is None or timezone.is_naive(parsed):
        raise ValueError("Missing or invalid event time")
    return parsed


def process_event(payload: dict, digest: str) -> dict:
    kind = payload.get("type")
    if kind not in EVENTS:
        return {"ok": True, "ignored": True}
    external_user_id = payload.get("externalUserId")
    applicant_id = payload.get("applicantId")
    if not isinstance(external_user_id, str) or not external_user_id or not isinstance(applicant_id, str) or not applicant_id:
        raise ValueError("Missing applicant identifiers")
    sandbox = payload.get("sandboxMode")
    if not isinstance(sandbox, bool):
        raise ValueError("Missing sandboxMode")
    if sandbox != str(settings.RUNEX_KYC_API_KEY).startswith("pk_test_"):
        return {"ok": True, "ignored": True}
    occurred = event_datetime(payload)
    review = payload.get("reviewResult") or {}
    if not isinstance(review, dict):
        raise ValueError("Invalid reviewResult")
    answer = review.get("reviewAnswer")
    if kind == "applicantReviewed" and answer not in ("GREEN", "RED"):
        raise ValueError("Invalid reviewAnswer")

    # Ranex test events may use non-UUID externalUserId values.
    # Never query a UUIDField with an invalid identifier.
    from django.contrib.auth import get_user_model
    from django.core.exceptions import ValidationError

    try:
        external_user_id = get_user_model()._meta.pk.to_python(external_user_id)
    except (ValidationError, ValueError, TypeError):
        logger.info("Ranex webhook ignored: invalid external user ID")
        return {"ok": True, "ignored": True, "reason": "unknown_user"}

    with transaction.atomic():
        # Match the exact applicant AND the external user; never approve by user ID alone.
        records = list(KYCVerification.objects.select_for_update().filter(
            user_id=external_user_id, external_applicant_id=applicant_id,
            provider="ranex",
        ).order_by("-created_at")[:2])
        if not records:
            # The applicant may have been created before the local start was committed.
            # Retry only if a local start is in progress; otherwise ignore foreign applicants.
            if KYCVerification.objects.filter(user_id=external_user_id, status="not_started").exists():
                raise RuntimeError("Verification start in progress")
            return {"ok": True, "ignored": True}
        record = records[0]
        level = payload.get("levelName")
        if level is not None and (not isinstance(level, str) or level.casefold() != record.level_name.casefold()):
            return {"ok": True, "ignored": True}
        previous = record.provider_payload if isinstance(record.provider_payload, dict) else {}
        if previous.get("webhook_sha256") == digest:
            return {"ok": True, "duplicate": True}
        previous_date = parse_datetime(previous.get("event_at", "")) if isinstance(previous.get("event_at"), str) else None
        if previous_date and occurred <= previous_date:
            return {"ok": True, "ignored": True, "reason": "old_event"}
        if occurred < record.created_at:
            return {"ok": True, "ignored": True, "reason": "before_start"}
        # A terminal decision is immutable through webhook; subsequent changes require manual review.
        if record.status in (KYCVerification.Status.APPROVED, KYCVerification.Status.REJECTED):
            return {"ok": True, "ignored": True, "reason": "terminal"}
        if kind == "applicantReviewed":
            record.status = KYCVerification.Status.APPROVED if answer == "GREEN" else KYCVerification.Status.REJECTED
            record.verified_at = timezone.now() if answer == "GREEN" else None
        elif kind == "applicantExpired":
            record.status = KYCVerification.Status.EXPIRED
        elif kind == "applicantWorkflowFailed":
            record.status = KYCVerification.Status.ERROR
        else:
            record.status = KYCVerification.Status.PENDING
        # Deliberately do not store document data, raw body or personal information.
        record.provider_payload = {"event_type": kind, "event_at": occurred.isoformat(),
                                   "webhook_sha256": digest, "review_answer": answer if kind == "applicantReviewed" else None}
        record.save(update_fields=["status", "verified_at", "provider_payload", "updated_at"])
    return {"ok": True, "status": record.status}


class RanexWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = []

    def post(self, request):
        body = request.body
        if len(body) > 262_144:
            return Response({"detail": "Payload too large"}, status=413)
        try:
            verify_signature(body, request.headers.get("X-Webhook-Signature", ""))
        except SignatureError:
            return Response({"detail": "Invalid signature"}, status=401)
        except WebhookConfigurationError:
            return Response({"detail": "Webhook unavailable"}, status=503)
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("Invalid payload")
            result = process_event(payload, hashlib.sha256(body).hexdigest())
            return Response(result)
        except (ValueError, UnicodeDecodeError):
            return Response({"detail": "Invalid payload"}, status=400)
        except Exception as exc:
            logger.error("Ranex webhook processing failed: %s", type(exc).__name__)
            return Response({"detail": "Temporary processing error"}, status=503)
