from ..texts import message

def handle(engine, chat, buyer, event_id):
    rows = engine.own_orders(chat,buyer)
    if rows:
        engine.say(rows[0], message("Plugins For FunPay\nАвтор: @aftreen\nhttps://t.me/aftreen"), f"author:{chat}:{event_id}")
