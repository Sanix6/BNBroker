from __future__ import annotations

from typing import Any


class RanexComplianceError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_data: Any = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data
        self.retryable = retryable


class RanexComplianceConfigurationError(RanexComplianceError):
    pass


class RanexComplianceConnectionError(RanexComplianceError):
    pass


class RanexComplianceResponseError(RanexComplianceError):
    pass


class RanexComplianceSignatureError(RanexComplianceError):
    pass
