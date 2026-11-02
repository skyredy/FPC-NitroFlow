SQL = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS orders(
 id TEXT PRIMARY KEY,seller INTEGER NOT NULL,buyer INTEGER NOT NULL,chat INTEGER NOT NULL,
 sku TEXT NOT NULL,qty INTEGER NOT NULL,sale TEXT NOT NULL,username TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'accepted',created REAL NOT NULL,updated REAL NOT NULL,
 due REAL NOT NULL DEFAULT 0,attempts INTEGER NOT NULL DEFAULT 0,
 request_id TEXT NOT NULL UNIQUE,provider_id TEXT,expected TEXT,receipt TEXT,
 purchase_started REAL,delivery_started INTEGER NOT NULL DEFAULT 0,
 refundable INTEGER NOT NULL DEFAULT 1,error TEXT,delivered_at REAL);
CREATE TABLE IF NOT EXISTS events(
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,order_id TEXT NOT NULL,state TEXT NOT NULL,
 at REAL NOT NULL,error TEXT);
CREATE TABLE IF NOT EXISTS outbox(
 id INTEGER PRIMARY KEY AUTOINCREMENT,order_id TEXT NOT NULL,kind TEXT NOT NULL,
 key TEXT NOT NULL UNIQUE,body TEXT,state TEXT NOT NULL DEFAULT 'pending',due REAL NOT NULL,
 sent_at REAL,error TEXT);
CREATE TABLE IF NOT EXISTS alerts(
 id INTEGER PRIMARY KEY AUTOINCREMENT,order_id TEXT,code TEXT NOT NULL,at REAL NOT NULL,
 acknowledged INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS menus(
 chat INTEGER NOT NULL,buyer INTEGER NOT NULL,kind TEXT NOT NULL,options TEXT NOT NULL,
 expires REAL NOT NULL,PRIMARY KEY(chat,buyer));
CREATE TABLE IF NOT EXISTS messages(chat INTEGER NOT NULL,id INTEGER NOT NULL,PRIMARY KEY(chat,id));
CREATE TABLE IF NOT EXISTS buyer_labels(buyer INTEGER PRIMARY KEY,status TEXT NOT NULL,reason TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS buyer_label_events(sequence INTEGER PRIMARY KEY AUTOINCREMENT,buyer INTEGER NOT NULL,status TEXT NOT NULL,reason TEXT NOT NULL,at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lot_pauses(lot INTEGER PRIMARY KEY,sku TEXT NOT NULL,reason TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS unique_market_item ON orders(provider_id) WHERE provider_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS gift_fingerprints(fingerprint TEXT PRIMARY KEY,order_id TEXT NOT NULL UNIQUE);
CREATE TRIGGER IF NOT EXISTS immutable_market_item BEFORE UPDATE OF provider_id ON orders
 WHEN OLD.provider_id IS NOT NULL AND OLD.provider_id IS NOT NEW.provider_id
 BEGIN SELECT RAISE(ABORT,'MarketItemImmutable'); END;
CREATE TRIGGER IF NOT EXISTS protect_refund BEFORE UPDATE OF state ON orders
 WHEN NEW.state IN ('refund_queued','refunding','refunded') AND (OLD.refundable=0 OR OLD.delivery_started=1)
 BEGIN SELECT RAISE(ABORT,'RefundForbidden'); END;
CREATE TRIGGER IF NOT EXISTS protect_delivery_flag BEFORE UPDATE OF delivery_started ON orders
 WHEN OLD.delivery_started=1 AND NEW.delivery_started=0
 BEGIN SELECT RAISE(ABORT,'DeliveryFlagImmutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_identity BEFORE UPDATE ON orders
 WHEN OLD.id<>NEW.id OR OLD.buyer<>NEW.buyer OR OLD.chat<>NEW.chat OR OLD.seller<>NEW.seller
 OR OLD.sku<>NEW.sku OR OLD.qty<>NEW.qty OR OLD.request_id<>NEW.request_id
 BEGIN SELECT RAISE(ABORT,'OrderIdentityImmutable'); END;
"""
