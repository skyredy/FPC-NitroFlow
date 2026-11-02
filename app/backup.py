import hashlib
import json
import shutil
import sqlite3
from .profiles import Profiles
from .store import Store

def backup(root, destination):
    destination.mkdir(parents=True,mode=0o700,exist_ok=False)
    (destination/"data").mkdir(mode=0o700)
    source=sqlite3.connect(f"file:{(root/'data/orders.sqlite3').as_posix()}?mode=ro",uri=True)
    target=sqlite3.connect(destination/"data/orders.sqlite3")
    try:
        source.backup(target)
        if target.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise RuntimeError("BackupIntegrityFailed")
    finally:
        target.close()
        source.close()
    key=root/"data/vault.key"
    if key.exists():
        shutil.copyfile(key,destination/"data/vault.key")
        (destination/"data/vault.key").chmod(0o600)
    store=Store(destination/"data/orders.sqlite3")
    try:
        Profiles(store,destination/"Base").rebuild()
    finally:
        store.db.close()
    files={str(p.relative_to(destination)):hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.rglob('*') if p.is_file()}
    (destination/"manifest.json").write_text(json.dumps(files,indent=2),encoding="utf-8")
