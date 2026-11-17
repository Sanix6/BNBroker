"""Pure Decimal arithmetic for manually-priced RUB <-> crypto quotes.

Each manual rate means RUB per 1 crypto unit regardless of direction.
No floats or automatic exchange-rate providers are involved.
"""
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP, localcontext


class QuoteAmountError(ValueError):
    pass


def _exact_scale(value, places, name):
    unit = Decimal(1).scaleb(-places)
    try:
        exact = value.quantize(unit)
    except InvalidOperation as exc:
        raise QuoteAmountError(f'{name}: сумма слишком велика') from exc
    if exact != value:
        raise QuoteAmountError(f'{name}: допускается не более {places} знаков после запятой')
    return exact


def calculate_amounts(*, from_kind, to_kind, rate, amount, amount_side='from', crypto_decimals=12):
    """Return (fiat_amount, crypto_amount), both exact Decimal snapshots.

    For client-protective rounding of RECEIVED amounts, always round down.
    For requested received amounts, round the REQUIRED sent amount up.
    """
    if (from_kind, to_kind) not in {('fiat', 'crypto'), ('crypto', 'fiat')}:
        raise QuoteAmountError('Поддерживаются только обмены RUB ↔ криптовалюта')
    if amount_side not in {'from', 'to'}:
        raise QuoteAmountError('amount_side должен быть from или to')
    try:
        amount = Decimal(str(amount))
        rate = Decimal(str(rate))
    except (InvalidOperation, ValueError) as exc:
        raise QuoteAmountError('Некорректная сумма или курс') from exc
    if not amount.is_finite() or not rate.is_finite() or amount <= 0 or rate <= 0:
        raise QuoteAmountError('Сумма и курс должны быть положительными')

    places = max(0, min(12, int(crypto_decimals)))
    fiat_unit = Decimal('0.01')
    crypto_unit = Decimal(1).scaleb(-places)

    with localcontext() as ctx:
        ctx.prec = 64
        if from_kind == 'fiat':
            if amount_side == 'from':
                fiat = _exact_scale(amount, 2, 'RUB')
                crypto = (fiat / rate).quantize(crypto_unit, rounding=ROUND_DOWN)
            else:
                crypto = _exact_scale(amount, places, 'Криптовалюта')
                fiat = (crypto * rate).quantize(fiat_unit, rounding=ROUND_UP)
        else:
            if amount_side == 'from':
                crypto = _exact_scale(amount, places, 'Криптовалюта')
                fiat = (crypto * rate).quantize(fiat_unit, rounding=ROUND_DOWN)
            else:
                fiat = _exact_scale(amount, 2, 'RUB')
                crypto = (fiat / rate).quantize(crypto_unit, rounding=ROUND_UP)

        if fiat < fiat_unit or crypto < crypto_unit:
            raise QuoteAmountError('Сумма слишком мала для выбранного курса')
        # ExchangeQuote fiat_amount: 24 digits, 2 decimal places;
        # crypto_amount: 30 digits, 12 decimal places.
        if fiat >= Decimal('1e22') or crypto >= Decimal('1e18'):
            raise QuoteAmountError('Сумма превышает допустимый максимум')
        return fiat, crypto
