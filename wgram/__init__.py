"""wgram: максимально простая библиотека для Telegram-ботов."""

from .bot import Bot
from .business import Business
from .easy import buttons, choice, menu
from .exceptions import NetworkError, TelegramAPIError, WgramError
from .inputs import InlineArticle, InlinePhoto, InputMedia
from .keyboards import (Button, ForceReply, InlineButton, InlineKeyboard, Keyboard,
                        RemoveKeyboard)
from .router import ANY_STATE
from .types import (BusinessConnection, BusinessMessagesDeleted, CallbackQuery, Chat,
                    ChatJoinRequest, ChatMember, ChatMemberUpdate, Contact, Dice,
                    InlineQuery, Location, Media, Message, Poll, PollAnswer,
                    PreCheckoutQuery, Update, User)
from .utils import escape_html, escape_md, link, mention, premium_emoji

__all__ = [
    "start", "Bot", "Business", "BusinessConnection", "BusinessMessagesDeleted",
    "ChatJoinRequest", "buttons", "choice", "menu",
    "Keyboard", "Button", "InlineKeyboard", "InlineButton", "RemoveKeyboard", "ForceReply",
    "InputMedia", "InlineArticle", "InlinePhoto", "ANY_STATE",
    "Message", "CallbackQuery", "InlineQuery", "PollAnswer", "ChatMemberUpdate",
    "PreCheckoutQuery", "Update", "User", "Chat", "ChatMember", "Media", "Location",
    "Contact", "Poll", "Dice",
    "escape_html", "escape_md", "mention", "link", "premium_emoji",
    "TelegramAPIError", "NetworkError", "WgramError",
]
__version__ = "0.2.3"


def start(token: str, parse=None) -> Bot:
    """Создаёт бота. Ничего не запускает: запуск делает bot.run().

    parse - форматирование текста по умолчанию: 'html', 'md' или None.
    """
    return Bot(token, parse=parse)
