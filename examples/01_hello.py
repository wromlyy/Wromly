"""Самый простой бот: команда, точный текст, запасной вариант."""
import wgram

bot = wgram.start("ВАШ_ТОКЕН")          # токен выдаёт @BotFather


@bot.on("/start")
def hello(msg):
    msg.reply("Привет, " + msg.user.first_name + "! Это мой бот")


@bot.on("/say")
def say(msg):
    # /say привет всем  ->  msg.args == "привет всем"
    return msg.args or "Напиши что-нибудь после /say"     # return строки = ответ


@bot.on("текст")
def echo(msg):
    msg.reply("Ты написал: " + msg.text)


@bot.on()                                # все остальные сообщения
def other(msg):
    msg.reply("Не понял. Попробуй /start")


bot.run()
