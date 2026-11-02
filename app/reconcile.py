from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import time
from .filter import identify

def timestamp(item):
    stamp=item.date
    if not isinstance(stamp,datetime):
        raise ValueError("OrderDateUnavailable")
    if stamp.tzinfo is None:
        stamp=stamp.replace(tzinfo=ZoneInfo("Europe/Moscow"))
    return stamp.timestamp()

def scan(account, store, engine):
    cutoff = float(store.meta("accept_orders_after",int(time.time()//60)*60))
    cursor = None
    for _ in range(10):
        cursor, orders = account.get_sells(start_from=cursor, include_closed=False, include_refunded=False)
        old = False
        for item in orders:
            if timestamp(item) < cutoff:
                old = True
                continue
            if store.get(item.id):
                continue
            sale = identify(account,account.get_order(item.id),engine.products)
            if sale:
                engine.accept(sale)
        if not cursor or old:
            break
