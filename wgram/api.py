"""Тонкая обёртка над aiohttp для вызова методов Telegram Bot API."""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from .exceptions import NetworkError, TelegramAPIError

logger = logging.getLogger("wgram")


class Upload:
    """Файл для загрузки в Telegram (байты в памяти или путь на диске)."""

    def __init__(self, name, data=None, path=None):
        self.name = name
        self.data = data
        self.path = path

    def load(self):
        if self.data is None and self.path is not None:
            with open(self.path, "rb") as f:
                self.data = f.read()
        return self.data


def split_file(value, default_name="file") -> Tuple[Optional[str], Optional[Upload]]:
    """Определяет, что за файл передан.

    Возвращает (ref, upload):
      ref    - строка для JSON (file_id или URL), если загружать не нужно
      upload - Upload, если файл надо загрузить (путь, байты, открытый файл)
    """
    if isinstance(value, Upload):
        return None, value
    if isinstance(value, (bytes, bytearray)):
        return None, Upload(default_name, data=bytes(value))
    if hasattr(value, "read"):
        data = value.read()
        if isinstance(data, str):
            raise TypeError("Файл нужно открывать в бинарном режиме: open(path, 'rb')")
        name = os.path.basename(getattr(value, "name", "") or "") or default_name
        return None, Upload(name, data=data)
    if isinstance(value, os.PathLike):
        value = os.fspath(value)
    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            return value, None
        if os.path.isfile(value):
            return None, Upload(os.path.basename(value), path=value)
        return value, None                      # считаем, что это file_id
    raise TypeError("Файл: ожидался путь, URL, file_id, bytes или открытый файл, "
                    "а не {!r}".format(type(value).__name__))


def _form_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (dict, list, tuple)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


class TelegramAPI:
    def __init__(self, token: str, base_url: str = "https://api.telegram.org"):
        self._token = token
        self._base = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    def _get_session(self) -> aiohttp.ClientSession:
        # Сессия создаётся лениво, уже внутри работающего event loop
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _hide_token(self, text: str) -> str:
        """Токен не должен попадать в логи и тексты ошибок."""
        return text.replace(self._token, "***")

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None,
                   files: Optional[Dict[str, Upload]] = None,
                   request_timeout: Optional[float] = None) -> Any:
        """Вызывает метод Telegram API и возвращает поле result.

        При ответе 429 (слишком часто) сам ждёт retry_after и повторяет запрос.
        """
        params = {k: v for k, v in (params or {}).items() if v is not None}
        if request_timeout is None:
            request_timeout = 300 if files else 60
        if files:
            loop = asyncio.get_running_loop()
            for up in files.values():
                if up.data is None:
                    await loop.run_in_executor(None, up.load)
        for attempt in range(3):
            try:
                return await self._call_once(method, params, files, request_timeout)
            except TelegramAPIError as e:
                if e.error_code == 429 and e.retry_after and attempt < 2:
                    delay = min(float(e.retry_after), 30.0) + 0.5
                    logger.warning("Telegram просит подождать %s с (429), повтор", delay)
                    await asyncio.sleep(delay)
                    continue
                raise

    async def _call_once(self, method, params, files, request_timeout):
        url = "{}/bot{}/{}".format(self._base, self._token, method)
        timeout = aiohttp.ClientTimeout(total=request_timeout)
        try:
            session = self._get_session()
            if files:
                form = aiohttp.FormData()
                for k, v in params.items():
                    form.add_field(k, _form_value(v))
                for field_name, up in files.items():
                    form.add_field(field_name, up.data, filename=up.name,
                                   content_type="application/octet-stream")
                request = session.post(url, data=form, timeout=timeout)
            else:
                request = session.post(url, json=params, timeout=timeout)
            async with request as resp:
                data = await resp.json(content_type=None)
        except asyncio.TimeoutError as e:
            raise NetworkError("Telegram не ответил вовремя") from e
        except aiohttp.ClientError as e:
            raise NetworkError(
                "Сетевая ошибка: " + self._hide_token(str(e) or e.__class__.__name__)
            ) from None
        except ValueError as e:
            raise NetworkError("Некорректный ответ Telegram: " + self._hide_token(str(e))) from None

        if not isinstance(data, dict) or not data.get("ok"):
            info = data if isinstance(data, dict) else {}
            extra = info.get("parameters") or {}
            raise TelegramAPIError(
                description=info.get("description", "Неизвестная ошибка Telegram"),
                error_code=info.get("error_code"),
                retry_after=extra.get("retry_after"),
                parameters=extra,
            )
        return data.get("result")

    async def get_updates(self, offset: Optional[int] = None, timeout: int = 30,
                          allowed_updates: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Long polling: Telegram держит соединение до timeout секунд."""
        params: Dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        if allowed_updates is not None:
            params["allowed_updates"] = allowed_updates
        return await self.call("getUpdates", params, request_timeout=timeout + 15)

    async def download(self, file_path: str) -> bytes:
        """Скачивает файл по file_path из ответа getFile."""
        url = "{}/file/bot{}/{}".format(self._base, self._token, file_path)
        try:
            timeout = aiohttp.ClientTimeout(total=300)
            async with self._get_session().get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    raise NetworkError("Не удалось скачать файл (HTTP {})".format(resp.status))
                return await resp.read()
        except asyncio.TimeoutError as e:
            raise NetworkError("Скачивание файла: таймаут") from e
        except aiohttp.ClientError as e:
            raise NetworkError(
                "Сетевая ошибка: " + self._hide_token(str(e) or e.__class__.__name__)
            ) from None

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
