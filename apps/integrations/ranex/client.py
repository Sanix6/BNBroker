import json
import logging
from urllib.parse import quote

import requests
from django.conf import settings

from apps.integrations.ranex.constants import (
    RanexEndpoints,
    RanexNetwork,
)
from apps.integrations.ranex.exceptions import (
    RanexAuthenticationError,
    RanexConfigurationError,
    RanexInvalidResponseError,
    RanexNotFoundError,
    RanexPaymentRequiredError,
    RanexRateLimitError,
    RanexRequestError,
    RanexTimeoutError,
    RanexValidationError,
)


logger = logging.getLogger(__name__)


class RanexClient:
    def __init__(self):
        self.api_key = getattr(
            settings,
            "RUNEX_API_KEY",
            "",
        ).strip()

        self.base_url = getattr(
            settings,
            "RUNEX_BASE_URL",
            "https://kyt-api.ranex.kg",
        ).rstrip("/")

        self.timeout = getattr(
            settings,
            "RUNEX_TIMEOUT",
            30,
        )

        if not self.api_key:
            raise RanexConfigurationError(
                "RUNEX_API_KEY is not configured."
            )

        if not self.base_url:
            raise RanexConfigurationError(
                "RUNEX_BASE_URL is not configured."
            )

    def _headers(self):
        return {
            "Accept": "application/json",
            "X-API-Key": self.api_key,
        }

    def _request(
        self,
        *,
        method,
        endpoint,
        params=None,
        expect_json=True,
    ):
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._headers(),
                params=params or None,
                timeout=self.timeout,
            )

        except requests.Timeout as exc:
            logger.exception(
                "Ranex request timed out. method=%s endpoint=%s",
                method,
                endpoint,
            )

            raise RanexTimeoutError(
                "Ranex request timed out."
            ) from exc

        except requests.RequestException as exc:
            logger.exception(
                "Ranex network request failed. "
                "method=%s endpoint=%s",
                method,
                endpoint,
            )

            raise RanexRequestError(
                f"Ranex request failed: {exc}"
            ) from exc

        if response.status_code == 401:
            raise RanexAuthenticationError(
                "Ranex authentication failed."
            )

        if response.status_code == 402:
            raise RanexPaymentRequiredError(
                "Ranex payment/subscription limit reached."
            )

        if response.status_code == 404:
            raise RanexNotFoundError(
                "Ranex resource not found."
            )

        if response.status_code == 429:
            raise RanexRateLimitError(
                "Ranex rate limit exceeded."
            )

        if response.status_code >= 400:
            body = response.text[:2000]

            logger.error(
                "Ranex HTTP error. "
                "status=%s endpoint=%s body=%s",
                response.status_code,
                endpoint,
                body,
            )

            raise RanexRequestError(
                f"Ranex HTTP {response.status_code}: "
                f"{body}"
            )

        if not expect_json:
            return response.content

        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise RanexInvalidResponseError(
                "Ranex returned invalid JSON."
            ) from exc

        if not isinstance(data, dict):
            raise RanexInvalidResponseError(
                "Ranex returned unexpected response format."
            )

        return data

    def get_usage(self):
        return self._request(
            method="GET",
            endpoint=RanexEndpoints.USAGE,
        )

    def get_risk_categories(self):
        return self._request(
            method="GET",
            endpoint=RanexEndpoints.RISK_CATEGORIES,
        )

    def get_check_history(
        self,
        *,
        from_date=None,
        to_date=None,
        page=1,
        limit=50,
    ):
        params = {
            "page": page,
            "limit": limit,
        }

        if from_date:
            params["fromDate"] = from_date

        if to_date:
            params["toDate"] = to_date

        return self._request(
            method="GET",
            endpoint=RanexEndpoints.CHECK_HISTORY,
            params=params,
        )

    def screen_address(
        self,
        *,
        network,
        address,
    ):
        network = (
            network
            or ""
        ).strip().lower()

        address = (
            address
            or ""
        ).strip()

        if network not in RanexNetwork.SUPPORTED:
            raise RanexValidationError(
                f"Unsupported Ranex network: {network}"
            )

        if not address:
            raise RanexValidationError(
                "Crypto address is required."
            )

        endpoint = RanexEndpoints.SCREEN_ADDRESS.format(
            network=quote(
                network,
                safe="",
            ),
            address=quote(
                address,
                safe="",
            ),
        )

        return self._request(
            method="GET",
            endpoint=endpoint,
        )

    def download_pdf_report(
        self,
        *,
        screening_id,
    ):
        if not screening_id:
            raise RanexValidationError(
                "screening_id is required."
            )

        endpoint = RanexEndpoints.PDF_REPORT.format(
            screening_id=screening_id,
        )

        return self._request(
            method="GET",
            endpoint=endpoint,
            expect_json=False,
        )
