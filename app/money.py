from decimal import Decimal, InvalidOperation

def money(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("InvalidMoney") from None
    if not result.is_finite() or result < 0 or result > Decimal("1000000"):
        raise ValueError("InvalidMoney")
    return result.quantize(Decimal("0.01"))
