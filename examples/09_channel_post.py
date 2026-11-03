"""Пост в канал по команде /post от администратора канала."""

import logging
import struct
import zlib

import wgram

BOT_TOKEN = ""
CHANNEL_ID = 0  # Числовой ID приватного канала, например -1001234567890
CUSTOM_EMOJI_ID = "5368324170671202286"  # Публичный пример Telegram: 👍


def make_photo() -> bytes:
    """Создаёт PNG штатными средствами Python; отдельный файл не нужен."""
    width, height = 320, 180
    pixels = bytearray()
    for y in range(height):
        pixels.append(0)  # PNG filter: None
        for x in range(width):
            pixels.extend((20 + x // 8, 70 + y // 4, 160 + x // 6))

    def chunk(kind: bytes, data: bytes) -> bytes:
        payload = kind + data
        return struct.pack(">I", len(data)) + payload + struct.pack(
            ">I", zlib.crc32(payload) & 0xFFFFFFFF
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(pixels)))
        + chunk(b"IEND", b"")
    )


if not BOT_TOKEN or CHANNEL_ID == 0:
    raise SystemExit("Заполните BOT_TOKEN и CHANNEL_ID в начале файла")

bot = wgram.start(BOT_TOKEN, parse="html")


@bot.on("/post", chat="private")
def post(message):
    try:
        if message.user is None or not bot.is_admin(CHANNEL_ID, message.user.id):
            message.reply("Команда доступна только администраторам канала.")
            return

        caption = (
            "<b>Пост от Wgram</b> "
            + wgram.premium_emoji(CUSTOM_EMOJI_ID, "👍")
            + "\nНажмите кнопку под фото."
        )
        buttons = wgram.InlineKeyboard(
            [
                wgram.InlineButton("Одобрить", data="approve", style="success"),
                wgram.InlineButton("Отклонить", data="reject", style="danger"),
            ],
            [wgram.InlineButton("Подробнее", data="details", style="primary")],
        )
        sent = bot.send_photo(
            CHANNEL_ID, make_photo(), caption=caption, keyboard=buttons, parse="html"
        )
        emoji_in_response = any(
            entity.get("type") == "custom_emoji"
            and entity.get("custom_emoji_id") == CUSTOM_EMOJI_ID
            for entity in sent.raw.get("caption_entities", [])
        )
        styles_in_response = [
            button.get("style")
            for row in sent.raw.get("reply_markup", {}).get("inline_keyboard", [])
            for button in row
        ]
        message.reply(
            "Пост опубликован. ID: {}\n"
            "Ответ API: custom_emoji={}, styles={}".format(
                sent.message_id, emoji_in_response, styles_in_response
            )
        )
    except Exception as exc:
        logging.exception("Не удалось опубликовать пост")
        try:
            message.reply("Ошибка публикации: " + wgram.escape_html(str(exc)))
        except Exception:
            logging.exception("Не удалось отправить сообщение об ошибке")


@bot.on_button("approve", "reject", "details")
def handle_button(callback):
    answers = {
        "approve": "Одобрено",
        "reject": "Отклонено",
        "details": "Это пример поста на Wgram",
    }
    callback.answer(answers[callback.data])


if __name__ == "__main__":
    bot.run(skip_old=True)
