import sqlite3
import time
from .catalog import Catalog, metadata, quote
from .errors import ProviderError
from .gift import extract, fingerprint
from .money import money

class Purchaser:
    def __init__(self, store, provider, port, products, vault, reconcile_seconds=86400):
        self.store, self.provider, self.port = store, provider, port
        self.products, self.vault, self.reconcile_seconds = products, vault, reconcile_seconds

    def manual(self, row, code):
        self.store.change(row["id"], row["state"], "manual", error=code)
        self.store.alert(row["id"], code)
        self.store.enqueue(row["id"], "attention", "attention:" + row["id"])

    def postpone(self, row, code, state=None):
        attempts = row["attempts"] + 1
        if attempts >= 12 or (row["purchase_started"] and time.time() - row["purchase_started"] > self.reconcile_seconds):
            self.manual(row, code)
            return
        self.store.change(row["id"], row["state"], state or row["state"], attempts=attempts,
                          due=time.time() + min(300, 2 ** min(attempts, 8)), error=code)

    def receipt(self, row, data, profile):
        product = self.products[row["sku"]]
        item = data.get("item")
        if not isinstance(item, dict) or str(item.get("item_id")) != row["provider_id"]:
            raise ProviderError("RECEIPT_IDENTITY_MISMATCH")
        buyer = item.get("buyer")
        if not isinstance(buyer, dict) or buyer.get("visitorIsBuyer") is not True or buyer.get("user_id") != profile["user_id"]:
            raise ProviderError("OWNERSHIP_NOT_CONFIRMED")
        if item.get("canViewLoginData") is not True:
            raise ProviderError("GIFT_DATA_NOT_VISIBLE")
        cost = metadata(item, product)
        if cost > money(row["expected"]):
            raise ProviderError("PURCHASE_PRICE_MISMATCH")
        link = extract(item)
        payload = dict(items=[link], instruction=product.instruction, provider_item=item)
        sealed = self.vault.seal(payload, row["id"])
        now = time.time()
        with self.store.transaction() as db:
            current = db.execute("SELECT state FROM orders WHERE id=?", (row["id"],)).fetchone()
            if not current or current[0] not in ("purchasing", "processing", "retry_buy", "manual"):
                return
            digest = fingerprint(link)
            previous = db.execute("SELECT order_id FROM gift_fingerprints WHERE fingerprint=?", (digest,)).fetchone()
            if previous and previous[0] != row["id"]:
                raise ProviderError("GIFT_ALREADY_ASSIGNED")
            assigned = db.execute("SELECT fingerprint FROM gift_fingerprints WHERE order_id=?", (row["id"],)).fetchone()
            if assigned and assigned[0] != digest:
                raise ProviderError("GIFT_DATA_CHANGED")
            db.execute("INSERT OR IGNORE INTO gift_fingerprints VALUES(?,?)", (digest, row["id"]))
            db.execute("UPDATE orders SET state='ready',receipt=?,error=NULL,updated=? WHERE id=?", (sealed, now, row["id"]))
            db.execute("INSERT INTO events(order_id,state,at) VALUES(?,'ready',?)", (row["id"], now))

    def send_buy(self, row, product):
        try:
            data = self.provider.buy(int(row["provider_id"]), money(row["expected"]))
        except ProviderError as exc:
            current = self.store.get(row["id"])
            if exc.code == "RETRY_REQUEST":
                self.postpone(current, exc.code, "retry_buy")
            else:
                self.postpone(current, exc.code, "processing")
            return
        sealed = self.vault.seal(dict(buy_response=data), row["id"])
        self.store.change(row["id"], "purchasing", "processing", receipt=sealed, due=time.time() + 3)
        self.reconcile(self.store.get(row["id"]))

    def reconcile(self, row):
        profile = self.provider.profile()
        self.receipt(row, self.provider.item(int(row["provider_id"])), profile)

    def step(self, row):
        try:
            product = self.products[row["sku"]]
            if row["purchase_started"] and time.time() - row["purchase_started"] > self.reconcile_seconds:
                self.manual(row, "RECONCILIATION_DEADLINE")
                return
            if row["state"] == "accepted":
                if not self.port.eligible(row):
                    self.manual(row, "FUNPAY_ORDER_CHANGED")
                    return
                profile = self.provider.profile()
                excluded = {int(r["provider_id"]) for r in self.store.rows("SELECT provider_id FROM orders WHERE provider_id IS NOT NULL")}
                item, cost = Catalog(self.provider).select(product, row["sale"], excluded)
                if money(profile.get("balance")) < cost:
                    raise ProviderError("INSUFFICIENT_BALANCE")
                if not self.port.eligible(row):
                    self.manual(row, "FUNPAY_ORDER_CHANGED")
                    return
                try:
                    claimed = self.store.change(row["id"], "accepted", "purchasing", provider_id=str(item["item_id"]),
                                                expected=str(cost), purchase_started=time.time(), refundable=0)
                except sqlite3.IntegrityError:
                    self.postpone(self.store.get(row["id"]), "ITEM_ALREADY_ASSIGNED")
                    return
                if claimed:
                    self.send_buy(self.store.get(row["id"]), product)
            elif row["state"] == "retry_buy":
                if not self.port.eligible(row):
                    self.manual(row, "FUNPAY_ORDER_CHANGED")
                    return
                detail = self.provider.item(int(row["provider_id"]))
                buyer = detail["item"].get("buyer")
                if isinstance(buyer, dict) and buyer.get("visitorIsBuyer") is True:
                    self.receipt(row, detail, self.provider.profile())
                    return
                cost = quote(dict(detail["item"], canBuyItem=detail.get("canBuyItem")), product, row["sale"])
                if cost != money(row["expected"]):
                    raise ProviderError("PURCHASE_PRICE_MISMATCH")
                if self.store.change(row["id"], "retry_buy", "purchasing"):
                    self.send_buy(self.store.get(row["id"]), product)
            elif row["state"] in ("purchasing", "processing"):
                self.reconcile(row)
        except ProviderError as exc:
            current = self.store.get(row["id"])
            if current["state"] == "accepted" and exc.code in {"NO_MATCHING_STOCK", "INSUFFICIENT_BALANCE", "UNVERIFIED_PRODUCT_PROFILE"}:
                self.store.change(row["id"], "accepted", "declined", error=exc.code)
                self.store.alert(row["id"], exc.code)
                self.store.enqueue(row["id"], "attention", "attention:" + row["id"])
            elif exc.code in {"RECEIPT_IDENTITY_MISMATCH", "SUBSCRIPTION_METADATA_MISMATCH", "SELLER_NOT_ALLOWED",
                              "ITEM_IDENTITY_MISMATCH", "INVALID_GIFT_LINK", "AMBIGUOUS_GIFT_DATA", "GIFT_ALREADY_ASSIGNED",
                              "PURCHASE_PRICE_MISMATCH", "ORIGIN_NOT_ALLOWED", "RESALE_ORIGIN_UNVERIFIED", "GIFT_DATA_CHANGED"}:
                self.manual(current, exc.code)
            else:
                self.postpone(current, exc.code)
        except Exception as exc:
            self.postpone(self.store.get(row["id"]), type(exc).__name__)

    def tick(self):
        rows = self.store.rows("SELECT * FROM orders WHERE state IN ('accepted','purchasing','processing','retry_buy') AND due<=? ORDER BY created LIMIT 1", (time.time(),))
        for row in rows:
            self.step(row)
