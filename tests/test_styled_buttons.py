"""Проверка JSON разметки и HTML custom emoji на пути отправки фото."""

import unittest

from test_wgram import make_bot, msg, upd
from wgram import InlineButton, InlineKeyboard, premium_emoji
from wgram.api import _form_value


class StyledPostTests(unittest.TestCase):
    def test_style_validation_and_old_button(self):
        self.assertEqual(
            InlineButton("Да", data="yes", style="success").to_dict(),
            {"text": "Да", "style": "success", "callback_data": "yes"},
        )
        self.assertEqual(
            InlineButton("Да", data="yes").to_dict(),
            {"text": "Да", "callback_data": "yes"},
        )
        for style in ("primary", "success", "danger"):
            self.assertEqual(InlineButton("X", data="x", style=style).to_dict()["style"], style)
        with self.assertRaises(ValueError):
            InlineButton("X", data="x", style="red")

    def test_photo_keeps_custom_emoji_and_styles(self):
        bot, api = make_bot([[upd(1, message=msg("/post"))]], parse="html")
        emoji = premium_emoji("5368324170671202286", "👍")
        keyboard = InlineKeyboard(
            [InlineButton("Да", data="yes", style="success")],
            [InlineButton("Нет", data="no", style="danger")],
            [InlineButton("Инфо", data="info", style="primary")],
        )

        @bot.on("/post")
        def post(message):
            bot.send_photo(-1001234567890, b"photo", caption=emoji,
                           keyboard=keyboard, parse="html")

        bot.run()
        params = api.find("sendPhoto")[0]
        self.assertEqual(params["caption"], emoji)
        self.assertEqual(params["parse_mode"], "HTML")
        rows = params["reply_markup"]["inline_keyboard"]
        self.assertEqual([row[0]["style"] for row in rows],
                         ["success", "danger", "primary"])
        self.assertIn('"style": "success"', _form_value(params["reply_markup"]))

    def test_emoji_helper_validates_id(self):
        self.assertEqual(
            premium_emoji("123", "🔥"),
            '<tg-emoji emoji-id="123">🔥</tg-emoji>',
        )
        with self.assertRaises(ValueError):
            premium_emoji('123" onclick="x', "🔥")
        with self.assertRaises(ValueError):
            premium_emoji("123", "")
