"""Пост в канал без декораторов и функций."""

import wgram

TOKEN = "PUT_YOUR_BOT_TOKEN_HERE"
CHANNEL_ID = -1001234567890
PHOTO = "post.jpg"

if TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
    raise SystemExit("Вставь токен от @BotFather в TOKEN")

bot = wgram.start(TOKEN, parse="html")
buttons = wgram.menu(
    wgram.choice("Хочу", "yes", color="success"),
    wgram.choice("Позже", "later", color="danger"),
)

bot.when("/post").post(
    CHANNEL_ID, "<b>Новый пост</b> — написал {first_name}",
    photo=PHOTO, buttons=buttons,
)
bot.when_button("yes").say("Отлично!")
bot.when_button("later").say("Хорошо, позже")

bot.run()
