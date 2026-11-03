"""Публикация поста из отдельного файла обработчиков."""

import logging
from pathlib import Path

import wgram

PHOTO = Path(__file__).resolve().parent.parent / "post.png"
EMOJI_ID = "5368324170671202286"


def register(bot, config) -> None:
    @bot.on("/post", chat="private")
    def post(message):
        try:
            if message.user is None or not bot.is_admin(config.channel_id, message.user.id):
                message.reply("Команда доступна только администраторам канала.")
                return
            keyboard = wgram.InlineKeyboard(
                [wgram.InlineButton("Одобрить", data="approve", style="success"),
                 wgram.InlineButton("Отклонить", data="reject", style="danger")],
                [wgram.InlineButton("Подробнее", data="details", style="primary")],
            )
            caption = "<b>Новый пост</b> " + wgram.premium_emoji(EMOJI_ID, "👍")
            sent = bot.send_photo(config.channel_id, PHOTO, caption=caption,
                                  keyboard=keyboard, parse="html")
            message.reply("Опубликовано. ID сообщения: {}".format(sent.message_id))
        except Exception as exc:
            logging.exception("Ошибка публикации")
            message.reply("Ошибка: " + wgram.escape_html(str(exc)))

    @bot.on_button("approve", "reject", "details")
    def button(callback):
        replies = {"approve": "Одобрено", "reject": "Отклонено",
                   "details": "Пост отправлен через wgram"}
        callback.answer(replies[callback.data])
