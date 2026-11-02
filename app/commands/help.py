from ..texts import message

def handle(engine, chat, buyer, event_id):
    rows = engine.own_orders(chat,buyer)
    if rows:
        engine.say(rows[0], message("!заказ — выбрать заказ\n!статус — проверить выдачу\n!данные — повторить свои данные\n"
            "!инструкция — инструкция\n!возврат — запрос до закупки/выдачи\n!поддержка — помощь продавца\n!автор — автор проекта"), f"help:{chat}:{event_id}")
