"""Задачи по расписанию, запуск/остановка, обработка ошибок, рассылка."""
import wgram

bot = wgram.start("ВАШ_ТОКЕН")
ADMIN_ID = 123456789                               # ваш id (узнайте командой /id в примере 05)
subscribers = set()


@bot.on_startup
def started():
    bot.set_commands({"start": "Подписаться", "stop": "Отписаться"})   # меню команд
    bot.send(ADMIN_ID, "Бот запущен")


@bot.on_shutdown
def stopped():
    bot.send(ADMIN_ID, "Бот остановлен")


@bot.on("/start")
def sub(msg):
    subscribers.add(msg.chat_id)
    msg.reply("Подписка оформлена")


@bot.on("/stop")
def unsub(msg):
    subscribers.discard(msg.chat_id)
    msg.reply("Вы отписаны")


@bot.daily("09:00", days=["mon", "tue", "wed", "thu", "fri"])   # по будням в 9:00
def morning():
    for chat_id in list(subscribers):
        bot.send(chat_id, "Доброе утро!")


@bot.every(3600)                                    # каждый час
def hourly():
    print("Подписчиков:", len(subscribers))


@bot.on_my_chat_member                              # кто-то заблокировал бота
def blocked(upd):
    if upd.blocked:
        subscribers.discard(upd.chat_id)


@bot.on_error                                       # любая ошибка в обработчиках
def on_error(error, obj):
    bot.send(ADMIN_ID, "Ошибка: {!r}".format(error))


bot.run(skip_old=True)                              # skip_old: пропустить накопившиеся сообщения
