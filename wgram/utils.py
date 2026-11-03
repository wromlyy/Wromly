"""Мелкие помощники: экранирование, ссылки, разбиение длинного текста."""

import html as _html
import re
from typing import List


def normalize_parse(parse):
    """'html' -> 'HTML', 'md' -> 'MarkdownV2', None/False/'none' -> None."""
    if parse is None or parse is False:
        return None
    p = str(parse).strip().lower()
    if p in ("", "none", "plain", "text"):
        return None
    if p == "html":
        return "HTML"
    if p in ("md", "markdown", "markdownv2", "md2"):
        return "MarkdownV2"
    raise ValueError("parse должен быть 'html', 'md' или None, а не {!r}".format(parse))


def escape_html(text) -> str:
    """Экранирует <, > и & для parse='html'."""
    return _html.escape(str(text), quote=False)


def premium_emoji(emoji_id, fallback) -> str:
    """HTML-тег custom emoji для сообщения с parse='html'.

    fallback должен быть обычным emoji, соответствующим emoji_id.
    """
    emoji_id = str(emoji_id).strip()
    if not emoji_id or not all("0" <= char <= "9" for char in emoji_id):
        raise ValueError("emoji_id должен состоять из цифр")
    fallback = str(fallback)
    if not fallback:
        raise ValueError("fallback не должен быть пустым")
    return '<tg-emoji emoji-id="{}">{}</tg-emoji>'.format(
        emoji_id, escape_html(fallback))


def escape_md(text) -> str:
    """Экранирует спецсимволы для parse='md' (MarkdownV2)."""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", str(text))


def mention(user_id, name) -> str:
    """HTML-упоминание пользователя по id (parse='html')."""
    return '<a href="tg://user?id={}">{}</a>'.format(int(user_id), escape_html(name))


def link(url, text) -> str:
    """HTML-ссылка (parse='html')."""
    return '<a href="{}">{}</a>'.format(_html.escape(str(url), quote=True), escape_html(text))


def split_text(text, limit: int = 4096) -> List[str]:
    """Режет длинный текст на части по limit символов, предпочитая границы строк."""
    text = str(text)
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    parts.append(text)
    return parts
