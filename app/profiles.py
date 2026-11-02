import json
import os
import tempfile
from .labels import read_labels

class Profiles:
    def __init__(self, store, directory):
        self.store, self.directory = store, directory
        directory.mkdir(parents=True, exist_ok=True)

    def write(self, buyer):
        with self.store.lock:
            orders = self.store.rows("SELECT id,sku,qty,sale,username,state,created,updated,provider_id,delivery_started,error,delivered_at FROM orders WHERE buyer=? ORDER BY created,id", (buyer,))
            for order in orders:
                order["history"] = self.store.rows("SELECT state,at,error FROM events WHERE order_id=? ORDER BY sequence", (order["id"],))
            profile = dict(schema_version=1, funpay_user_id=buyer, customer_label=read_labels(self.store.db, buyer),
                           purchase_count=len(orders), delivered_count=sum(o["state"] == "delivered" for o in orders),
                           refund_count=sum(o["state"] == "refunded" for o in orders), orders=orders)
            descriptor, temporary = tempfile.mkstemp(prefix=".buyer-", dir=self.directory)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                    json.dump(profile, output, ensure_ascii=False, indent=2)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, self.directory / f"{int(buyer)}.json")
                if os.name != "nt":
                    descriptor = os.open(self.directory, os.O_RDONLY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            return profile

    def rebuild(self):
        for row in self.store.rows("SELECT buyer FROM orders UNION SELECT buyer FROM buyer_labels"):
            self.write(row["buyer"])
