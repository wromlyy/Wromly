"""Inline-режим: пользователь пишет @имя_бота запрос в любом чате.
Включите его у @BotFather: /setinline."""
import wgram

bot = wgram.start("ВАШ_ТОКЕН")


@bot.on_inline
def search(q):
    text = q.query.strip() or "привет"
    q.answer([
        wgram.InlineArticle("Крупно", text.upper(), description="Отправить ЗАГЛАВНЫМИ"),
        wgram.InlineArticle("Мелко", text.lower(), description="Отправить строчными"),
        wgram.InlineArticle("Задом наперёд", text[::-1]),
    ], cache=10)


bot.run()
