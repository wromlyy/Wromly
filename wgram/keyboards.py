"""Клавиатуры: обычные (под полем ввода) и inline (под сообщением).

Правило для строк: list = одна строка кнопок, всё остальное = строка из одной кнопки.

    Keyboard(["Да", "Нет"], ["Отмена"])          # 2 строки: в первой две кнопки
    InlineKeyboard([("Да", "yes"), ("Нет", "no")])
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

_URL_PREFIXES = ("http://", "https://", "tg://")


# ---------------------------------------------------------------- обычная

class Button:
    """Кнопка обычной клавиатуры. Просто строка тоже сработает."""

    def __init__(self, text, contact=False, location=False, poll=None, web_app=None):
        self.text = str(text)
        self.contact = contact        # запросить телефон пользователя
        self.location = location      # запросить геопозицию
        self.poll = poll              # True / "quiz" / "regular": запросить создание опроса
        self.web_app = web_app        # URL мини-приложения

    def to_dict(self) -> Dict[str, Any]:
        d = {"text": self.text}
        if self.contact:
            d["request_contact"] = True
        if self.location:
            d["request_location"] = True
        if self.poll:
            d["request_poll"] = {} if self.poll is True else {"type": self.poll}
        if self.web_app:
            d["web_app"] = {"url": self.web_app}
        return d


def _btn(b) -> Dict[str, Any]:
    if isinstance(b, Button):
        return b.to_dict()
    if isinstance(b, dict):
        return b
    if isinstance(b, str):
        return {"text": b}
    raise TypeError("Кнопка должна быть строкой или Button, а не {!r}".format(b))


def _rows(rows) -> List[list]:
    return [list(row) if isinstance(row, list) else [row] for row in rows]


class Keyboard:
    """Обычная клавиатура под полем ввода.

    Keyboard(["Да", "Нет"], ["Отмена"], resize=True, one_time=False, placeholder="Выберите...")
    Keyboard.grid(["1", "2", "3", "4", "5"], columns=3)
    """

    def __init__(self, *rows, resize=True, one_time=False, placeholder=None,
                 persistent=False, selective=False):
        if not rows:
            raise ValueError("Пустая клавиатура: передайте хотя бы одну кнопку")
        self.rows = _rows(rows)
        self.resize = resize
        self.one_time = one_time
        self.placeholder = placeholder
        self.persistent = persistent
        self.selective = selective

    @classmethod
    def grid(cls, items, columns=2, **options):
        """Раскладывает плоский список кнопок по columns штук в строке."""
        items = list(items)
        rows = [items[i:i + columns] for i in range(0, len(items), columns)]
        return cls(*rows, **options)

    def to_dict(self) -> Dict[str, Any]:
        d = {"keyboard": [[_btn(b) for b in row] for row in self.rows],
             "resize_keyboard": bool(self.resize)}
        if self.one_time:
            d["one_time_keyboard"] = True
        if self.placeholder:
            d["input_field_placeholder"] = self.placeholder
        if self.persistent:
            d["is_persistent"] = True
        if self.selective:
            d["selective"] = True
        return d


class RemoveKeyboard:
    """Убирает обычную клавиатуру: keyboard=wgram.RemoveKeyboard()."""

    def __init__(self, selective=False):
        self.selective = selective

    def to_dict(self):
        d = {"remove_keyboard": True}
        if self.selective:
            d["selective"] = True
        return d


class ForceReply:
    """Просит Telegram открыть ответ на сообщение бота: keyboard=wgram.ForceReply()."""

    def __init__(self, placeholder=None, selective=False):
        self.placeholder = placeholder
        self.selective = selective

    def to_dict(self):
        d = {"force_reply": True}
        if self.placeholder:
            d["input_field_placeholder"] = self.placeholder
        if self.selective:
            d["selective"] = True
        return d


# ---------------------------------------------------------------- inline

class InlineButton:
    """Inline-кнопка. Нужно указать ровно одно действие.

    InlineButton("Да", data="yes")                 # нажатие -> @bot.on_button("yes")
    InlineButton("Сайт", url="https://example.com")
    InlineButton("Открыть", web_app="https://example.com/app")
    InlineButton("Поделиться", switch="текст")      # выбор чата + inline-режим
    InlineButton("Искать тут", switch_here="кот")   # inline-режим в этом же чате
    InlineButton("Скопировать", copy="PROMO2026")   # копирует текст в буфер
    InlineButton("Оплатить", pay=True)              # для счетов (первая кнопка)
    InlineButton("Готово", data="ok", style="success")
    """

    def __init__(self, text, data=None, url=None, web_app=None, switch=None,
                 switch_here=None, copy=None, pay=False, style: str | None = None):
        self.text = str(text)
        self.data = data
        self.url = url
        self.web_app = web_app
        self.switch = switch
        self.switch_here = switch_here
        self.copy = copy
        self.pay = pay
        if style is not None and style not in ("primary", "success", "danger"):
            raise ValueError("style должен быть primary, success, danger или None")
        self.style = style
        chosen = [x for x in (data, url, web_app, switch, switch_here, copy) if x is not None]
        if len(chosen) + (1 if pay else 0) != 1:
            raise ValueError("У inline-кнопки {!r} нужно указать ровно одно действие "
                             "(data, url, web_app, switch, switch_here, copy или pay)".format(text))
        if data is not None and len(str(data).encode("utf-8")) > 64:
            raise ValueError("data кнопки {!r} длиннее 64 байт (лимит Telegram)".format(text))

    def to_dict(self) -> Dict[str, Any]:
        d = {"text": self.text}
        if self.style is not None:
            d["style"] = self.style
        if self.data is not None:
            d["callback_data"] = str(self.data)
        elif self.url is not None:
            d["url"] = self.url
        elif self.web_app is not None:
            d["web_app"] = {"url": self.web_app}
        elif self.switch is not None:
            d["switch_inline_query"] = self.switch
        elif self.switch_here is not None:
            d["switch_inline_query_current_chat"] = self.switch_here
        elif self.copy is not None:
            d["copy_text"] = {"text": str(self.copy)}
        elif self.pay:
            d["pay"] = True
        return d


def _ibtn(b) -> Dict[str, Any]:
    if isinstance(b, InlineButton):
        return b.to_dict()
    if isinstance(b, dict):
        return b
    if isinstance(b, str):                       # "Да" -> текст и data одинаковые
        return InlineButton(b, data=b).to_dict()
    if isinstance(b, tuple) and len(b) == 2:     # ("Текст", "data") или ("Текст", "https://...")
        text, second = b
        if isinstance(second, str) and second.startswith(_URL_PREFIXES):
            return InlineButton(text, url=second).to_dict()
        return InlineButton(text, data=second).to_dict()
    raise TypeError("Inline-кнопка: ожидалась InlineButton, строка или пара (текст, data/url), "
                    "а не {!r}".format(b))


class InlineKeyboard:
    """Кнопки под сообщением.

    InlineKeyboard([("Да", "yes"), ("Нет", "no")],
                   [("Сайт", "https://example.com")])
    InlineKeyboard.grid([("1", "n:1"), ("2", "n:2"), ("3", "n:3")], columns=2)
    """

    def __init__(self, *rows):
        if not rows:
            raise ValueError("Пустая inline-клавиатура: передайте хотя бы одну кнопку")
        self.rows = _rows(rows)

    @classmethod
    def grid(cls, items, columns=2):
        items = list(items)
        return cls(*[items[i:i + columns] for i in range(0, len(items), columns)])

    def to_dict(self) -> Dict[str, Any]:
        return {"inline_keyboard": [[_ibtn(b) for b in row] for row in self.rows]}


# ---------------------------------------------------------------- общий вход

def to_markup(obj) -> Optional[Dict[str, Any]]:
    """Превращает что угодно (Keyboard, InlineKeyboard, список списков) в reply_markup.

    Список списков: строки/Button -> обычная клавиатура,
    пары (текст, data) и InlineButton -> inline-клавиатура.
    """
    if obj is None:
        return None
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, (list, tuple)):
        rows = list(obj)
        if not rows:
            return None
        if not any(isinstance(r, list) for r in rows):
            rows = [rows]                          # плоский список = одна строка
        flat = [b for r in rows for b in (r if isinstance(r, list) else [r])]
        if any(isinstance(b, (tuple, InlineButton)) for b in flat):
            return InlineKeyboard(*rows).to_dict()
        return Keyboard(*rows).to_dict()
    raise TypeError("keyboard: неподдерживаемый тип {!r}".format(type(obj).__name__))
