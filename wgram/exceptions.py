"""Исключения библиотеки wgram."""


class WgramError(Exception):
    """Базовое исключение библиотеки."""


class TelegramAPIError(WgramError):
    """Telegram вернул ok=false.

    Поля:
      description  - текст ошибки от Telegram (поле description из JSON)
      error_code   - числовой код (400, 403, 429 ...)
      retry_after  - сколько секунд ждать при 429 (иначе None)
    """

    def __init__(self, description, error_code=None, retry_after=None, parameters=None):
        self.description = description
        self.error_code = error_code
        self.retry_after = retry_after
        self.parameters = parameters or {}
        if error_code is not None:
            text = "[{}] {}".format(error_code, description)
        else:
            text = str(description)
        super().__init__(text)


class NetworkError(WgramError):
    """Проблемы с сетью: таймаут, обрыв соединения, битый ответ."""
