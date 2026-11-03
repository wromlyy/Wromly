"""Оплата Telegram Stars: счёт -> подтверждение -> успешная оплата."""
import wgram

bot = wgram.start("ВАШ_ТОКЕН")


@bot.on("/buy")
def buy(msg):
    # prices=50 -> 50 звёзд. Для звёзд provider_token не нужен.
    msg.reply_invoice("Премиум на месяц", "Доступ ко всем функциям", "premium_month", 50,
                      keyboard=wgram.InlineKeyboard([wgram.InlineButton("Оплатить 50 ⭐", pay=True)]))


@bot.on_checkout                                   # у вас 10 секунд, чтобы ответить
def checkout(c):
    if c.payload == "premium_month":
        c.ok()
    else:
        c.error("Такого товара нет")


@bot.on_payment                                    # деньги получены
def paid(msg):
    msg.reply("Спасибо за оплату! Выдан: " + msg.payment["invoice_payload"])


bot.run()
