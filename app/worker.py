import logging
import threading
import time
from .alerts import Alerts
from .market import Market
from .engine import Engine
from .delivery_queue import prepare
from .refunds import Refunder
from .lots import Lots
from .outbox import Outbox
from .ports import FunPayPort
from .profiles import Profiles
from .purchase import Purchaser
from .reconcile import scan

class Worker:
    def __init__(self, store, settings, vault):
        self.store, self.settings, self.vault = store, settings, vault
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, name="nitro-worker", daemon=True)

    def run(self):
        from FunPayAPI import Account
        while not self.stop.is_set():
            try:
                account = Account(self.settings.token,requests_timeout=15).get()
                break
            except Exception as exc:
                logging.error("Worker authentication postponed: %s",type(exc).__name__)
                self.stop.wait(15)
        else:
            return
        provider = Market(self.settings.api_key)
        port = FunPayPort(account,self.settings.products)
        purchase = Purchaser(self.store,provider,port,self.settings.products,self.vault,self.settings.reconcile_seconds)
        refunder = Refunder(self.store,port)
        outbox = Outbox(self.store,port,self.settings.products,self.vault)
        lots = Lots(self.store,account,provider,self.settings.products,self.settings.auto_resume)
        engine = Engine(self.store,self.settings.products)
        profiles = Profiles(self.store,self.settings.root / "Base")
        alerts = Alerts(self.store,self.settings.root)
        scanned = supervised = exported = 0
        while not self.stop.is_set():
            now = time.time()
            for operation in (refunder.tick,purchase.tick,lambda:prepare(self.store),outbox.tick,alerts.tick):
                try:
                    operation()
                except Exception as exc:
                    logging.error("Worker operation failed: %s",type(exc).__name__)
            if now-scanned>=60:
                try:
                    scan(account,self.store,engine)
                except Exception as exc:
                    logging.error("Order scan failed: %s",type(exc).__name__)
                scanned=now
            if now-supervised>=60:
                try:
                    lots.tick()
                except Exception as exc:
                    logging.error("Lot supervision failed: %s",type(exc).__name__)
                supervised=now
            if now-exported>=15:
                try:
                    profiles.rebuild()
                except Exception as exc:
                    logging.error("Buyer export pending: %s",type(exc).__name__)
                exported=now
            self.stop.wait(self.settings.interval)

    def start(self):
        self.thread.start()

    def close(self):
        self.stop.set()
        self.thread.join(timeout=90)
        if self.thread.is_alive():
            raise RuntimeError("WorkerShutdownIncomplete")
