import json
from datetime import datetime, timezone

STATUSES = frozenset(("neutral", "good", "suspicious", "restricted"))

def read_labels(connection, buyer):
    row = connection.execute(
        "SELECT status,reason,updated_at FROM buyer_labels WHERE buyer=?", (buyer,)).fetchone()
    history = [{"status": status, "reason": reason, "at": at, "source": "owner"}
               for status, reason, at in connection.execute(
                   "SELECT status,reason,at FROM buyer_label_events WHERE buyer=? ORDER BY sequence", (buyer,))]
    return {
        "status": row[0] if row else "neutral",
        "reason": row[1] if row else None,
        "updated_at": row[2] if row else None,
        "needs_owner_review": bool(row and row[0] in ("suspicious", "restricted")),
        "automatic_refund": False,
        "source": "owner" if row else "default",
        "history": history,
    }

class BuyerLabels:
    def __init__(self, store):
        self.store = store
        self.store.db.execute("CREATE TABLE IF NOT EXISTS buyer_labels (buyer INTEGER PRIMARY KEY,status TEXT NOT NULL,reason TEXT NOT NULL,updated_at TEXT NOT NULL)")
        self.store.db.execute("CREATE TABLE IF NOT EXISTS buyer_label_events (sequence INTEGER PRIMARY KEY AUTOINCREMENT,buyer INTEGER NOT NULL,status TEXT NOT NULL,reason TEXT NOT NULL,at TEXT NOT NULL)")
        self.store.db.commit()

    def get(self, buyer):
        with self.store.lock:
            return read_labels(self.store.db, buyer)

    def set(self, buyer, status, reason):
        if not isinstance(buyer, int) or buyer <= 0:
            raise ValueError("Invalid FunPay user ID")
        if status not in STATUSES or not reason.strip() or len(reason) > 2000:
            raise ValueError("Valid status and a reason up to 2000 characters are required")
        at = datetime.now(timezone.utc).isoformat()
        with self.store.lock:
            with self.store.db:
                self.store.db.execute(
                    "INSERT INTO buyer_labels VALUES (?,?,?,?) ON CONFLICT(buyer) DO UPDATE SET status=excluded.status,reason=excluded.reason,updated_at=excluded.updated_at",
                    (buyer, status, reason.strip(), at))
                self.store.db.execute("INSERT INTO buyer_label_events(buyer,status,reason,at) VALUES (?,?,?,?)",
                                      (buyer, status, reason.strip(), at))
            self.store.sync_buyer(buyer)
            return read_labels(self.store.db, buyer)
