"""Точка входа бота: python main.py."""

import wgram

from config import load_config
from handlers import register_handlers


def main() -> None:
    config = load_config()
    bot = wgram.start(config.token, parse="html")
    register_handlers(bot, config)
    bot.run(skip_old=True)


if __name__ == "__main__":
    main()
