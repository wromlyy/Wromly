"""Исходящие объекты: альбомы (InputMedia) и результаты inline-режима."""

import uuid
from typing import Any, Dict

from .api import split_file
from .keyboards import to_markup


class InputMedia:
    """Элемент альбома для bot.send_media_group / msg.reply_media_group.

    InputMedia.photo("a.jpg", caption="Первое")
    InputMedia.video("https://example.com/v.mp4")
    Альбом: от 2 до 10 элементов. Фото+видео можно смешивать,
    документы - только с документами, аудио - только с аудио.
    """

    KINDS = ("photo", "video", "document", "audio")

    def __init__(self, kind, media, caption=None, parse=None, spoiler=False):
        if kind not in self.KINDS:
            raise ValueError("kind должен быть одним из {}".format(self.KINDS))
        self.kind = kind
        self.media = media
        self.caption = caption
        self.parse = parse
        self.spoiler = spoiler

    @classmethod
    def photo(cls, media, caption=None, **kw):
        return cls("photo", media, caption, **kw)

    @classmethod
    def video(cls, media, caption=None, **kw):
        return cls("video", media, caption, **kw)

    @classmethod
    def document(cls, media, caption=None, **kw):
        return cls("document", media, caption, **kw)

    @classmethod
    def audio(cls, media, caption=None, **kw):
        return cls("audio", media, caption, **kw)

    def build(self, bot, index, files) -> Dict[str, Any]:
        ref, up = split_file(self.media, "{}{}".format(self.kind, index))
        if up is not None:
            attach = "file{}".format(index)
            files[attach] = up
            media_ref = "attach://" + attach
        else:
            media_ref = ref
        d = {"type": self.kind, "media": media_ref}
        if self.caption is not None:
            d["caption"] = self.caption
            pm = bot._parse(self.parse)
            if pm:
                d["parse_mode"] = pm
        if self.spoiler and self.kind in ("photo", "video"):
            d["has_spoiler"] = True
        return d


class InlineArticle:
    """Результат inline-режима: карточка с заголовком, при выборе отправляет text."""

    def __init__(self, title, text, description=None, id=None, keyboard=None,
                 parse=None, thumb_url=None, url=None):
        self.title = title
        self.text = text
        self.description = description
        self.id = id
        self.keyboard = keyboard
        self.parse = parse
        self.thumb_url = thumb_url
        self.url = url

    def to_dict(self, bot) -> Dict[str, Any]:
        content = {"message_text": str(self.text)}
        pm = bot._parse(self.parse)
        if pm:
            content["parse_mode"] = pm
        d = {"type": "article", "id": str(self.id or uuid.uuid4().hex[:16]),
             "title": str(self.title), "input_message_content": content}
        if self.description:
            d["description"] = self.description
        if self.thumb_url:
            d["thumbnail_url"] = self.thumb_url
        if self.url:
            d["url"] = self.url
        markup = to_markup(self.keyboard)
        if markup:
            d["reply_markup"] = markup
        return d


class InlinePhoto:
    """Результат inline-режима: фото по URL (JPEG, до 5 МБ)."""

    def __init__(self, photo_url, thumb_url=None, title=None, caption=None,
                 id=None, keyboard=None, parse=None):
        self.photo_url = photo_url
        self.thumb_url = thumb_url
        self.title = title
        self.caption = caption
        self.id = id
        self.keyboard = keyboard
        self.parse = parse

    def to_dict(self, bot) -> Dict[str, Any]:
        d = {"type": "photo", "id": str(self.id or uuid.uuid4().hex[:16]),
             "photo_url": self.photo_url, "thumbnail_url": self.thumb_url or self.photo_url}
        if self.title:
            d["title"] = self.title
        if self.caption:
            d["caption"] = self.caption
            pm = bot._parse(self.parse)
            if pm:
                d["parse_mode"] = pm
        markup = to_markup(self.keyboard)
        if markup:
            d["reply_markup"] = markup
        return d
