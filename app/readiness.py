from .market import Market
from .catalog import Catalog
from .money import money

def check(settings):
    result = dict(mode="read_only", funpay_key_present=bool(settings.token), lzt_token_present=bool(settings.api_key),
                  purchases_enabled=settings.live, products=[])
    if not settings.api_key:
        result["status"] = "awaiting_lzt_token"
        return result
    if not all(p.verified for p in settings.products.values()):
        result["status"] = "awaiting_verified_supplier_profiles"
        return result
    provider = Market(settings.api_key)
    profile = provider.profile()
    for product in settings.products.values():
        item, cost = Catalog(provider).select(product, product.min_unit_sale)
        result["products"].append(dict(sku=product.sku, candidate_item_id=item["item_id"], unit_cost=str(cost),
                                       balance_sufficient=money(profile["balance"]) >= cost))
    result["status"] = "read_only_checks_passed" if all(p["balance_sufficient"] for p in result["products"]) else "insufficient_provider_balance"
    return result
