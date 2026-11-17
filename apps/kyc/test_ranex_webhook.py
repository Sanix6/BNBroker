import base64
import hashlib
import hmac
import time
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from .webhook import SignatureError, verify_signature


class RanexWebhookSignatureTests(SimpleTestCase):
    @override_settings(RUNEX_KYC_WEBHOOK_SECRET=base64.b64encode(b"a" * 32).decode())
    def test_valid_and_tampered(self):
        body = b'{"type":"applicantPending"}'
        stamp = str(int(time.time() * 1000))
        digest = hmac.new(b"a" * 32, stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        header = f"t={stamp},v1={digest}"
        verify_signature(body, header)
        with self.assertRaises(SignatureError):
            verify_signature(body + b" ", header)

    @override_settings(RUNEX_KYC_WEBHOOK_SECRET=base64.b64encode(b"a" * 32).decode())
    def test_expired(self):
        stamp = str(int(time.time() * 1000) - 600_000)
        digest = hmac.new(b"a" * 32, stamp.encode() + b"." + b"{}", hashlib.sha256).hexdigest()
        with self.assertRaises(SignatureError):
            verify_signature(b"{}", f"t={stamp},v1={digest}")
