from copy import copy
from types import SimpleNamespace
from .filter import identify

class FunPayPort:
    def __init__(self, account, products):
        self.account, self.products = account, products

    def eligible(self, row, paid_only=True):
        order = self.account.get_order(row["id"])
        if order.status.name == "CLOSED" and not paid_only and row["purchase_started"]:
            order = copy(order)
            order.status = SimpleNamespace(name="PAID")
        sale = identify(self.account, order, self.products)
        return bool(sale and all(sale[k] == row[k] for k in ("id", "seller", "buyer", "chat", "sku", "qty")) and str(sale["sale"]) == row["sale"])

    def send(self, chat, text):
        result = self.account.send_message(chat, text)
        if not result:
            raise RuntimeError("MessageResultUnknown")

    def refund(self, oid):
        self.account.refund(oid)

    def awaiting_confirmation(self, row):
        order = self.account.get_order(row["id"])
        return order.seller_id == row["seller"] and order.buyer_id == row["buyer"] and order.status.name == "PAID" and "арбитраж" not in (order.html or "").casefold()
