import re
from bs4 import BeautifulSoup
from .money import money

def identify(account, order, products):
    if order.seller_id != account.id or order.status.name != "PAID":
        return None
    matches = re.findall(r"(?m)^\s*!nitro[ \t]+([a-z][a-z0-9-]{1,39})[ \t]*$", order.full_description or "")
    if len(matches) != 1 or matches[0] not in products:
        return None
    product = products[matches[0]]
    currency = getattr(order, "currency", None)
    if currency is not None and getattr(currency, "name", currency) != "RUB":
        return None
    if not order.subcategory or order.subcategory.id not in product.categories:
        return None
    page = BeautifulSoup(order.html, "html.parser")
    if page.select_one(".text-danger") or "арбитраж" in page.get_text().casefold():
        return None
    quantity = getattr(order, "amount", None)
    for node in page.select(".param-item"):
        heading, value = node.find("h5"), node.find("div")
        if heading and value and heading.get_text(strip=True)=="Сумма" and any(c in value.get_text() for c in ("$","€")):
            return None
        if heading and value and "Количество" in heading.get_text():
            match = re.fullmatch(r"([1-9][0-9]*)\s*(?:шт\.?)?", value.get_text(strip=True))
            if not match:
                return None
            parsed = int(match[1])
            if quantity is not None and int(quantity) != parsed:
                return None
            quantity = parsed
    qty = int(quantity) if quantity is not None else 1
    if not 1 <= qty <= product.max_qty:
        return None
    sale = money(order.sum)
    if sale < product.min_unit_sale * qty:
        return None
    chat = account.get_chat_by_name(order.buyer_username, True)
    if not chat or int(order.buyer_id) <= 0:
        return None
    return dict(id=order.id, seller=account.id, buyer=order.buyer_id, chat=chat.id,
                sku=product.sku, qty=qty, sale=sale, username=order.buyer_username)
