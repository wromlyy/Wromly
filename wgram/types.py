"""Лёгкие типы данных: User, Chat, Message, CallbackQuery, Update и другие."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

MEDIA_KINDS = ("photo", "animation", "document", "video", "audio", "voice",
               "video_note", "sticker")
ALL_KINDS = ("text", "command") + MEDIA_KINDS + (
    "venue", "location", "contact", "poll", "dice",
    "new_members", "left_member", "payment", "pinned", "other")


def _need(bot):
    if bot is None:
        raise RuntimeError("Объект не привязан к боту (создан вручную, а не через bot.run())")
    return bot


# ============================================================ базовые

@dataclass
class User:
    """Пользователь Telegram."""

    id: int
    first_name: str = ""
    last_name: Optional[str] = None
    username: Optional[str] = None
    is_bot: bool = False
    language_code: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        return cls(
            id=data["id"],
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name"),
            username=data.get("username"),
            is_bot=data.get("is_bot", False),
            language_code=data.get("language_code"),
        )

    @property
    def name(self) -> str:
        """Имя и фамилия одной строкой."""
        return " ".join(p for p in (self.first_name, self.last_name or "") if p)

    @property
    def mention(self) -> str:
        """HTML-упоминание (для parse='html')."""
        from .utils import mention
        return mention(self.id, self.name or self.username or str(self.id))


@dataclass
class Chat:
    """Чат: личный, группа, супергруппа или канал."""

    id: int
    type: str = "private"
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Chat":
        return cls(id=data["id"], type=data.get("type", "private"),
                   title=data.get("title"), username=data.get("username"),
                   first_name=data.get("first_name"), last_name=data.get("last_name"),
                   raw=data)

    @property
    def is_private(self) -> bool:
        return self.type == "private"

    @property
    def is_group(self) -> bool:
        return self.type in ("group", "supergroup")

    @property
    def name(self) -> str:
        return self.title or " ".join(p for p in (self.first_name, self.last_name) if p) \
            or self.username or str(self.id)


@dataclass
class ChatMember:
    """Участник чата и его статус (creator, administrator, member, restricted, left, kicked)."""

    user: User
    status: str
    raw: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMember":
        return cls(user=User.from_dict(data["user"]), status=data.get("status", ""), raw=data)

    @property
    def is_admin(self) -> bool:
        return self.status in ("administrator", "creator")

    @property
    def is_owner(self) -> bool:
        return self.status == "creator"

    @property
    def is_member(self) -> bool:
        return _present(self.status, self.raw)


def _present(status: str, raw: Dict[str, Any]) -> bool:
    if status in ("creator", "administrator", "member"):
        return True
    if status == "restricted":
        return bool(raw.get("is_member", True))
    return False


@dataclass
class Media:
    """Файл из сообщения: фото, документ, видео, аудио, голосовое, стикер и т.д."""

    kind: str
    file_id: str
    file_unique_id: str = ""
    file_size: Optional[int] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    duration: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    title: Optional[str] = None
    performer: Optional[str] = None
    emoji: Optional[str] = None          # у стикера
    set_name: Optional[str] = None       # у стикера
    _bot: Any = field(default=None, repr=False, compare=False)

    @classmethod
    def from_dict(cls, kind: str, data: Any, bot: Any = None) -> "Media":
        if kind == "photo":                       # приходит список размеров: берём самый большой
            data = max(data, key=lambda s: ((s.get("width") or 0) * (s.get("height") or 0),
                                            s.get("file_size") or 0))
        return cls(
            kind=kind, file_id=data["file_id"],
            file_unique_id=data.get("file_unique_id", ""),
            file_size=data.get("file_size"), file_name=data.get("file_name"),
            mime_type=data.get("mime_type"), duration=data.get("duration"),
            width=data.get("width"), height=data.get("height"),
            title=data.get("title"), performer=data.get("performer"),
            emoji=data.get("emoji"), set_name=data.get("set_name"), _bot=bot)

    def download(self, path=None):
        """Скачивает файл. Без path вернёт bytes, с path сохранит и вернёт путь.
        Если path - существующая папка, имя файла возьмётся от Telegram."""
        return _need(self._bot).download(self.file_id, path)


@dataclass
class Location:
    latitude: float
    longitude: float


@dataclass
class Contact:
    phone_number: str
    first_name: str = ""
    last_name: Optional[str] = None
    user_id: Optional[int] = None


@dataclass
class Dice:
    emoji: str
    value: int


@dataclass
class PollOption:
    text: str
    voter_count: int = 0


@dataclass
class Poll:
    id: str
    question: str
    options: List[PollOption] = field(default_factory=list)
    total_voter_count: int = 0
    is_anonymous: bool = True
    type: str = "regular"
    allows_multiple_answers: bool = False
    is_closed: bool = False
    correct_option_id: Optional[int] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Poll":
        return cls(
            id=d.get("id", ""), question=d.get("question", ""),
            options=[PollOption(o.get("text", ""), o.get("voter_count", 0))
                     for o in d.get("options", [])],
            total_voter_count=d.get("total_voter_count", 0),
            is_anonymous=d.get("is_anonymous", True), type=d.get("type", "regular"),
            allows_multiple_answers=d.get("allows_multiple_answers", False),
            is_closed=d.get("is_closed", False),
            correct_option_id=d.get("correct_option_id"))


def _detect_kind(d: Dict[str, Any]) -> str:
    if "text" in d:
        return "command" if d["text"].startswith("/") else "text"
    for key, kind in (("photo", "photo"), ("animation", "animation"), ("document", "document"),
                      ("video", "video"), ("audio", "audio"), ("voice", "voice"),
                      ("video_note", "video_note"), ("sticker", "sticker"),
                      ("venue", "venue"), ("location", "location"), ("contact", "contact"),
                      ("poll", "poll"), ("dice", "dice"),
                      ("new_chat_members", "new_members"), ("left_chat_member", "left_member"),
                      ("successful_payment", "payment"), ("pinned_message", "pinned")):
        if key in d:
            return kind
    return "other"


# ============================================================ Message

@dataclass
class Message:
    """Входящее сообщение."""

    message_id: int
    chat: Chat
    text: str = ""                              # текст или подпись (caption); у остальных ""
    caption: Optional[str] = None
    user: Optional[User] = None                 # у постов канала None
    kind: str = "text"                          # см. ALL_KINDS
    date: Optional[int] = None
    thread_id: Optional[int] = None             # тема форума
    reply_to: Optional["Message"] = None        # сообщение, на которое ответили
    media: Optional[Media] = None
    location: Optional[Location] = None
    contact: Optional[Contact] = None
    poll: Optional[Poll] = None
    dice: Optional[Dice] = None
    new_members: List[User] = field(default_factory=list)
    left_member: Optional[User] = None
    payment: Optional[Dict[str, Any]] = None    # successful_payment
    forwarded: bool = False
    entities: List[Dict[str, Any]] = field(default_factory=list, repr=False)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    match: Any = field(default=None, repr=False, compare=False)   # regex-совпадение
    _bot: Any = field(default=None, repr=False, compare=False)

    @classmethod
    def from_dict(cls, d: Dict[str, Any], bot: Any = None) -> "Message":
        kind = _detect_kind(d)
        sender = d.get("from")
        media = None
        if kind in MEDIA_KINDS:
            media = Media.from_dict(kind, d[kind], bot)
        loc = d.get("location") or (d.get("venue") or {}).get("location")
        contact = d.get("contact")
        reply = d.get("reply_to_message")
        return cls(
            message_id=d["message_id"],
            chat=Chat.from_dict(d["chat"]),
            text=d.get("text") or d.get("caption") or "",
            caption=d.get("caption"),
            user=User.from_dict(sender) if sender else None,
            kind=kind, date=d.get("date"),
            thread_id=d.get("message_thread_id") if d.get("is_topic_message") else None,
            reply_to=cls.from_dict(reply, bot) if reply else None,
            media=media,
            location=Location(loc["latitude"], loc["longitude"]) if loc else None,
            contact=Contact(contact["phone_number"], contact.get("first_name", ""),
                            contact.get("last_name"), contact.get("user_id")) if contact else None,
            poll=Poll.from_dict(d["poll"]) if "poll" in d else None,
            dice=Dice(d["dice"]["emoji"], d["dice"]["value"]) if "dice" in d else None,
            new_members=[User.from_dict(u) for u in d.get("new_chat_members", [])],
            left_member=User.from_dict(d["left_chat_member"]) if "left_chat_member" in d else None,
            payment=d.get("successful_payment"),
            forwarded=("forward_origin" in d or "forward_date" in d),
            entities=d.get("entities") or d.get("caption_entities") or [],
            raw=d, _bot=bot)

    # ---------- удобные свойства ----------

    @property
    def chat_id(self) -> int:
        return self.chat.id

    @property
    def is_private(self) -> bool:
        return self.chat.is_private

    @property
    def is_group(self) -> bool:
        return self.chat.is_group

    @property
    def command(self) -> Optional[str]:
        """'/start' для текста '/start abc' или '/Start@my_bot'. Иначе None.
        Команды, адресованные другому боту (/start@other_bot), игнорируются."""
        t = self.text
        if not t.startswith("/"):
            return None
        first = t.split(None, 1)[0]
        name, _, target = first.partition("@")
        bot = self._bot
        if target and bot is not None and getattr(bot, "username", None) \
                and target.lower() != bot.username.lower():
            return None
        return name.lower()

    @property
    def is_command(self) -> bool:
        return self.command is not None

    @property
    def args(self) -> str:
        """Текст после команды: для '/say привет всем' будет 'привет всем'."""
        if not self.text.startswith("/"):
            return ""
        parts = self.text.split(None, 1)
        return parts[1].strip() if len(parts) > 1 else ""

    @property
    def args_list(self) -> List[str]:
        return self.args.split()

    # типизированные доступы к медиа (None, если сообщение другого вида)
    def _m(self, kind):
        return self.media if self.kind == kind else None

    @property
    def photo(self): return self._m("photo")
    @property
    def document(self): return self._m("document")
    @property
    def video(self): return self._m("video")
    @property
    def audio(self): return self._m("audio")
    @property
    def voice(self): return self._m("voice")
    @property
    def video_note(self): return self._m("video_note")
    @property
    def animation(self): return self._m("animation")
    @property
    def sticker(self): return self._m("sticker")

    # ---------- состояние и данные пользователя ----------

    @property
    def state(self) -> Optional[str]:
        """Текущее состояние пользователя (см. msg.set_state)."""
        return self._bot.get_state(self.user.id) if self._bot and self.user else None

    def set_state(self, name: str) -> None:
        _need(self._bot).set_state(_need(self.user).id, name)

    def clear_state(self) -> None:
        if self._bot and self.user:
            self._bot.clear_state(self.user.id)

    @property
    def user_data(self) -> Dict[str, Any]:
        """Личный словарь пользователя (в памяти): msg.user_data['имя'] = 'Вася'."""
        if self._bot is None or self.user is None:
            return {}
        return self._bot.user_data[self.user.id]

    # ---------- ответы ----------

    def _send(self, method, *args, quote=False, **kw):
        if quote:
            kw["reply_to"] = self.message_id
        if self.thread_id is not None:
            kw.setdefault("thread_id", self.thread_id)
        return getattr(_need(self._bot), method)(self.chat_id, *args, **kw)

    def reply(self, text, keyboard=None, **kw):
        """Отправляет текст в тот же чат. quote=True - ответом на это сообщение.
        Возвращает отправленное Message (в sync-коде) - его можно потом edit()."""
        return self._send("send", text, keyboard=keyboard, **kw)

    def reply_photo(self, photo, caption=None, **kw):
        return self._send("send_photo", photo, caption=caption, **kw)

    def reply_document(self, document, caption=None, **kw):
        return self._send("send_document", document, caption=caption, **kw)

    def reply_video(self, video, caption=None, **kw):
        return self._send("send_video", video, caption=caption, **kw)

    def reply_audio(self, audio, caption=None, **kw):
        return self._send("send_audio", audio, caption=caption, **kw)

    def reply_voice(self, voice, caption=None, **kw):
        return self._send("send_voice", voice, caption=caption, **kw)

    def reply_animation(self, animation, caption=None, **kw):
        return self._send("send_animation", animation, caption=caption, **kw)

    def reply_video_note(self, video_note, **kw):
        return self._send("send_video_note", video_note, **kw)

    def reply_sticker(self, sticker, **kw):
        return self._send("send_sticker", sticker, **kw)

    def reply_location(self, latitude, longitude, **kw):
        return self._send("send_location", latitude, longitude, **kw)

    def reply_venue(self, latitude, longitude, title, address, **kw):
        return self._send("send_venue", latitude, longitude, title, address, **kw)

    def reply_contact(self, phone, first_name, last_name=None, **kw):
        return self._send("send_contact", phone, first_name, last_name=last_name, **kw)

    def reply_poll(self, question, options, **kw):
        return self._send("send_poll", question, options, **kw)

    def reply_dice(self, emoji="🎲", **kw):
        return self._send("send_dice", emoji, **kw)

    def reply_media_group(self, items, **kw):
        return self._send("send_media_group", items, **kw)

    def reply_invoice(self, title, description, payload, prices, **kw):
        return self._send("send_invoice", title, description, payload, prices, **kw)

    def typing(self):
        """Показывает 'печатает...' в чате."""
        return self._send("send_chat_action", "typing")

    def action(self, action="typing"):
        """upload_photo, record_voice, upload_document, find_location, choose_sticker ..."""
        return self._send("send_chat_action", action)

    # ---------- действия над этим сообщением ----------

    def edit(self, text, keyboard=None, **kw):
        """Меняет текст сообщения (только свои сообщения бота). Без keyboard кнопки убираются."""
        return _need(self._bot).edit_text(self.chat_id, self.message_id, text,
                                          keyboard=keyboard, **kw)

    def edit_caption(self, caption, keyboard=None, **kw):
        return _need(self._bot).edit_caption(self.chat_id, self.message_id, caption,
                                             keyboard=keyboard, **kw)

    def edit_keyboard(self, keyboard=None):
        """Меняет inline-кнопки под сообщением; keyboard=None убирает их."""
        return _need(self._bot).edit_keyboard(self.chat_id, self.message_id, keyboard)

    def delete(self):
        return _need(self._bot).delete_message(self.chat_id, self.message_id)

    def forward(self, to_chat_id, **kw):
        return _need(self._bot).forward(to_chat_id, self.chat_id, self.message_id, **kw)

    def copy(self, to_chat_id, **kw):
        return _need(self._bot).copy(to_chat_id, self.chat_id, self.message_id, **kw)

    def pin(self, silent=True):
        return _need(self._bot).pin(self.chat_id, self.message_id, silent=silent)

    def unpin(self):
        return _need(self._bot).unpin(self.chat_id, self.message_id)

    def react(self, emoji="👍", big=False):
        """Ставит реакцию на сообщение; emoji=None снимает."""
        return _need(self._bot).react(self.chat_id, self.message_id, emoji, big=big)

    def download(self, path=None):
        """Скачивает файл этого сообщения (фото, документ, голосовое...)."""
        if self.media is None:
            raise ValueError("В сообщении нет файла (kind={!r})".format(self.kind))
        return self.media.download(path)


# ============================================================ другие обновления

@dataclass
class CallbackQuery:
    """Нажатие на inline-кнопку."""

    id: str
    user: User
    data: str = ""
    message: Optional[Message] = None
    inline_message_id: Optional[str] = None
    match: Any = field(default=None, repr=False, compare=False)    # regex-совпадение
    arg: Optional[str] = None       # остаток data после prefix для on_button(prefix=...)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    _answered: bool = field(default=False, repr=False, compare=False)
    _bot: Any = field(default=None, repr=False, compare=False)

    @classmethod
    def from_dict(cls, d: Dict[str, Any], bot: Any = None) -> "CallbackQuery":
        msg = d.get("message")
        return cls(id=d["id"], user=User.from_dict(d["from"]), data=d.get("data") or "",
                   message=Message.from_dict(msg, bot) if msg else None,
                   inline_message_id=d.get("inline_message_id"), raw=d, _bot=bot)

    @property
    def chat_id(self) -> int:
        return self.message.chat_id if self.message else self.user.id

    @property
    def message_id(self) -> Optional[int]:
        return self.message.message_id if self.message else None

    @property
    def text(self) -> str:
        """Текст сообщения, под которым нажали кнопку."""
        return self.message.text if self.message else ""

    @property
    def state(self) -> Optional[str]:
        return self._bot.get_state(self.user.id) if self._bot else None

    def set_state(self, name):
        _need(self._bot).set_state(self.user.id, name)

    def clear_state(self):
        if self._bot:
            self._bot.clear_state(self.user.id)

    @property
    def user_data(self) -> Dict[str, Any]:
        return self._bot.user_data[self.user.id] if self._bot else {}

    def answer(self, text=None, alert=False, url=None, cache=None):
        """Отвечает на нажатие: всплывающая подсказка (alert=True - окно с OK).
        Если не вызвать, wgram сам ответит пустым ответом, чтобы убрать 'часики'."""
        self._answered = True
        return _need(self._bot).answer_callback(self.id, text=text, alert=alert, url=url,
                                                cache=cache)

    def reply(self, text, keyboard=None, **kw):
        """Новое сообщение в чат, где нажали кнопку."""
        if self.message is not None:
            return self.message.reply(text, keyboard=keyboard, **kw)
        return _need(self._bot).send(self.user.id, text, keyboard=keyboard, **kw)

    def edit(self, text, keyboard=None, **kw):
        """Меняет текст сообщения с кнопкой. Без keyboard кнопки убираются."""
        bot = _need(self._bot)
        if self.message is not None:
            return bot.edit_text(self.chat_id, self.message_id, text, keyboard=keyboard, **kw)
        return bot.edit_text(None, None, text, keyboard=keyboard,
                             inline_id=self.inline_message_id, **kw)

    def edit_caption(self, caption, keyboard=None, **kw):
        bot = _need(self._bot)
        if self.message is not None:
            return bot.edit_caption(self.chat_id, self.message_id, caption,
                                    keyboard=keyboard, **kw)
        return bot.edit_caption(None, None, caption, keyboard=keyboard,
                                inline_id=self.inline_message_id, **kw)

    def edit_keyboard(self, keyboard=None):
        bot = _need(self._bot)
        if self.message is not None:
            return bot.edit_keyboard(self.chat_id, self.message_id, keyboard)
        return bot.edit_keyboard(None, None, keyboard, inline_id=self.inline_message_id)

    def delete(self):
        """Удаляет сообщение, под которым нажали кнопку."""
        if self.message is None:
            raise ValueError("У этого нажатия нет сообщения (inline-режим)")
        return _need(self._bot).delete_message(self.chat_id, self.message_id)


@dataclass
class InlineQuery:
    """Пользователь набрал @имя_бота запрос в любом чате."""

    id: str
    user: User
    query: str = ""
    offset: str = ""
    _bot: Any = field(default=None, repr=False, compare=False)

    @classmethod
    def from_dict(cls, d, bot=None):
        return cls(id=d["id"], user=User.from_dict(d["from"]), query=d.get("query", ""),
                   offset=d.get("offset", ""), _bot=bot)

    def answer(self, results, cache=300, personal=False, next_offset=None, button=None):
        """results: список InlineArticle / InlinePhoto (до 50 штук)."""
        return _need(self._bot).answer_inline(self.id, results, cache=cache,
                                              personal=personal, next_offset=next_offset,
                                              button=button)


@dataclass
class PollAnswer:
    """Кто-то проголосовал в неанонимном опросе."""

    poll_id: str
    user: Optional[User]
    option_ids: List[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d, bot=None):
        u = d.get("user")
        return cls(poll_id=d["poll_id"], user=User.from_dict(u) if u else None,
                   option_ids=d.get("option_ids", []))


@dataclass
class ChatMemberUpdate:
    """Изменился статус участника чата (вступил, вышел, заблокировал бота, повышен...)."""

    chat: Chat
    user: User                      # кто совершил действие
    target: User                    # чей статус изменился
    old_status: str
    new_status: str
    raw: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    _bot: Any = field(default=None, repr=False, compare=False)

    @classmethod
    def from_dict(cls, d, bot=None):
        new = d["new_chat_member"]
        old = d["old_chat_member"]
        return cls(chat=Chat.from_dict(d["chat"]), user=User.from_dict(d["from"]),
                   target=User.from_dict(new["user"]),
                   old_status=old.get("status", ""), new_status=new.get("status", ""),
                   raw=d, _bot=bot)

    @property
    def chat_id(self) -> int:
        return self.chat.id

    @property
    def joined(self) -> bool:
        return (not _present(self.old_status, self.raw.get("old_chat_member", {}))
                and _present(self.new_status, self.raw.get("new_chat_member", {})))

    @property
    def left(self) -> bool:
        return (_present(self.old_status, self.raw.get("old_chat_member", {}))
                and not _present(self.new_status, self.raw.get("new_chat_member", {})))

    @property
    def blocked(self) -> bool:
        """Пользователь заблокировал бота (в личном чате статус 'kicked')."""
        return self.new_status == "kicked"

    def reply(self, text, **kw):
        return _need(self._bot).send(self.chat_id, text, **kw)


@dataclass
class PreCheckoutQuery:
    """Последний шаг перед оплатой: нужно ответить за 10 секунд."""

    id: str
    user: User
    currency: str
    total_amount: int
    payload: str
    _answered: bool = field(default=False, repr=False, compare=False)
    _bot: Any = field(default=None, repr=False, compare=False)

    @classmethod
    def from_dict(cls, d, bot=None):
        return cls(id=d["id"], user=User.from_dict(d["from"]), currency=d.get("currency", ""),
                   total_amount=d.get("total_amount", 0),
                   payload=d.get("invoice_payload", ""), _bot=bot)

    def ok(self):
        self._answered = True
        return _need(self._bot).answer_checkout(self.id, True)

    def error(self, text):
        self._answered = True
        return _need(self._bot).answer_checkout(self.id, False, text)


# ============================================================ Update

@dataclass
class Update:
    """Одно обновление из getUpdates. kind: message, edited, channel, callback,
    inline, poll_answer, my_member, member, checkout (или None, если тип неизвестен)."""

    update_id: int
    kind: Optional[str] = None
    obj: Any = None

    @property
    def message(self) -> Optional[Message]:
        return self.obj if self.kind in ("message", "edited", "channel") else None

    @classmethod
    def from_dict(cls, d: Dict[str, Any], bot: Any = None) -> "Update":
        uid = d["update_id"]
        for key, kind in (("message", "message"), ("edited_message", "edited"),
                          ("channel_post", "channel"), ("edited_channel_post", "edited")):
            if key in d:
                return cls(uid, kind, Message.from_dict(d[key], bot))
        if "callback_query" in d:
            return cls(uid, "callback", CallbackQuery.from_dict(d["callback_query"], bot))
        if "inline_query" in d:
            return cls(uid, "inline", InlineQuery.from_dict(d["inline_query"], bot))
        if "poll_answer" in d:
            return cls(uid, "poll_answer", PollAnswer.from_dict(d["poll_answer"], bot))
        if "my_chat_member" in d:
            return cls(uid, "my_member", ChatMemberUpdate.from_dict(d["my_chat_member"], bot))
        if "chat_member" in d:
            return cls(uid, "member", ChatMemberUpdate.from_dict(d["chat_member"], bot))
        if "pre_checkout_query" in d:
            return cls(uid, "checkout", PreCheckoutQuery.from_dict(d["pre_checkout_query"], bot))
        return cls(uid, None, None)
