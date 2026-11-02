import argparse
import json
from pathlib import Path
from app.settings import Settings
from app.store import Store
from app.labels import BuyerLabels

def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("alerts")
    commands.add_parser("orders")
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("order_id")
    label = commands.add_parser("label")
    label.add_argument("buyer", type=int)
    label.add_argument("status", choices=["neutral", "good", "suspicious", "restricted"])
    label.add_argument("reason")
    export = commands.add_parser("backup")
    export.add_argument("destination", type=Path)
    args = parser.parse_args()
    settings = Settings.load()
    if args.command == "backup":
        from app.backup import backup
        backup(settings.root, args.destination.resolve())
        print("Backup verified")
        return
    store = Store(settings.root / "data/orders.sqlite3")
    try:
        if args.command == "reconcile":
            row = store.get(args.order_id)
            if not row or not row["provider_id"] or row["state"] not in ("manual", "purchasing", "processing", "retry_buy"):
                raise ValueError("AssignedMarketItemRequired")
            from app.market import Market
            from app.purchase import Purchaser
            from app.vault import Vault
            from app.ports import FunPayPort
            from FunPayAPI import Account
            port = FunPayPort(Account(settings.token).get(), settings.products)
            if not port.eligible(row, paid_only=False):
                raise ValueError("FunPayOrderRequiresReview")
            provider = Market(settings.api_key)
            Purchaser(store, provider, port, settings.products, Vault(settings.root / "data/vault.key")).reconcile(row)
            result = {"state": store.get(row["id"])["state"]}
        elif args.command == "label":
            result = BuyerLabels(store).set(args.buyer, args.status, args.reason)
        elif args.command == "alerts":
            result = store.rows("SELECT * FROM alerts ORDER BY id DESC LIMIT 100")
        else:
            result = store.rows("SELECT id,buyer,sku,qty,state,error,provider_id FROM orders ORDER BY created DESC LIMIT 100")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        store.db.close()

if __name__ == "__main__":
    main()
