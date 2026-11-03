"""Первый бот без @ и def: поменяй TOKEN и запусти файл."""

import wgram

TOKEN = "PUT_YOUR_BOT_TOKEN_HERE"

if TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
    raise SystemExit("Вставь токен от @BotFather в переменную TOKEN")

bot = wgram.start(TOKEN)

bot.when("/start").say("Привет! Напиши 'привет' или отправь фото.")
bot.when("привет").ask("Как тебя зовут?", state="name")
bot.when_state("name").say("Очень приятно!", clear_state=True)
bot.when_photo().say("Красивое фото!")
bot.when_contains("кот").say("Мяу!")

buttons = wgram.menu(
    wgram.choice("Да", "yes", color="success"),
    wgram.choice("Нет", "no", color="danger"),
)
bot.when("/menu").say("Выбери кнопку:", buttons=buttons)
bot.when_button("yes").say("Ты выбрал Да")
bot.when_button("no").say("Ты выбрал Нет")

bot.run()
