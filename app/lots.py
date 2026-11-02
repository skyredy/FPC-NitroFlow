import re
from .catalog import Catalog
from .money import money

class Lots:
    def __init__(self, store, account, provider, products, auto_resume=False):
        self.store, self.account, self.provider, self.products = store, account, provider, products
        self.auto_resume=auto_resume

    def tick(self):
        for product in self.products.values():
            if not product.lot_ids:
                continue
            reason = None
            try:
                excluded = {int(r["provider_id"]) for r in self.store.rows("SELECT provider_id FROM orders WHERE provider_id IS NOT NULL")}
                _, cost = Catalog(self.provider).select(product, product.min_unit_sale, excluded)
                balance = self.provider.profile()
                if money(balance["balance"]) < cost:
                    reason = "INSUFFICIENT_BALANCE"
            except Exception:
                reason = "PROVIDER_NOT_READY"
            for lot in product.lot_ids:
                fields = self.account.get_lot_fields(lot)
                descriptions = "\n".join(str(v) for k,v in fields.fields.items() if "desc" in k)
                markers = re.findall(r"(?m)^\s*!nitro[ \t]+([a-z][a-z0-9-]{1,39})[ \t]*$", descriptions)
                if not markers or any(sku != product.sku for sku in markers):
                    self.store.alert(None,"LOT_MARKER_MISMATCH")
                    continue
                paused = self.store.rows("SELECT * FROM lot_pauses WHERE lot=?",(lot,))
                if reason and fields.active:
                    fields.active = False
                    self.account.save_lot(fields)
                    if not self.account.get_lot_fields(lot).active:
                        with self.store.transaction() as db:
                            db.execute("INSERT OR IGNORE INTO lot_pauses VALUES(?,?,?)",(lot,product.sku,reason))
                elif not reason and paused and not fields.active:
                    if not self.auto_resume:
                        self.store.alert(None,"LOT_READY_FOR_MANUAL_RESUME")
                        continue
                    fields.active = True
                    self.account.save_lot(fields)
                    with self.store.transaction() as db:
                        db.execute("DELETE FROM lot_pauses WHERE lot=?",(lot,))
