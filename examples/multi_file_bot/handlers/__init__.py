"""Регистрация обработчиков из отдельных модулей."""

from .post import register as register_post
from .start import register as register_start


def register_handlers(bot, config) -> None:
    register_start(bot)
    register_post(bot, config)
