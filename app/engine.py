import json
import re
import time
from .texts import message, status
from .labels import BuyerLabels
from .commands import help, status as status_command, orders, refund, support, author, data, instruction

class Engine:
    def __init__(self, store, products):
        self.store, self.products = store, products
        self.labels = BuyerLabels(store)
        self.commands = {"!помощь": help.handle, "!команды": help.handle, "!статус": status_command.handle,
                         "!заказ": orders.handle, "!возврат": refund.handle, "!поддержка": support.handle,
                         "!автор": author.handle, "!данные": data.handle, "!инструкция": instruction.handle}

    def say(self, row, text, key):
        self.store.enqueue(row["id"], "text", key, body=text)

    def accept(self, sale):
        if not self.store.add(sale):
            return False
        row = self.store.get(sale["id"])
        count = len(self.store.rows("SELECT id FROM orders WHERE buyer=?", (row["buyer"],)))
        if count > 1:
            self.say(row, message(f"Рады вас видеть снова! Это ваша {count}-я покупка у нас.", True), "greeting:"+row["id"])
        product = self.products[row["sku"]]
        self.say(row, message(f"Заказ #{row['id']} принят.\n{product.name}\nКоличество: {row['qty']}.\n\n"
                              "Проверяем наличие у поставщика. Данные и инструкцию отправим в этот чат.\n"
                              "Статус: !статус. Помощь: !поддержка."), "accepted:"+row["id"])
        if self.labels.get(row["buyer"])["needs_owner_review"]:
            self.store.alert(row["id"], "BUYER_LABEL_REQUIRES_REVIEW")
        self.store.sync_buyer(row["buyer"])
        return True

    def own_orders(self, chat, buyer):
        return self.store.rows("SELECT * FROM orders WHERE chat=? AND buyer=? ORDER BY created DESC LIMIT 50", (chat, buyer))

    def select(self, chat, buyer, action, event_id):
        rows = self.own_orders(chat, buyer)
        if not rows:
            return
        if len(rows) == 1:
            self.apply(rows[0], action, event_id)
            return
        self.store.menu(chat, buyer, action, [r["id"] for r in rows])
        text = "Выберите заказ:\n\n" + "\n".join(f"{i} #{r['id']} — {self.products[r['sku']].name}" for i,r in enumerate(rows,1))
        self.say(rows[0], message(text+"\n\nОтветьте только цифрой."), f"menu:{chat}:{event_id}")

    def apply(self, row, action, event_id):
        if action == "refund":
            if not row["refundable"] or row["delivery_started"] or row["state"] not in ("accepted", "declined", "provider_failed"):
                self.say(row, message("Автоматический возврат недоступен: закупка или выдача начата либо результат требует проверки. Напишите !поддержка."), f"refund-denied:{row['chat']}:{event_id}")
                return
            self.store.menu(row["chat"], row["buyer"], "refund_confirm", [row["id"]])
            self.say(row, message(f"Заказ #{row['id']}.\n\n+ Подтвердить возврат\n- Отмена"), f"refund-confirm:{row['chat']}:{event_id}")
        elif action == "data":
            if row["receipt"] and row["state"] in ("ready", "delivered"):
                self.store.enqueue(row["id"], "repeat", f"repeat:{row['chat']}:{event_id}")
            else:
                self.say(row, message("Данные ещё не выданы или требуется проверка. Напишите !статус или !поддержка."), f"not-ready:{row['chat']}:{event_id}")
        elif action == "support":
            self.store.alert(row["id"], "BUYER_REQUESTED_SUPPORT")
            self.say(row, message(f"Запрос по заказу #{row['id']} записан для продавца. Опишите проблему в этом чате. Пароли, коды и данные аккаунта повторно присылать не нужно."), f"support:{row['chat']}:{event_id}")
        elif action == "instruction":
            self.say(row, message(self.products[row["sku"]].instruction), f"instruction:{row['chat']}:{event_id}")
        else:
            self.say(row, message(status(row)), f"status:{row['chat']}:{event_id}")

    def handle(self, chat, buyer, text, event_id):
        if not isinstance(event_id, int) or event_id <= 0:
            return
        with self.store.transaction() as db:
            if not db.execute("INSERT OR IGNORE INTO messages VALUES(?,?)", (chat,event_id)).rowcount:
                return
        text = text.strip()
        if text.split() and text.split()[0].casefold() in self.commands:
            with self.store.transaction() as db:
                db.execute("DELETE FROM menus WHERE chat=? AND buyer=?", (chat,buyer))
            self.commands[text.split()[0].casefold()](self,chat,buyer,event_id)
            return
        menus = self.store.rows("SELECT * FROM menus WHERE chat=? AND buyer=? AND expires>?", (chat,buyer,time.time()))
        if not menus:
            return
        menu = menus[0]
        options = json.loads(menu["options"])
        if menu["kind"] == "refund_confirm":
            if text not in ("+", "-"):
                row=self.store.get(options[0])
                if row:
                    self.say(row,message("Ответьте только + для возврата или - для отмены."),f"invalid-confirm:{chat}:{event_id}")
                return
            if text == "+":
                row = self.store.get(options[0])
                if row and row["chat"] == chat and row["buyer"] == buyer and row["refundable"] and not row["delivery_started"]:
                    if self.store.change(row["id"], ("accepted", "declined", "provider_failed"), "refund_queued"):
                        self.say(row, message("Возврат запрошен. Результат сообщим после проверки FunPay."), f"refund-requested:{chat}:{event_id}")
            with self.store.transaction() as db:
                db.execute("DELETE FROM menus WHERE chat=? AND buyer=?",(chat,buyer))
            return
        if re.fullmatch(r"[1-9][0-9]{0,2}",text) and 1 <= int(text) <= len(options):
            row = self.store.get(options[int(text)-1])
            if row and row["chat"] == chat and row["buyer"] == buyer:
                with self.store.transaction() as db:
                    db.execute("DELETE FROM menus WHERE chat=? AND buyer=?",(chat,buyer))
                self.apply(row, menu["kind"], event_id)
        else:
            row=self.store.get(options[0])
            if row:
                self.say(row,message("Ответьте только цифрой из списка: 1, 2 и т. д."),f"invalid-choice:{chat}:{event_id}")
