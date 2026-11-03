"""Команда /start."""


def register(bot) -> None:
    @bot.on("/start", chat="private")
    def start(message):
        message.reply("Привет! Администратор канала может отправить /post.")
