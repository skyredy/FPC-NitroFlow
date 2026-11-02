import json
import re
from dataclasses import dataclass
from decimal import Decimal
from .money import money

@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    subscription: str
    length: int
    period: str
    categories: tuple
    max_unit_cost: Decimal
    min_unit_sale: Decimal
    min_profit: Decimal
    fee_percent: Decimal
    sellers: tuple
    provider_category: int
    expected_fields: dict
    verified: bool
    max_qty: int
    lot_ids: tuple
    instruction: str

def load_products(path):
    result = {}
    for item in json.loads(path.read_text(encoding="utf-8")):
        if not item.get("enabled", False):
            continue
        sku = item["sku"]
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,39}", sku) or sku in result:
            raise ValueError("InvalidSku")
        product = Product(sku, item["name"], item["subscription"], int(item["subscription_length"]),
                          item["subscription_period"], tuple(map(int, item["category_ids"])),
                          money(item["max_unit_cost_rub"]), money(item["min_sale_unit_rub"]),
                          money(item["min_profit_rub"]), Decimal(str(item["funpay_fee_percent"])),
                          tuple(map(int, item.get("seller_ids", []))), int(item.get("provider_category_id", 0)),
                          item.get("expected_fields", {}), item.get("profile_verified") is True, 1,
                          tuple(map(int, item.get("lot_ids", []))), item["instruction"])
        if product.subscription not in {"discord_nitro", "discord_nitro_basic", "discord_nitro_trial"}:
            raise ValueError("InvalidSubscription")
        if product.length <= 0 or product.period not in {"day", "month", "year"} or not product.categories:
            raise ValueError("InvalidDurationOrCategory")
        if not product.fee_percent.is_finite() or not 0 <= product.fee_percent < 100:
            raise ValueError("InvalidFee")
        if product.max_unit_cost <= 0 or product.min_unit_sale <= 0 or product.min_profit < 0:
            raise ValueError("InvalidPricing")
        if not isinstance(product.expected_fields, dict):
            raise ValueError("InvalidMetadata")
        if product.verified and (not product.sellers or any(i <= 0 for i in product.sellers) or
                                 product.provider_category <= 0 or not {"gifts_service", "gifts_type", "gifts_duration"} <= product.expected_fields.keys()):
            raise ValueError("VerifiedProfileIncomplete")
        result[sku] = product
    if not result:
        raise ValueError("NoProducts")
    return result
