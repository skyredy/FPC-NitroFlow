import logging
import time
import os
from .engine import Engine
from .filter import identify
from .lock import InstanceLock
from .store import Store
from .vault import Vault
from .worker import Worker

def run(settings):
    if not settings.configured:
        raise RuntimeError("LiveConfigurationIncomplete")
    from FunPayAPI import Account, Runner, enums
    if hasattr(time,"tzset"):
        os.environ.setdefault("TZ","Europe/Moscow")
        time.tzset()
    instance = InstanceLock(settings.root / "data" / "runtime.lock")
    store = Store(settings.root / "data" / "orders.sqlite3")
    store.recover()
    cutoff=float(store.meta("accept_orders_after",int(time.time()//60)*60))
    vault = Vault(settings.root / "data" / "vault.key")
    worker = Worker(store,settings,vault)
    try:
        account = Account(settings.token,requests_timeout=15).get()
        engine = Engine(store,settings.products)
        worker.start()
        for event in Runner(account).listen(requests_delay=4):
            if not worker.thread.is_alive():
                raise RuntimeError("WorkerStopped")
            try:
                if event.type in (enums.EventTypes.NEW_ORDER,enums.EventTypes.ORDER_STATUS_CHANGED):
                    from .reconcile import timestamp
                    if timestamp(event.order)<cutoff:
                        continue
                    sale = identify(account,account.get_order(event.order.id),settings.products)
                    if sale:
                        engine.accept(sale)
                elif event.type is enums.EventTypes.NEW_MESSAGE:
                    msg=event.message
                    if msg.author_id and msg.author_id!=account.id and not msg.by_bot:
                        engine.handle(msg.chat_id,msg.author_id,msg.text or "",msg.id)
            except Exception as exc:
                logging.error("Event failed: %s",type(exc).__name__)
    finally:
        if worker.thread.ident is not None:
            worker.close()
        store.db.close()
        instance.close()
