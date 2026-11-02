import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from .schema import SQL

class Store:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=20)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(SQL)
        self.db.commit()

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
                self.db.commit()
            except BaseException:
                self.db.rollback()
                raise

    def get(self, oid):
        with self.lock:
            row = self.db.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
            return dict(row) if row else None

    def rows(self, query, args=()):
        with self.lock:
            return [dict(row) for row in self.db.execute(query, args).fetchall()]

    def add(self, sale):
        now = time.time()
        with self.transaction() as db:
            cursor = db.execute("INSERT OR IGNORE INTO orders(id,seller,buyer,chat,sku,qty,sale,username,created,updated,request_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (sale["id"], sale["seller"], sale["buyer"], sale["chat"], sale["sku"], sale["qty"],
                 str(sale["sale"]), sale["username"], now, now, "fp-" + uuid.uuid4().hex))
            if cursor.rowcount:
                db.execute("INSERT INTO events(order_id,state,at) VALUES(?,'accepted',?)", (sale["id"], now))
            return bool(cursor.rowcount)

    def change(self, oid, expected_states, state, **fields):
        allowed = {"due", "attempts", "provider_id", "expected", "receipt", "purchase_started", "delivery_started", "refundable", "error", "delivered_at"}
        if fields.keys() - allowed:
            raise ValueError("InvalidOrderFields")
        if isinstance(expected_states, str):
            expected_states = (expected_states,)
        values = dict(fields, state=state, updated=time.time())
        with self.transaction() as db:
            cursor = db.execute("UPDATE orders SET " + ",".join(k + "=?" for k in values) + " WHERE id=? AND state IN (" + ",".join("?" for _ in expected_states) + ")",
                                (*values.values(), oid, *expected_states))
            if cursor.rowcount:
                db.execute("INSERT INTO events(order_id,state,at,error) VALUES(?,?,?,?)", (oid, state, time.time(), fields.get("error")))
            return bool(cursor.rowcount)

    def alert(self, oid, code):
        with self.transaction() as db:
            now=time.time()
            if not db.execute("SELECT 1 FROM alerts WHERE order_id IS ? AND code=? AND at>?",(oid,code,now-300)).fetchone():
                db.execute("INSERT INTO alerts(order_id,code,at) VALUES(?,?,?)", (oid, code, now))

    def enqueue(self, oid, kind, key, due=None, body=None):
        with self.transaction() as db:
            db.execute("INSERT OR IGNORE INTO outbox(order_id,kind,key,body,due) VALUES(?,?,?,?,?)",
                       (oid, kind, key, body, time.time() if due is None else due))

    def recover(self):
        with self.transaction() as db:
            db.execute("UPDATE outbox SET state='uncertain',error='RestartDuringSend' WHERE state='sending'")
            db.execute("UPDATE orders SET state='refund_review',error='RestartDuringRefund' WHERE state='refunding'")

    def menu(self, chat, buyer, kind, options):
        with self.transaction() as db:
            db.execute("INSERT OR REPLACE INTO menus VALUES(?,?,?,?,?)", (chat, buyer, kind, json.dumps(options), time.time()+600))

    def meta(self, key, initial):
        with self.transaction() as db:
            db.execute("INSERT OR IGNORE INTO meta VALUES(?,?)", (key, str(initial)))
            return db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()[0]

    def sync_buyer(self, buyer):
        from .profiles import Profiles
        return Profiles(self, self.path.parent.parent / "Base").write(buyer)
