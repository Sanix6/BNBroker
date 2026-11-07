from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import requests
from django.conf import settings

from .exceptions import (
    RanexComplianceConfigurationError,
    RanexComplianceConnectionError,
    RanexComplianceResponseError,
)


logger = logging.getLogger(__name__)


class RanexComplianceClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = (
            base_url or settings.RANEX_COMPLIANCE_BASE_URL
        ).rstrip("/") + "/"
        self.api_key = api_key or settings.RANEX_COMPLIANCE_API_KEY
        self.api_secret = api_secret or settings.RANEX_COMPLIANCE_API_SECRET
        self.timeout = (
            settings.RANEX_COMPLIANCE_CONNECT_TIMEOUT,
            settings.RANEX_COMPLIANCE_READ_TIMEOUT,
        )
        self.session = session or requests.Session()
        self._validate_configuration()

    def _validate_configuration(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise RanexComplianceConfigurationError(
                "RANEX_COMPLIANCE_BASE_URL должен быть абсолютным HTTPS URL."
            )
        if not self.api_key or not self.api_secret:
            raise RanexComplianceConfigurationError(
                "Не настроены ключи Ranex Compliance."
            )

    def get_status(self, external_user_id: str) -> dict[str, Any]:
        external_id = quote(external_user_id, safe="")
        return self.get(f"v1/applicants/{external_id}/status")

    def create_applicant(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("v1/applicants", data=payload)

    def get_applicant(self, external_user_id: str) -> dict[str, Any]:
        external_id = quote(external_user_id, safe="")
        return self.get(f"v1/applicants/{external_id}")

    def create_verification(
        self,
        external_user_id: str,
        *,
        level_name: str,
    ) -> dict[str, Any]:
        external_id = quote(external_user_id, safe="")
        return self._request(
            "POST",
            f"v1/applicants/{external_id}/verification-sessions",
            params={
                "verificationLevelName": level_name,
                "lang": "ru",
                "theme": "system",
                "returnUrl": settings.RANEX_COMPLIANCE_RETURN_URL,
            },
        )

    def get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def post(self, path: str, *, data: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, data=data)

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = self._build_url(path)
        logger.info("Ranex Compliance request method=%s path=%s", method, path)

        try:
            headers = {
                "X-Api-Key": self.api_key,
                "X-Api-Secret": self.api_secret,
                "Accept": "application/json",
                "Content-Type": "application/json",
            }

            response = self.session.request(
                method,
                url,
                json=data,
                params=params,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.Timeout as exc:
            raise RanexComplianceConnectionError(
                "Ranex Compliance не ответил вовремя.",
                retryable=True,
            ) from exc
        except requests.RequestException as exc:
            raise RanexComplianceConnectionError(
                "Не удалось подключиться к Ranex Compliance.",
                retryable=True,
            ) from exc

        request_id = (
            response.headers.get("X-Request-ID")
            or response.headers.get("X-Correlation-ID")
        )
        try:
            body = response.json() if response.content else {}
        except ValueError as exc:
            logger.warning(
                "Ranex Compliance invalid JSON path=%s status=%s request_id=%s",
                path,
                response.status_code,
                request_id,
            )
            raise RanexComplianceResponseError(
                "Ranex Compliance вернул некорректный ответ.",
                status_code=response.status_code,
                retryable=response.status_code >= 500,
            ) from exc

        if not 200 <= response.status_code < 300:
            message = self._extract_error_message(body)
            logger.warning(
                "Ranex Compliance error path=%s status=%s request_id=%s",
                path,
                response.status_code,
                request_id,
            )
            raise RanexComplianceResponseError(
                message,
                status_code=response.status_code,
                response_data=body,
                retryable=response.status_code == 429 or response.status_code >= 500,
            )

        if not isinstance(body, dict):
            raise RanexComplianceResponseError(
                "Ranex Compliance вернул неожиданный формат ответа.",
                status_code=response.status_code,
            )

        logger.info(
            "Ranex Compliance response path=%s status=%s request_id=%s",
            path,
            response.status_code,
            request_id,
        )
        return body

    def _build_url(self, path: str) -> str:
        url = urljoin(self.base_url, path.lstrip("/"))
        if urlparse(url).netloc != urlparse(self.base_url).netloc:
            raise RanexComplianceConfigurationError("Некорректный endpoint Ranex.")
        return url

    @staticmethod
    def _extract_error_message(body: Any) -> str:
        if isinstance(body, dict):
            for key in ("message", "detail", "error", "title"):
                value = body.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            errors = body.get("errors")
            if isinstance(errors, list) and errors:
                first = errors[0]
                if isinstance(first, dict) and first.get("message"):
                    return str(first["message"])
        return "Ranex Compliance отклонил запрос."
