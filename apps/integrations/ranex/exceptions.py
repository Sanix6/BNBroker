class RanexError(Exception):
    """
    Base exception for Ranex integration.
    """


class RanexConfigurationError(RanexError):
    """
    Ranex credentials/configuration are missing or invalid.
    """


class RanexValidationError(RanexError):
    """
    Invalid request parameters before sending request to Ranex.
    """


class RanexAuthenticationError(RanexError):
    """
    API key is invalid or unauthorized.
    """


class RanexPaymentRequiredError(RanexError):
    """
    Ranex subscription/payment limit issue.
    """


class RanexNotFoundError(RanexError):
    """
    Requested Ranex resource was not found.
    """


class RanexRateLimitError(RanexError):
    """
    Ranex request rate limit exceeded.
    """


class RanexTimeoutError(RanexError):
    """
    Ranex did not respond within configured timeout.
    """


class RanexRequestError(RanexError):
    """
    Generic HTTP/network error.
    """


class RanexInvalidResponseError(RanexError):
    """
    Ranex returned an invalid or unexpected response.
    """
