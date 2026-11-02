from decimal import Decimal
from .errors import ProviderError
from .money import money

def metadata(item, product):
    if not product.verified or not product.sellers or product.provider_category <= 0:
        raise ProviderError("UNVERIFIED_PRODUCT_PROFILE")
    if type(item.get("item_id")) is not int or item["item_id"] <= 0 or item.get("category_id") != product.provider_category:
        raise ProviderError("ITEM_IDENTITY_MISMATCH")
    seller = item.get("seller")
    if not isinstance(seller, dict) or seller.get("user_id") not in product.sellers or seller.get("is_banned") not in (0, False):
        raise ProviderError("SELLER_NOT_ALLOWED")
    if item.get("item_origin") not in {"personal", "autoreg", "resale"}:
        raise ProviderError("ORIGIN_NOT_ALLOWED")
    if item.get("item_origin") == "resale" and item.get("resale_item_origin") not in {"personal", "autoreg"}:
        raise ProviderError("RESALE_ORIGIN_UNVERIFIED")
    for field, expected in product.expected_fields.items():
        value = item.get(field)
        if type(value) is not type(expected) or value != expected:
            raise ProviderError("SUBSCRIPTION_METADATA_MISMATCH")
    if str(item.get("price_currency", "")).lower() != "rub":
        raise ProviderError("RUB_PRICE_REQUIRED")
    cost = money(item.get("price"))
    if cost <= 0 or cost > product.max_unit_cost:
        raise ProviderError("PRICE_LIMIT")
    return cost

def quote(item, product, sale):
    cost = metadata(item, product)
    if item.get("item_state") != "active" or item.get("canBuyItem") is not True:
        raise ProviderError("ITEM_NOT_AVAILABLE")
    proceeds = money(sale) * (Decimal(1) - product.fee_percent / 100)
    if proceeds - cost < product.min_profit:
        raise ProviderError("PROFIT_LIMIT")
    return cost

class Catalog:
    def __init__(self, provider):
        self.provider = provider

    def select(self, product, sale, excluded=()):
        if not product.verified:
            raise ProviderError("UNVERIFIED_PRODUCT_PROFILE")
        found = []
        for seller in product.sellers:
            after = None
            for _ in range(3):
                page = self.provider.search(product, seller, after)
                for item in page["items"]:
                    if item.get("item_id") in excluded:
                        continue
                    try:
                        found.append((quote(item, product, sale), item["item_id"]))
                    except (ProviderError, ValueError, TypeError):
                        continue
                if not page.get("hasNextPage") or not page.get("nextCursor"):
                    break
                after = page["nextCursor"]
        for _, item_id in sorted(set(found)):
            detail = self.provider.item(item_id)
            item = dict(detail["item"], canBuyItem=detail.get("canBuyItem"))
            try:
                price = quote(item, product, sale)
            except (ProviderError, ValueError, TypeError):
                continue
            return item, price
        raise ProviderError("NO_MATCHING_STOCK")
