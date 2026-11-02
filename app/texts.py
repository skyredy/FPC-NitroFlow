from urllib.parse import quote

STATES = {"accepted": "ожидает закупки", "purchasing": "проверяется закупка", "processing": "сверяется результат закупки", "retry_buy": "поставщик запросил повтор проверки",
          "ready": "товар получен от поставщика", "delivered": "выдан", "declined": "закупка приостановлена",
          "provider_failed": "поставщик подтвердил невыдачу", "refund_queued": "возврат запрошен",
          "refunding": "возврат выполняется", "refunded": "деньги возвращены", "manual": "проверяется продавцом",
          "refund_review": "результат возврата проверяется продавцом"}

def message(text, heart=False):
    return ("💙" if heart else "🐦") + "\n\n" + text

def link(row):
    return "https://funpay.com/orders/" + quote(row["id"], safe="") + "/"

def completed(row):
    return message(f"@{row['username'].lstrip('@')}, заказ #{row['id']} выполнен!\n\n{link(row)}\n\n"
                   "Спасибо за покупку! Подтвердите, пожалуйста, получение товара и оставьте отзыв. "
                   "Ваш отзыв помогает мне развивать аккаунт, а у вас это займёт всего пару секунд.\n\nВсего доброго!", True)

def reminder(row):
    return message(f"Напомню о заказе #{row['id']}: товар уже выдан.\n\n{link(row)}\n\n"
                   "Если всё получили, подтвердите, пожалуйста, заказ и оставьте отзыв. "
                   "Если нужна помощь, напишите !поддержка. Всего доброго!", True)

def status(row):
    return f"Заказ #{row['id']}: {STATES.get(row['state'], 'проверяется продавцом')}."
