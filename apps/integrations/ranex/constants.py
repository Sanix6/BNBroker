class RanexNetwork:
    BITCOIN = "bitcoin"
    ETHEREUM = "ethereum"
    TRON = "tron"

    SUPPORTED = {
        BITCOIN,
        ETHEREUM,
        TRON,
    }


class RanexEndpoints:
    USAGE = "/api/v1/crypto-screening/usage"

    CHECK_HISTORY = (
        "/api/v1/crypto-screening/check-history"
    )

    RISK_CATEGORIES = (
        "/api/v1/crypto-screening/risk-categories"
    )

    SCREEN_ADDRESS = (
        "/api/v1/crypto-screening/{network}/{address}"
    )

    PDF_REPORT = (
        "/api/v1/reports/checks/{screening_id}/pdf"
    )
