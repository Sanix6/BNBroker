"""Run: python manage.py test apps.users.tests_password_change -v 2"""
from datetime import timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import (
    EmailVerificationCode,
    TwoFactorLoginChallenge,
    User,
    UserTwoFactor,
)
from .two_factor_login import issue_tokens


class PasswordChangeTests(APITestCase):
    def setUp(self):
        self.password = "CurrentPass!2026"
        self.new_password = "NewSecurePass!2026"
        self.user = User.objects.create_user(
            email="password-change-test@example.com",
            password=self.password,
            is_email_verified=True,
        )
        self.url = reverse("change-password")
        self.tokens = issue_tokens(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.tokens['access']}"
        )

    def payload(self, **changes):
        result = {
            "current_password": self.password,
            "new_password": self.new_password,
            "confirm_password": self.new_password,
        }
        result.update(changes)
        return result

    def test_requires_authentication(self):
        self.client.credentials()
        response = self.client.post(self.url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wrong_current_password(self):
        response = self.client.post(
            self.url, self.payload(current_password="wrong"), format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_confirm_password_mismatch(self):
        response = self.client.post(
            self.url, self.payload(confirm_password="DifferentPass!2026"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_reject_same_password(self):
        response = self.client.post(
            self.url,
            self.payload(new_password=self.password, confirm_password=self.password),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_django_password_strength_validation(self):
        response = self.client.post(
            self.url,
            self.payload(new_password="12345", confirm_password="12345"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data)

    def test_changes_password_and_revokes_old_access_and_refresh(self):
        response = self.client.post(self.url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("access", response.data)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertFalse(self.user.check_password(self.password))
        self.assertEqual(UserTwoFactor.objects.get(user=self.user).auth_version, 1)

        # Old access rejected by the project's custom JWT authentication.
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.tokens['access']}"
        )
        old_access = self.client.get(reverse("me"))
        self.assertEqual(old_access.status_code, status.HTTP_401_UNAUTHORIZED)

        # Old refresh rejected by the project's secure refresh serializer.
        self.client.credentials()
        old_refresh = self.client.post(
            reverse("token-refresh"),
            {"refresh": self.tokens["refresh"]},
            format="json",
        )
        self.assertEqual(old_refresh.status_code, status.HTTP_400_BAD_REQUEST)

        fresh_tokens = issue_tokens(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {fresh_tokens['access']}"
        )
        self.assertEqual(
            self.client.get(reverse("me")).status_code,
            status.HTTP_200_OK,
        )

    def test_preserves_2fa_and_invalidates_pending_challenges(self):
        security = UserTwoFactor.objects.create(user=self.user, enabled=True)
        token = issue_tokens(self.user, mfa_verified=True)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token['access']}")
        challenge = TwoFactorLoginChallenge.objects.create(
            user=self.user,
            token_hash="0" * 64,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        reset_code = EmailVerificationCode.objects.create(
            user=self.user,
            code_hash="reset:dummy",
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        response = self.client.post(self.url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        security.refresh_from_db()
        challenge.refresh_from_db()
        reset_code.refresh_from_db()
        self.assertTrue(security.enabled)
        self.assertEqual(security.auth_version, 1)
        self.assertIsNotNone(challenge.used_at)
        self.assertIsNotNone(reset_code.used_at)
