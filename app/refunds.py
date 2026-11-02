class Refunder:
    def __init__(self, store, port):
        self.store, self.port = store, port

    def tick(self):
        for row in self.store.rows("SELECT * FROM orders WHERE state='refund_queued' LIMIT 1"):
            if not self.store.change(row["id"], "refund_queued", "refunding"):
                continue
            try:
                if not self.port.eligible(row):
                    raise RuntimeError("RefundOrderChanged")
                self.port.refund(row["id"])
            except Exception as exc:
                self.store.change(row["id"], "refunding", "refund_review", error=type(exc).__name__)
                self.store.alert(row["id"], "REFUND_REQUIRES_REVIEW")
            else:
                self.store.change(row["id"], "refunding", "refunded")
                self.store.enqueue(row["id"], "refund_done", "refund_done:"+row["id"])
