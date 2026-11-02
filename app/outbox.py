import time
from .texts import message, completed, reminder

class Outbox:
    def __init__(self, store, port, products, vault):
        self.store, self.port, self.products, self.vault = store, port, products, vault

    def render(self, job, row):
        kind = job["kind"]
        if kind in ("credentials", "repeat"):
            receipt = self.vault.open(row["receipt"], row["id"])
            sections = [f"Заказ #{row['id']}\n{self.products[row['sku']].name}"]
            sections.extend(f"{i}. {value}" for i, value in enumerate(receipt["items"], 1))
            instructions = receipt.get("instruction") or self.products[row["sku"]].instruction
            if instructions:
                sections.append(instructions)
            sections.append("Для помощи напишите !поддержка. Данные доступа не передавайте другим людям.")
            text = message("\n\n".join(sections))
            if len(text) > 12000:
                raise ValueError("DeliveryMessageTooLong")
            return text
        if kind == "completion":
            return completed(row)
        if kind == "reminder":
            return reminder(row)
        if kind == "attention":
            return message(f"Заказ #{row['id']} требует проверки продавца. Повторная закупка остановлена. "
                           "Напишите !поддержка. Если возврат доступен до выдачи — !возврат.")
        if kind == "refund_done":
            return message(f"Возврат по заказу #{row['id']} выполнен. Товар по нему выдаваться не будет.")
        return job["body"]

    def tick(self):
        for job in self.store.rows("SELECT * FROM outbox WHERE state='pending' AND due<=? ORDER BY id LIMIT 10", (time.time(),)):
            row = self.store.get(job["order_id"])
            if row is None:
                continue
            try:
                if job["kind"] in ("credentials", "repeat"):
                    if row["state"] not in ("ready", "delivered") or not self.port.eligible(row, paid_only=False):
                        self.store.alert(row["id"], "DELIVERY_ORDER_REQUIRES_REVIEW")
                        with self.store.transaction() as db:
                            db.execute("UPDATE outbox SET due=? WHERE id=?",(time.time()+60,job["id"]))
                        continue
                if job["kind"] == "reminder" and not self.port.awaiting_confirmation(row):
                    with self.store.transaction() as db:
                        db.execute("UPDATE outbox SET state='cancelled' WHERE id=? AND state='pending'", (job["id"],))
                    continue
                text = self.render(job, row)
            except Exception as exc:
                self.store.alert(row["id"], type(exc).__name__)
                with self.store.transaction() as db:
                    db.execute("UPDATE outbox SET due=? WHERE id=?",(time.time()+60,job["id"]))
                continue
            with self.store.transaction() as db:
                changed = db.execute("UPDATE outbox SET state='sending' WHERE id=? AND state='pending'", (job["id"],)).rowcount
                if changed and job["kind"] in ("credentials", "repeat"):
                    db.execute("UPDATE orders SET delivery_started=1,refundable=0 WHERE id=?", (row["id"],))
            if not changed:
                continue
            try:
                self.port.send(row["chat"], text)
            except Exception as exc:
                with self.store.transaction() as db:
                    db.execute("UPDATE outbox SET state='uncertain',error=? WHERE id=?", (type(exc).__name__, job["id"]))
                self.store.alert(row["id"], "MESSAGE_RESULT_UNKNOWN")
                continue
            now = time.time()
            with self.store.transaction() as db:
                db.execute("UPDATE outbox SET state='sent',sent_at=? WHERE id=?", (now, job["id"]))
                if job["kind"] in ("credentials", "repeat") and row["state"] == "ready":
                    db.execute("UPDATE orders SET state='delivered',delivered_at=?,updated=? WHERE id=? AND state='ready'", (now, now, row["id"]))
                    db.execute("INSERT INTO events(order_id,state,at) VALUES(?,'delivered',?)", (row["id"], now))
