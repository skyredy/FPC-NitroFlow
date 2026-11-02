import json
import logging
import os
from html import escape
import requests
from dotenv import dotenv_values

class Alerts:
    def __init__(self, store, root):
        self.store = store
        values=dotenv_values(root/".env")
        self.token = os.environ.get("OWNER_BOT_TOKEN",values.get("OWNER_BOT_TOKEN") or "")
        self.chat = os.environ.get("OWNER_CHAT_ID",values.get("OWNER_CHAT_ID") or "")

    def tick(self):
        rows = self.store.rows("SELECT * FROM alerts WHERE acknowledged=0 ORDER BY id LIMIT 10")
        for row in rows:
            text = f"Заказ #{row['order_id'] or '—'}: {row['code']}. Проверьте журнал FPC-NitroFlow."
            if self.token and self.chat:
                response = requests.post(f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json={"chat_id":self.chat,"text":'<tg-emoji emoji-id="6028435952299413210">ℹ</tg-emoji>\n\n'+escape(text),
                          "parse_mode":"HTML"},timeout=15)
                if response.status_code != 200 or not response.json().get("ok"):
                    return
            else:
                logging.warning("Owner attention: %s %s", row["order_id"], row["code"])
            with self.store.transaction() as db:
                db.execute("UPDATE alerts SET acknowledged=1 WHERE id=?",(row["id"],))
