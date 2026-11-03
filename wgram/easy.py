"""Простые правила: что пришло и что ответить, без декораторов."""

import re

from .keyboards import InlineButton, InlineKeyboard, Keyboard
from .utils import escape_html, escape_md


def buttons(*names):
    """Обычные кнопки под полем ввода: buttons("Да", "Нет")."""
    if not names:
        raise ValueError("Добавь хотя бы одну кнопку")
    return Keyboard(list(names))


def menu(*items):
    """Кнопки под сообщением: menu(("Да", "yes"), ("Нет", "no"))."""
    if not items:
        raise ValueError("Добавь хотя бы одну кнопку")
    return InlineKeyboard(list(items))


def choice(text, data=None, url=None, color=None):
    """Одна inline-кнопка; data по умолчанию совпадает с надписью."""
    if data is not None and url is not None:
        raise ValueError("Кнопка может иметь data или url, но не оба сразу")
    if url is not None:
        return InlineButton(text, url=url, style=color)
    return InlineButton(text, data=text if data is None else data, style=color)


class SimpleRule:
    """Правило для сообщения: bot.when('/start').say('Привет')."""

    def __init__(self, bot, register):
        self._bot = bot
        self._register = register
        self._remember_key = None

    def remember(self, key):
        """Запомнить текст пользователя: .remember("name").say("Привет, {name}")."""
        if not isinstance(key, str) or not key.isidentifier():
            raise ValueError("Имя для памяти должно быть одним словом")
        self._remember_key = key
        return self

    def _prepare(self, message):
        if self._remember_key is not None:
            message.user_data[self._remember_key] = message.text

    def _render(self, template, message):
        values = {"text": message.text, "args": message.args,
                  "first_name": message.user.first_name if message.user else ""}
        values.update(message.user_data)
        escape = (escape_html if self._bot.parse_mode == "HTML" else
                  escape_md if self._bot.parse_mode == "MarkdownV2" else str)
        return re.sub(r"\{([A-Za-z_][A-Za-z_0-9]*)\}",
                      lambda match: escape(values[match.group(1)])
                      if match.group(1) in values else match.group(0), str(template))

    def do(self, handler):
        """Подключить свою функцию, когда короткого ответа недостаточно."""
        if not callable(handler):
            raise TypeError("Нужна функция обработки сообщения")
        self._register(handler)
        return handler

    def say(self, text, buttons=None, clear_state=False):
        """Ответить текстом. После ответа можно убрать состояние."""
        def answer(message):
            self._prepare(message)
            result = message.say(self._render(text, message), buttons=buttons)
            if clear_state:
                message.clear_state()
            return result
        return self.do(answer)

    def ask(self, text, state, buttons=None):
        """Задать вопрос и ждать следующее сообщение в состоянии state."""
        if not isinstance(state, str) or not state:
            raise ValueError("Укажи непустое имя состояния")
        def answer(message):
            self._prepare(message)
            return message.ask(self._render(text, message), state, buttons=buttons)
        return self.do(answer)

    def picture(self, photo, caption=None, buttons=None):
        """Ответить фото из файла, URL или Telegram file_id."""
        def answer(message):
            self._prepare(message)
            text = self._render(caption, message) if caption is not None else None
            return message.send_picture(photo, caption=text, buttons=buttons)
        return self.do(answer)

    def file(self, document, caption=None, buttons=None):
        """Ответить документом из файла, URL или Telegram file_id."""
        def answer(message):
            self._prepare(message)
            text = self._render(caption, message) if caption is not None else None
            return message.send_file(document, caption=text, buttons=buttons)
        return self.do(answer)

    def post(self, chat_id, text, photo=None, buttons=None, admins_only=True):
        """Опубликовать текст или фото в канале одной строкой."""
        def publish(message):
            try:
                if admins_only and (message.user is None or not self._bot.is_admin(
                        chat_id, message.user.id)):
                    return message.say("Публиковать может только администратор канала.")
                self._prepare(message)
                content = self._render(text, message)
                if photo is None:
                    sent = self._bot.say(chat_id, content, buttons=buttons)
                else:
                    sent = self._bot.picture(chat_id, photo, caption=content,
                                             buttons=buttons)
                return message.say("Опубликовано. ID: {}".format(sent.message_id))
            except Exception as exc:
                return message.say("Ошибка публикации: " + str(exc), parse=False)
        return self.do(publish)


class SimpleButtonRule:
    """Правило для нажатой inline-кнопки."""

    def __init__(self, register):
        self._register = register

    def do(self, handler):
        if not callable(handler):
            raise TypeError("Нужна функция обработки кнопки")
        self._register(handler)
        return handler

    def say(self, text):
        """Показать короткую подсказку после нажатия кнопки."""
        return self.do(lambda button: button.answer(text))
