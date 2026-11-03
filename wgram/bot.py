"""Класс Bot: обработчики, long polling, диспетчер, отправка и управление чатами."""

import asyncio
import datetime
import inspect
import logging
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from .api import TelegramAPI, split_file
from .exceptions import NetworkError, TelegramAPIError
from .keyboards import to_markup
from .router import Router
from .types import CallbackQuery, Chat, ChatMember, Message, Poll, Update, User
from .utils import normalize_parse, split_text

# Логгер пишет в stderr (стандартное поведение logging)
logger = logging.getLogger("wgram")

POLL_TIMEOUT = 30       # секунд long polling
RETRY_DELAY = 3         # пауза после ошибки сети или API
MAX_TEXT = 4096         # лимит Telegram на длину текста сообщения

ALLOWED_UPDATES = ["message", "edited_message", "channel_post", "edited_channel_post",
                   "callback_query", "inline_query", "poll_answer", "my_chat_member",
                   "chat_member", "pre_checkout_query"]

_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_MSG_OPTS = ("contains", "starts", "regex", "kind", "state", "users", "chat", "ignore_case")


def _is_async(func) -> bool:
    return inspect.iscoroutinefunction(func) or \
        inspect.iscoroutinefunction(getattr(func, "__call__", None))


class Bot:
    def __init__(self, token: str, parse=None, workers: int = 32):
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Нужен токен бота в виде непустой строки")
        self.token = token.strip()
        self.parse_mode = normalize_parse(parse)       # режим форматирования по умолчанию
        self.me: Optional[User] = None                 # заполняется при run()
        self.states: Dict[int, str] = {}               # user_id -> состояние
        self.user_data: Dict[int, Dict[str, Any]] = defaultdict(dict)
        self._api = TelegramAPI(self.token)
        self._router = Router()
        self._workers = workers
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop: Optional[asyncio.Event] = None
        self._tasks = set()                            # ссылки, чтобы задачи не собрал GC
        self._locks: Dict[Any, list] = {}
        self._startup: List[Callable] = []
        self._shutdown: List[Callable] = []
        self._jobs: list = []
        self._error_handler: Optional[Callable] = None

    @property
    def username(self) -> Optional[str]:
        return self.me.username if self.me else None

    # ================================================================ регистрация

    def _clean_opts(self, opts: dict) -> dict:
        bad = [k for k in opts if k not in _MSG_OPTS]
        if bad:
            raise TypeError("Неизвестные параметры фильтра: {}. Доступны: {}".format(
                ", ".join(bad), ", ".join(_MSG_OPTS)))
        return opts

    def _msg_dec(self, target, triggers, opts, **forced):
        opts = self._clean_opts(opts)
        full = dict(opts)
        full.update(forced)
        if len(triggers) == 1 and callable(triggers[0]) and not any(opts.values()):
            func = triggers[0]                    # @bot.on без скобок
            self._router.add_message(target, func, (), **full)
            return func

        def decorator(func):
            self._router.add_message(target, func, triggers, **full)
            return func
        return decorator

    def on(self, *triggers, contains=None, starts=None, regex=None, kind=None,
           state=None, users=None, chat=None, ignore_case=False):
        """Главный декоратор сообщений.

        @bot.on("/start")              команда
        @bot.on("/help", "/помощь")    несколько команд/текстов сразу
        @bot.on("привет")              точный текст
        @bot.on(contains="цена")       текст содержит
        @bot.on(starts="поиск ")       текст начинается с
        @bot.on(regex=r"\\d+")         регулярное выражение (msg.match)
        @bot.on(kind="photo")          вид сообщения
        @bot.on(state="ждём_имя")      пользователь в состоянии
        @bot.on(users=[123, "vasya"])  только эти пользователи
        @bot.on(chat="private")        только личка ('private', 'group', 'channel')
        @bot.on()                      любое сообщение (запасной вариант)
        """
        return self._msg_dec("message", triggers, dict(
            contains=contains, starts=starts, regex=regex, kind=kind, state=state,
            users=users, chat=chat, ignore_case=ignore_case))

    # Простые правила без декораторов и отдельных функций.
    def when(self, text, answer=None):
        """bot.when("/start").say("Привет") или bot.when("привет", "Привет")."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Нужно написать непустую команду или текст")
        from .easy import SimpleRule
        rule = SimpleRule(self, lambda handler: self.on(text, ignore_case=True)(handler))
        return rule.say(answer) if answer is not None else rule

    def when_contains(self, text, answer=None):
        """bot.when_contains("кот").say("Мяу")."""
        if not isinstance(text, str) or not text:
            raise ValueError("Нужно указать непустое слово или фразу")
        from .easy import SimpleRule
        rule = SimpleRule(self, lambda handler: self.on(contains=text, ignore_case=True)(handler))
        return rule.say(answer) if answer is not None else rule

    def when_photo(self, answer=None):
        """bot.when_photo().say("Красивое фото")."""
        from .easy import SimpleRule
        rule = SimpleRule(self, self.on_photo())
        return rule.say(answer) if answer is not None else rule

    def when_file(self, answer=None):
        """bot.when_file().say("Файл получен")."""
        from .easy import SimpleRule
        rule = SimpleRule(self, self.on_document())
        return rule.say(answer) if answer is not None else rule

    def when_video(self, answer=None):
        """bot.when_video().say("Видео получено")."""
        from .easy import SimpleRule
        rule = SimpleRule(self, self.on_video())
        return rule.say(answer) if answer is not None else rule

    def when_voice(self, answer=None):
        """bot.when_voice().say("Голосовое получено")."""
        from .easy import SimpleRule
        rule = SimpleRule(self, self.on_voice())
        return rule.say(answer) if answer is not None else rule

    def when_state(self, state, answer=None):
        """bot.when_state("name").say("Спасибо", clear_state=True)."""
        from .easy import SimpleRule
        rule = SimpleRule(self, self.on(state=state))
        return rule.say(answer) if answer is not None else rule

    def when_button(self, data, answer=None):
        """bot.when_button("yes").say("Ты нажал Да")."""
        from .easy import SimpleButtonRule
        rule = SimpleButtonRule(self.on_button(data))
        return rule.say(answer) if answer is not None else rule

    def on_edit(self, *triggers, **opts):
        """То же, что on(), но для отредактированных сообщений."""
        return self._msg_dec("edited", triggers, opts)

    def on_channel(self, *triggers, **opts):
        """То же, что on(), но для постов в каналах, где бот админ."""
        return self._msg_dec("channel", triggers, opts)

    def _kind_dec(self, kind, args, opts):
        return self._msg_dec("message", args, opts, kind=kind)

    def on_text(self, *a, **kw):        return self._kind_dec("text", a, kw)
    def on_photo(self, *a, **kw):       return self._kind_dec("photo", a, kw)
    def on_document(self, *a, **kw):    return self._kind_dec("document", a, kw)
    def on_video(self, *a, **kw):       return self._kind_dec("video", a, kw)
    def on_audio(self, *a, **kw):       return self._kind_dec("audio", a, kw)
    def on_voice(self, *a, **kw):       return self._kind_dec("voice", a, kw)
    def on_video_note(self, *a, **kw):  return self._kind_dec("video_note", a, kw)
    def on_animation(self, *a, **kw):   return self._kind_dec("animation", a, kw)
    def on_sticker(self, *a, **kw):     return self._kind_dec("sticker", a, kw)
    def on_location(self, *a, **kw):    return self._kind_dec("location", a, kw)
    def on_contact(self, *a, **kw):     return self._kind_dec("contact", a, kw)
    def on_poll(self, *a, **kw):        return self._kind_dec("poll", a, kw)
    def on_dice(self, *a, **kw):        return self._kind_dec("dice", a, kw)
    def on_media(self, *a, **kw):       return self._kind_dec("media", a, kw)
    def on_join(self, *a, **kw):        return self._kind_dec("new_members", a, kw)
    def on_leave(self, *a, **kw):       return self._kind_dec("left_member", a, kw)
    def on_payment(self, *a, **kw):     return self._kind_dec("payment", a, kw)

    def on_button(self, *data, prefix=None, regex=None, state=None, users=None):
        """Нажатие inline-кнопки.

        @bot.on_button("yes")           data == "yes"
        @bot.on_button(prefix="item:")  data начинается с "item:" (остаток в cb.arg)
        @bot.on_button(regex=r"^n:\\d+$")
        @bot.on_button()                любая другая кнопка
        """
        opts = (prefix, regex, state, users)
        if len(data) == 1 and callable(data[0]) and not any(o is not None for o in opts):
            self._router.add_button(data[0])
            return data[0]

        def decorator(func):
            self._router.add_button(func, data, prefix, regex, state, users)
            return func
        return decorator

    def _plain_dec(self, target, args, state=None, users=None):
        if len(args) == 1 and callable(args[0]) and state is None and users is None:
            self._router.add_plain(target, args[0])
            return args[0]

        def decorator(func):
            self._router.add_plain(target, func, state, users)
            return func
        return decorator

    def on_inline(self, *a, **kw):           return self._plain_dec("inline", a, **kw)
    def on_poll_answer(self, *a, **kw):      return self._plain_dec("poll_answer", a, **kw)
    def on_my_chat_member(self, *a, **kw):   return self._plain_dec("my_member", a, **kw)
    def on_chat_member(self, *a, **kw):      return self._plain_dec("member", a, **kw)
    def on_checkout(self, *a, **kw):         return self._plain_dec("checkout", a, **kw)

    # ---------- хуки и задачи по расписанию ----------

    def on_startup(self, func=None):
        """Функция без аргументов, вызывается один раз после старта бота."""
        def decorator(f):
            self._startup.append(f)
            return f
        return decorator(func) if func is not None else decorator

    def on_shutdown(self, func=None):
        """Функция без аргументов, вызывается при остановке бота."""
        def decorator(f):
            self._shutdown.append(f)
            return f
        return decorator(func) if func is not None else decorator

    def on_error(self, func):
        """Функция (error, obj): вызывается, если обработчик упал с исключением.
        obj - то, что обрабатывалось (Message, CallbackQuery...) или None для задач."""
        self._error_handler = func
        return func

    def every(self, seconds, first_run=False):
        """@bot.every(3600) - вызывать функцию (без аргументов) каждые N секунд."""
        if seconds <= 0:
            raise ValueError("seconds должен быть больше нуля")

        def decorator(func):
            self._jobs.append(("every", (seconds, first_run), func))
            return func
        return decorator

    def daily(self, at, days=None):
        """@bot.daily("09:30") - каждый день в 09:30 по времени компьютера.
        days=["mon", "fri"] или [0, 4] - только в эти дни (0 = понедельник)."""
        try:
            hh, mm = [int(x) for x in str(at).split(":")]
            datetime.time(hh, mm)
        except (ValueError, TypeError):
            raise ValueError("Время должно быть в формате 'ЧЧ:ММ', например '09:30'")
        wanted = None
        if days is not None:
            wanted = set()
            for d in days:
                wanted.add(_WEEKDAYS[d.lower()[:3]] if isinstance(d, str) else int(d))

        def decorator(func):
            self._jobs.append(("daily", ((hh, mm), wanted), func))
            return func
        return decorator

    # ---------- состояния и данные пользователей ----------

    def set_state(self, user_id: int, name: str) -> None:
        self.states[user_id] = name

    def get_state(self, user_id: int) -> Optional[str]:
        return self.states.get(user_id)

    def clear_state(self, user_id: int) -> None:
        self.states.pop(user_id, None)

    # ================================================================ запуск

    def run(self, skip_old: bool = False) -> None:
        """Запускает бота и блокирует поток до Ctrl+C.

        skip_old=True - не обрабатывать сообщения, накопленные, пока бот был выключен.
        """
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO,
                                format="%(asctime)s [%(levelname)s] %(message)s")
        try:
            asyncio.run(self._main(skip_old))
        except KeyboardInterrupt:
            pass
        logger.info("wgram: бот остановлен")

    async def run_async(self, skip_old: bool = False) -> None:
        """То же, что run(), но для вызова из своего async-кода (await bot.run_async())."""
        await self._main(skip_old)

    def stop(self) -> None:
        """Останавливает бота (можно вызвать из любого обработчика)."""
        if self._loop is not None and self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)

    async def _main(self, skip_old: bool) -> None:
        loop = asyncio.get_running_loop()
        self._loop = loop
        self._stop = asyncio.Event()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=self._workers,
                                                     thread_name_prefix="wgram"))
        offset: Optional[int] = None
        try:
            # getMe проверяет токен; при сетевых проблемах пробуем снова
            while True:
                try:
                    self.me = User.from_dict(await self._api.call("getMe"))
                    break
                except NetworkError as e:
                    logger.error("Нет связи с Telegram: %s. Повтор через %s с", e, RETRY_DELAY)
                    await asyncio.sleep(RETRY_DELAY)
            # Вебхук мешает getUpdates, поэтому выключаем его
            await self._api.call("deleteWebhook", {"drop_pending_updates": bool(skip_old)})
            logger.info("wgram: бот @%s запущен, для остановки нажмите Ctrl+C", self.me.username)

            for func in self._startup:
                await self._call_plain(func, "startup")
            for kind, args, func in self._jobs:
                self._spawn(self._job_loop(kind, args, func))

            while not self._stop.is_set():
                poll = asyncio.ensure_future(
                    self._api.get_updates(offset, POLL_TIMEOUT, ALLOWED_UPDATES))
                stopper = asyncio.ensure_future(self._stop.wait())
                try:
                    await asyncio.wait({poll, stopper}, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    stopper.cancel()
                    if not poll.done():
                        poll.cancel()
                if not poll.done() or poll.cancelled():
                    break
                try:
                    raw_updates = poll.result()
                except NetworkError as e:
                    logger.error("Сетевая ошибка: %s. Повтор через %s с", e, RETRY_DELAY)
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                except TelegramAPIError as e:
                    logger.error("Ошибка Telegram API: %s", e)
                    if e.error_code in (401, 404):
                        raise                      # неверный токен: повторять бессмысленно
                    await asyncio.sleep(RETRY_DELAY)
                    continue

                for raw in raw_updates:
                    # offset = последний update_id + 1, иначе придут повторно
                    offset = raw["update_id"] + 1
                    try:
                        update = Update.from_dict(raw, bot=self)
                    except Exception:
                        logger.exception("Не удалось разобрать обновление %s", raw.get("update_id"))
                        continue
                    if update.obj is not None:
                        # Каждое обновление в своей задаче: медленный обработчик
                        # не тормозит приём новых сообщений
                        self._spawn(self._dispatch(update))
        finally:
            for task in list(self._tasks):
                task.cancel()
            for func in self._shutdown:
                await self._call_plain(func, "shutdown")
            await self._api.close()
            self._loop = None
            self._stop = None

    # ================================================================ диспетчер

    def _spawn(self, coro, log: bool = True) -> "asyncio.Task":
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        if log:
            def _log(t):
                if not t.cancelled() and t.exception() is not None:
                    logger.error("Необработанная ошибка в задаче", exc_info=t.exception())
            task.add_done_callback(_log)
        return task

    @staticmethod
    def _uid(obj) -> Optional[int]:
        user = getattr(obj, "user", None)
        return user.id if user is not None else None

    async def _dispatch(self, update: Update) -> None:
        """Сообщения одного пользователя обрабатываются по очереди (сохраняется порядок)."""
        obj = update.obj
        key = self._uid(obj)
        if key is None:
            key = getattr(obj, "chat_id", None)
        if key is None:
            await self._process(update)
            return
        entry = self._locks.get(key)
        if entry is None:
            entry = self._locks[key] = [asyncio.Lock(), 0]
        entry[1] += 1
        try:
            async with entry[0]:
                await self._process(update)
        finally:
            entry[1] -= 1
            if entry[1] == 0:
                self._locks.pop(key, None)

    async def _process(self, update: Update) -> None:
        target, obj = update.kind, update.obj
        uid = self._uid(obj)
        state = self.states.get(uid) if uid is not None else None
        rule = self._router.find(target, obj, state)
        ok = True
        try:
            if rule is not None:
                ok = await self._invoke(rule.handler, obj)
        finally:
            if isinstance(obj, CallbackQuery) and not obj._answered:
                obj._answered = True
                await self._quiet(self._api.call("answerCallbackQuery",
                                                 {"callback_query_id": obj.id}))
            elif target == "checkout" and not obj._answered:
                obj._answered = True
                await self._quiet(self._api.call("answerPreCheckoutQuery", {
                    "pre_checkout_query_id": obj.id, "ok": bool(ok),
                    "error_message": None if ok else "Внутренняя ошибка, попробуйте позже"}))

    async def _quiet(self, coro) -> None:
        try:
            await coro
        except Exception as e:
            logger.warning("Не удалось выполнить служебный запрос: %s", e)

    async def _invoke(self, handler: Callable, obj: Any) -> bool:
        """Вызывает обработчик. Ошибки логируются и не роняют бота."""
        try:
            if _is_async(handler):
                result = await handler(obj)
            else:
                # Обычная функция идёт в поток, чтобы msg.reply() мог
                # спокойно ждать ответа, не блокируя event loop
                result = await asyncio.get_running_loop().run_in_executor(None, handler, obj)
            if isinstance(result, str) and result.strip():
                if isinstance(obj, Message):
                    await self._send_text(obj.chat_id, result, thread_id=obj.thread_id)
                elif isinstance(obj, CallbackQuery) and not obj._answered:
                    obj._answered = True
                    await self._api.call("answerCallbackQuery", {
                        "callback_query_id": obj.id, "text": result})
            return True
        except Exception as e:
            logger.exception("Ошибка в обработчике %s", getattr(handler, "__name__", repr(handler)))
            await self._report(e, obj)
            return False

    async def _report(self, error: Exception, obj: Any) -> None:
        if self._error_handler is None:
            return
        try:
            if _is_async(self._error_handler):
                await self._error_handler(error, obj)
            else:
                await asyncio.get_running_loop().run_in_executor(
                    None, self._error_handler, error, obj)
        except Exception:
            logger.exception("Ошибка внутри обработчика on_error")

    async def _call_plain(self, func: Callable, what: str) -> None:
        """Вызывает функцию без аргументов (startup, shutdown, задачи)."""
        try:
            if _is_async(func):
                await func()
            else:
                await asyncio.get_running_loop().run_in_executor(None, func)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Ошибка в функции %s (%s)", getattr(func, "__name__", func), what)
            await self._report(e, None)

    @staticmethod
    def _seconds_until(at, days) -> float:
        now = datetime.datetime.now()
        target = now.replace(hour=at[0], minute=at[1], second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        while days and target.weekday() not in days:
            target += datetime.timedelta(days=1)
        return (target - now).total_seconds()

    async def _job_loop(self, kind, args, func) -> None:
        if kind == "every":
            seconds, first_run = args
            if not first_run:
                await asyncio.sleep(seconds)
            while True:
                await self._call_plain(func, "every")
                await asyncio.sleep(seconds)
        else:
            at, days = args
            while True:
                await asyncio.sleep(self._seconds_until(at, days))
                await self._call_plain(func, "daily")
                await asyncio.sleep(1)           # чтобы не сработать дважды в ту же минуту

    # ================================================================ sync/async мост

    def _run(self, coro):
        """Выполняет корутину и отдаёт результат так, как удобно вызывающему:

        - из обычной функции (рабочий поток)  -> ждёт и возвращает результат
        - из async-обработчика                -> возвращает Task (можно await, можно нет)
        - из скрипта без bot.run()            -> выполняет разово и возвращает результат
        """
        loop = self._loop
        if loop is not None and loop.is_running():
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                running = None
            if running is loop:
                return self._spawn(coro, log=False)
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            async def once():
                try:
                    return await coro
                finally:
                    await self._api.close()
            return asyncio.run(once())
        return asyncio.ensure_future(coro)       # чужой event loop

    async def _exec(self, method, params=None, files=None, wrap=None):
        result = await self._api.call(method, params, files)
        return self._wrap(result, wrap)

    def _wrap(self, result, how):
        if how is None:
            return result
        if how == "message":
            return Message.from_dict(result, self)
        if how == "messages":
            return [Message.from_dict(r, self) for r in result]
        if how == "message_or_true":
            return Message.from_dict(result, self) if isinstance(result, dict) else bool(result)
        if how == "bool":
            return bool(result)
        if how == "chat":
            return Chat.from_dict(result)
        if how == "member":
            return ChatMember.from_dict(result)
        if how == "is_admin":
            return ChatMember.from_dict(result).is_admin
        if how == "members":
            return [ChatMember.from_dict(r) for r in result]
        if how == "user":
            return User.from_dict(result)
        if how == "poll":
            return Poll.from_dict(result)
        if how == "message_id":
            return result["message_id"]
        return result

    def _do(self, method, params=None, files=None, wrap=None):
        return self._run(self._exec(method, params, files, wrap))

    # ================================================================ помощники отправки

    def _parse(self, parse):
        """None -> режим по умолчанию; False/''/'none' -> без форматирования."""
        if parse is None:
            return self.parse_mode
        return normalize_parse(parse)

    def _common(self, keyboard=None, reply_to=None, silent=False, protect=False,
                thread_id=None) -> Dict[str, Any]:
        p: Dict[str, Any] = {}
        markup = to_markup(keyboard)
        if markup is not None:
            p["reply_markup"] = markup
        if reply_to:
            p["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
        if silent:
            p["disable_notification"] = True
        if protect:
            p["protect_content"] = True
        if thread_id:
            p["message_thread_id"] = thread_id
        return p

    @staticmethod
    def _attach(params, files, field, value, default_name):
        ref, upload = split_file(value, default_name)
        if upload is not None:
            files[field] = upload
        else:
            params[field] = ref

    def _send_file(self, method, field, value, default_name, chat_id, caption=None,
                   keyboard=None, parse=None, spoiler=False, thumb=None, reply_to=None,
                   silent=False, protect=False, thread_id=None, params=None, extra=None):
        p = {"chat_id": chat_id}
        p.update(self._common(keyboard, reply_to, silent, protect, thread_id))
        if caption is not None:
            p["caption"] = str(caption)
            pm = self._parse(parse)
            if pm:
                p["parse_mode"] = pm
        if spoiler:
            p["has_spoiler"] = True
        for k, v in (params or {}).items():
            if v is not None:
                p[k] = v
        files: Dict[str, Any] = {}
        self._attach(p, files, field, value, default_name)
        if thumb is not None:
            self._attach(p, files, "thumbnail", thumb, "thumb.jpg")
        p.update(extra or {})
        return self._do(method, p, files, "message")

    # ================================================================ отправка

    async def _send_text(self, chat_id, text, keyboard=None, parse=None, preview=True,
                         reply_to=None, silent=False, protect=False, thread_id=None,
                         extra=None):
        parts = split_text(str(text), MAX_TEXT)
        pm = self._parse(parse)
        result = None
        for i, part in enumerate(parts):
            last = i == len(parts) - 1
            p: Dict[str, Any] = {"chat_id": chat_id, "text": part}
            p.update(self._common(keyboard if last else None, reply_to if i == 0 else None,
                                  silent, protect, thread_id))
            if pm:
                p["parse_mode"] = pm
            if not preview:
                p["link_preview_options"] = {"is_disabled": True}
            p.update(extra or {})
            result = await self._exec("sendMessage", p, None, "message")
        return result

    def send(self, chat_id, text, keyboard=None, parse=None, preview=True, reply_to=None,
             silent=False, protect=False, thread_id=None, **extra):
        """Отправляет текст в любой чат (chat_id или '@канал').

        keyboard   - Keyboard / InlineKeyboard / RemoveKeyboard / ForceReply / список списков
        parse      - 'html', 'md' или False (по умолчанию из wgram.start(parse=...))
        preview    - False отключает превью ссылок
        reply_to   - id сообщения, на которое отвечаем
        silent     - без звука; protect - запретить пересылку
        Тексты длиннее 4096 символов режутся на несколько сообщений.
        Возвращает Message (последнее из отправленных).
        """
        return self._run(self._send_text(chat_id, text, keyboard, parse, preview, reply_to,
                                         silent, protect, thread_id, extra))

    def say(self, chat_id, text, buttons=None, **options):
        """Отправить текст: bot.say(CHAT_ID, "Привет")."""
        return self.send(chat_id, text, keyboard=buttons, **options)

    def picture(self, chat_id, photo, caption=None, buttons=None, **options):
        """Отправить фото: bot.picture(CHAT_ID, "photo.jpg")."""
        return self.send_photo(chat_id, photo, caption=caption, keyboard=buttons, **options)

    def file(self, chat_id, document, caption=None, buttons=None, **options):
        """Отправить документ: bot.file(CHAT_ID, "report.pdf")."""
        return self.send_document(chat_id, document, caption=caption,
                                  keyboard=buttons, **options)

    def send_photo(self, chat_id, photo, caption=None, keyboard=None, parse=None,
                   spoiler=False, reply_to=None, silent=False, protect=False,
                   thread_id=None, **extra):
        """photo: путь к файлу, URL, file_id, bytes или открытый файл ('rb')."""
        return self._send_file("sendPhoto", "photo", photo, "photo.jpg", chat_id, caption,
                               keyboard, parse, spoiler, None, reply_to, silent, protect,
                               thread_id, None, extra)

    def send_document(self, chat_id, document, caption=None, keyboard=None, parse=None,
                      thumb=None, reply_to=None, silent=False, protect=False,
                      thread_id=None, **extra):
        return self._send_file("sendDocument", "document", document, "document", chat_id,
                               caption, keyboard, parse, False, thumb, reply_to, silent,
                               protect, thread_id, None, extra)

    def send_video(self, chat_id, video, caption=None, keyboard=None, parse=None,
                   spoiler=False, duration=None, width=None, height=None, thumb=None,
                   reply_to=None, silent=False, protect=False, thread_id=None, **extra):
        return self._send_file("sendVideo", "video", video, "video.mp4", chat_id, caption,
                               keyboard, parse, spoiler, thumb, reply_to, silent, protect,
                               thread_id, {"duration": duration, "width": width,
                                           "height": height, "supports_streaming": True},
                               extra)

    def send_audio(self, chat_id, audio, caption=None, keyboard=None, parse=None,
                   title=None, performer=None, duration=None, thumb=None, reply_to=None,
                   silent=False, protect=False, thread_id=None, **extra):
        return self._send_file("sendAudio", "audio", audio, "audio.mp3", chat_id, caption,
                               keyboard, parse, False, thumb, reply_to, silent, protect,
                               thread_id, {"title": title, "performer": performer,
                                           "duration": duration}, extra)

    def send_voice(self, chat_id, voice, caption=None, keyboard=None, parse=None,
                   duration=None, reply_to=None, silent=False, protect=False,
                   thread_id=None, **extra):
        """Голосовое сообщение (лучше всего .ogg в кодеке OPUS)."""
        return self._send_file("sendVoice", "voice", voice, "voice.ogg", chat_id, caption,
                               keyboard, parse, False, None, reply_to, silent, protect,
                               thread_id, {"duration": duration}, extra)

    def send_animation(self, chat_id, animation, caption=None, keyboard=None, parse=None,
                       spoiler=False, reply_to=None, silent=False, protect=False,
                       thread_id=None, **extra):
        """GIF или MP4 без звука."""
        return self._send_file("sendAnimation", "animation", animation, "animation.gif",
                               chat_id, caption, keyboard, parse, spoiler, None, reply_to,
                               silent, protect, thread_id, None, extra)

    def send_video_note(self, chat_id, video_note, keyboard=None, duration=None, length=None,
                        reply_to=None, silent=False, protect=False, thread_id=None, **extra):
        """Круглое видео (квадратный MP4 до минуты). По URL отправить нельзя."""
        return self._send_file("sendVideoNote", "video_note", video_note, "note.mp4",
                               chat_id, None, keyboard, None, False, None, reply_to, silent,
                               protect, thread_id, {"duration": duration, "length": length},
                               extra)

    def send_sticker(self, chat_id, sticker, emoji=None, keyboard=None, reply_to=None,
                     silent=False, protect=False, thread_id=None, **extra):
        """sticker: file_id, URL или файл .webp / .tgs / .webm."""
        return self._send_file("sendSticker", "sticker", sticker, "sticker.webp", chat_id,
                               None, keyboard, None, False, None, reply_to, silent, protect,
                               thread_id, {"emoji": emoji}, extra)

    def send_location(self, chat_id, latitude, longitude, live_period=None, keyboard=None,
                      reply_to=None, silent=False, protect=False, thread_id=None, **extra):
        p = {"chat_id": chat_id, "latitude": latitude, "longitude": longitude,
             "live_period": live_period}
        p.update(self._common(keyboard, reply_to, silent, protect, thread_id))
        p.update(extra)
        return self._do("sendLocation", p, None, "message")

    def send_venue(self, chat_id, latitude, longitude, title, address, keyboard=None,
                   reply_to=None, silent=False, protect=False, thread_id=None, **extra):
        p = {"chat_id": chat_id, "latitude": latitude, "longitude": longitude,
             "title": title, "address": address}
        p.update(self._common(keyboard, reply_to, silent, protect, thread_id))
        p.update(extra)
        return self._do("sendVenue", p, None, "message")

    def send_contact(self, chat_id, phone, first_name, last_name=None, keyboard=None,
                     reply_to=None, silent=False, protect=False, thread_id=None, **extra):
        p = {"chat_id": chat_id, "phone_number": phone, "first_name": first_name,
             "last_name": last_name}
        p.update(self._common(keyboard, reply_to, silent, protect, thread_id))
        p.update(extra)
        return self._do("sendContact", p, None, "message")

    def send_poll(self, chat_id, question, options, anonymous=True, multiple=False,
                  quiz=False, correct=None, explanation=None, open_period=None,
                  keyboard=None, reply_to=None, silent=False, protect=False,
                  thread_id=None, **extra):
        """Опрос. options - список строк (2-10 штук).
        Викторина: quiz=True, correct=номер правильного ответа (с нуля), explanation=пояснение."""
        if not 2 <= len(options) <= 10:
            raise ValueError("В опросе должно быть от 2 до 10 вариантов")
        p = {"chat_id": chat_id, "question": question,
             "options": [{"text": str(o)} for o in options],
             "is_anonymous": anonymous, "allows_multiple_answers": multiple or None,
             "explanation": explanation, "open_period": open_period}
        if quiz:
            p["type"] = "quiz"
            p["correct_option_id"] = correct
            p["allows_multiple_answers"] = None
        p.update(self._common(keyboard, reply_to, silent, protect, thread_id))
        p.update(extra)
        return self._do("sendPoll", p, None, "message")

    def stop_poll(self, chat_id, message_id):
        """Закрывает опрос и возвращает итоговый Poll."""
        return self._do("stopPoll", {"chat_id": chat_id, "message_id": message_id},
                        None, "poll")

    def send_dice(self, chat_id, emoji="🎲", keyboard=None, reply_to=None, silent=False,
                  protect=False, thread_id=None, **extra):
        """Анимированный эмодзи со случайным результатом: 🎲 🎯 🏀 ⚽ 🎳 🎰."""
        p = {"chat_id": chat_id, "emoji": emoji}
        p.update(self._common(keyboard, reply_to, silent, protect, thread_id))
        p.update(extra)
        return self._do("sendDice", p, None, "message")

    def send_media_group(self, chat_id, items, reply_to=None, silent=False, protect=False,
                         thread_id=None, **extra):
        """Альбом из 2-10 InputMedia. Возвращает список Message."""
        items = list(items)
        if not 2 <= len(items) <= 10:
            raise ValueError("В альбоме должно быть от 2 до 10 элементов")
        files: Dict[str, Any] = {}
        media = [it.build(self, i, files) for i, it in enumerate(items)]
        p = {"chat_id": chat_id, "media": media}
        p.update(self._common(None, reply_to, silent, protect, thread_id))
        p.update(extra)
        return self._do("sendMediaGroup", p, files, "messages")

    def send_chat_action(self, chat_id, action="typing", thread_id=None):
        """typing, upload_photo, record_video, upload_video, record_voice, upload_voice,
        upload_document, choose_sticker, find_location, record_video_note, upload_video_note."""
        return self._do("sendChatAction", {"chat_id": chat_id, "action": action,
                                           "message_thread_id": thread_id}, None, "bool")

    typing = send_chat_action

    def send_invoice(self, chat_id, title, description, payload, prices, currency="XTR",
                     provider_token=None, photo=None, keyboard=None, reply_to=None,
                     silent=False, protect=False, thread_id=None, **extra):
        """Счёт на оплату.

        Telegram Stars: currency='XTR' (по умолчанию), provider_token не нужен, prices=50
        (или [("Подписка", 50)]).  Обычные валюты: укажите provider_token от @BotFather
        и цены в минимальных единицах (копейки/центы).
        """
        if isinstance(prices, (int, float)):
            prices = [(title, int(prices))]
        p = {"chat_id": chat_id, "title": title, "description": description,
             "payload": payload, "currency": currency,
             "prices": [{"label": str(label), "amount": int(amount)} for label, amount in prices],
             "provider_token": provider_token, "photo_url": photo}
        p.update(self._common(keyboard, reply_to, silent, protect, thread_id))
        p.update(extra)
        return self._do("sendInvoice", p, None, "message")

    def answer_checkout(self, checkout_id, ok=True, error=None):
        return self._do("answerPreCheckoutQuery", {
            "pre_checkout_query_id": checkout_id, "ok": bool(ok),
            "error_message": None if ok else (error or "Оплата невозможна")}, None, "bool")

    # ================================================================ редактирование

    def _target(self, chat_id, message_id, inline_id):
        if inline_id:
            return {"inline_message_id": inline_id}
        return {"chat_id": chat_id, "message_id": message_id}

    def edit_text(self, chat_id, message_id, text, keyboard=None, parse=None, preview=True,
                  inline_id=None, **extra):
        """Меняет текст сообщения бота. Если keyboard не передать, inline-кнопки пропадут."""
        p = self._target(chat_id, message_id, inline_id)
        p["text"] = str(text)
        pm = self._parse(parse)
        if pm:
            p["parse_mode"] = pm
        if not preview:
            p["link_preview_options"] = {"is_disabled": True}
        markup = to_markup(keyboard)
        if markup:
            p["reply_markup"] = markup
        p.update(extra)
        return self._do("editMessageText", p, None, "message_or_true")

    def edit_caption(self, chat_id, message_id, caption, keyboard=None, parse=None,
                     inline_id=None, **extra):
        p = self._target(chat_id, message_id, inline_id)
        p["caption"] = str(caption)
        pm = self._parse(parse)
        if pm:
            p["parse_mode"] = pm
        markup = to_markup(keyboard)
        if markup:
            p["reply_markup"] = markup
        p.update(extra)
        return self._do("editMessageCaption", p, None, "message_or_true")

    def edit_keyboard(self, chat_id, message_id, keyboard=None, inline_id=None):
        """Меняет inline-кнопки под сообщением; keyboard=None убирает их."""
        p = self._target(chat_id, message_id, inline_id)
        markup = to_markup(keyboard)
        if markup:
            p["reply_markup"] = markup
        return self._do("editMessageReplyMarkup", p, None, "message_or_true")

    def delete_message(self, chat_id, message_id):
        return self._do("deleteMessage", {"chat_id": chat_id, "message_id": message_id},
                        None, "bool")

    def delete_messages(self, chat_id, message_ids):
        """Удаляет до 100 сообщений за раз."""
        return self._do("deleteMessages", {"chat_id": chat_id,
                                           "message_ids": list(message_ids)}, None, "bool")

    def forward(self, chat_id, from_chat_id, message_id, silent=False, protect=False,
                thread_id=None):
        """Пересылает сообщение (с пометкой 'Переслано от...')."""
        p = {"chat_id": chat_id, "from_chat_id": from_chat_id, "message_id": message_id}
        p.update(self._common(None, None, silent, protect, thread_id))
        return self._do("forwardMessage", p, None, "message")

    def copy(self, chat_id, from_chat_id, message_id, caption=None, keyboard=None,
             silent=False, protect=False, thread_id=None):
        """Копирует сообщение без пометки об авторе. Возвращает id нового сообщения."""
        p = {"chat_id": chat_id, "from_chat_id": from_chat_id, "message_id": message_id,
             "caption": caption}
        p.update(self._common(keyboard, None, silent, protect, thread_id))
        return self._do("copyMessage", p, None, "message_id")

    def pin(self, chat_id, message_id, silent=True):
        return self._do("pinChatMessage", {"chat_id": chat_id, "message_id": message_id,
                                           "disable_notification": silent}, None, "bool")

    def unpin(self, chat_id, message_id=None):
        return self._do("unpinChatMessage", {"chat_id": chat_id, "message_id": message_id},
                        None, "bool")

    def unpin_all(self, chat_id):
        return self._do("unpinAllChatMessages", {"chat_id": chat_id}, None, "bool")

    def react(self, chat_id, message_id, emoji="👍", big=False):
        """Реакция на сообщение. emoji - строка или список; None снимает реакции."""
        if emoji is None:
            reactions = []
        else:
            items = emoji if isinstance(emoji, (list, tuple)) else [emoji]
            reactions = [{"type": "emoji", "emoji": e} for e in items]
        return self._do("setMessageReaction", {
            "chat_id": chat_id, "message_id": message_id, "reaction": reactions,
            "is_big": big or None}, None, "bool")

    # ================================================================ ответы на запросы

    def answer_callback(self, callback_id, text=None, alert=False, url=None, cache=None):
        return self._do("answerCallbackQuery", {
            "callback_query_id": callback_id, "text": text, "show_alert": alert or None,
            "url": url, "cache_time": cache}, None, "bool")

    def answer_inline(self, inline_id, results, cache=300, personal=False, next_offset=None,
                      button=None):
        """results - список InlineArticle / InlinePhoto / готовых dict."""
        built = [r.to_dict(self) if hasattr(r, "to_dict") else r for r in results]
        return self._do("answerInlineQuery", {
            "inline_query_id": inline_id, "results": built, "cache_time": cache,
            "is_personal": personal or None, "next_offset": next_offset,
            "button": button}, None, "bool")

    # ================================================================ чаты и участники

    def get_me(self):
        return self._do("getMe", None, None, "user")

    def get_chat(self, chat_id):
        return self._do("getChat", {"chat_id": chat_id}, None, "chat")

    def get_member(self, chat_id, user_id):
        """Возвращает ChatMember (status: creator, administrator, member, restricted, left, kicked)."""
        return self._do("getChatMember", {"chat_id": chat_id, "user_id": user_id},
                        None, "member")

    def get_admins(self, chat_id):
        return self._do("getChatAdministrators", {"chat_id": chat_id}, None, "members")

    def member_count(self, chat_id):
        return self._do("getChatMemberCount", {"chat_id": chat_id}, None, None)

    def is_admin(self, chat_id, user_id):
        """True, если пользователь админ или владелец чата."""
        return self._do("getChatMember", {"chat_id": chat_id, "user_id": user_id},
                        None, "is_admin")

    def ban(self, chat_id, user_id, until=None, delete_history=False):
        """Банит участника. until - на сколько секунд (без него - навсегда)."""
        return self._do("banChatMember", {
            "chat_id": chat_id, "user_id": user_id,
            "until_date": int(time.time() + until) if until else None,
            "revoke_messages": delete_history or None}, None, "bool")

    def unban(self, chat_id, user_id):
        return self._do("unbanChatMember", {"chat_id": chat_id, "user_id": user_id,
                                            "only_if_banned": True}, None, "bool")

    def kick(self, chat_id, user_id):
        """Исключает участника, но не банит: он сможет вернуться по ссылке."""
        async def _kick():
            await self._api.call("banChatMember", {"chat_id": chat_id, "user_id": user_id})
            return bool(await self._api.call("unbanChatMember", {
                "chat_id": chat_id, "user_id": user_id, "only_if_banned": True}))
        return self._run(_kick())

    def restrict(self, chat_id, user_id, until=None, **permissions):
        """Ограничивает права: bot.restrict(chat, user, until=3600, can_send_messages=False).
        Все названия can_* - из документации Telegram (ChatPermissions)."""
        return self._do("restrictChatMember", {
            "chat_id": chat_id, "user_id": user_id, "permissions": permissions,
            "until_date": int(time.time() + until) if until else None}, None, "bool")

    def mute(self, chat_id, user_id, seconds=None):
        """Запрещает писать. seconds - на сколько (без него - навсегда)."""
        return self.restrict(chat_id, user_id, until=seconds, can_send_messages=False)

    def unmute(self, chat_id, user_id):
        """Возвращает обычные права участника (писать, отправлять медиа, опросы, ссылки)."""
        return self.restrict(
            chat_id, user_id, can_send_messages=True, can_send_audios=True,
            can_send_documents=True, can_send_photos=True, can_send_videos=True,
            can_send_video_notes=True, can_send_voice_notes=True, can_send_polls=True,
            can_send_other_messages=True, can_add_web_page_previews=True,
            can_invite_users=True)

    def promote(self, chat_id, user_id, **rights):
        """Назначает админом: bot.promote(chat, user, can_delete_messages=True, can_pin_messages=True).
        Без прав (все False) - снимает админа."""
        p = {"chat_id": chat_id, "user_id": user_id}
        p.update(rights)
        return self._do("promoteChatMember", p, None, "bool")

    def set_title(self, chat_id, title):
        return self._do("setChatTitle", {"chat_id": chat_id, "title": title}, None, "bool")

    def set_description(self, chat_id, description):
        return self._do("setChatDescription", {"chat_id": chat_id,
                                               "description": description}, None, "bool")

    def set_chat_photo(self, chat_id, photo):
        p, files = {"chat_id": chat_id}, {}
        self._attach(p, files, "photo", photo, "photo.jpg")
        if "photo" in p:
            raise ValueError("Фото чата нужно загрузить файлом, а не передавать как file_id/URL")
        return self._do("setChatPhoto", p, files, "bool")

    def leave(self, chat_id):
        return self._do("leaveChat", {"chat_id": chat_id}, None, "bool")

    def invite_link(self, chat_id, name=None, limit=None, expire=None, approve=False):
        """Создаёт пригласительную ссылку. expire - через сколько секунд истечёт,
        limit - максимум вступлений, approve - вступление по заявке."""
        res = self._do("createChatInviteLink", {
            "chat_id": chat_id, "name": name, "member_limit": limit,
            "expire_date": int(time.time() + expire) if expire else None,
            "creates_join_request": approve or None}, None, None)
        if isinstance(res, dict):
            return res.get("invite_link")
        return res

    # ================================================================ бот и файлы

    def set_commands(self, commands, language=None):
        """Меню команд бота: bot.set_commands({"start": "Запуск", "help": "Помощь"})
        или [("start", "Запуск"), ("help", "Помощь")]."""
        items = commands.items() if isinstance(commands, dict) else commands
        data = [{"command": str(c).lstrip("/").lower(), "description": str(d)} for c, d in items]
        return self._do("setMyCommands", {"commands": data, "language_code": language},
                        None, "bool")

    def delete_commands(self):
        return self._do("deleteMyCommands", {}, None, "bool")

    def get_file(self, file_id):
        """Информация о файле (file_path, file_size)."""
        return self._do("getFile", {"file_id": file_id}, None, None)

    def download(self, file_id, path=None):
        """Скачивает файл по file_id. Без path вернёт bytes, с path сохранит и вернёт путь.
        Если path - папка, имя файла возьмётся от Telegram. Боты могут скачивать до 20 МБ."""
        return self._run(self._download(file_id, path))

    async def _download(self, file_id, path):
        info = await self._api.call("getFile", {"file_id": file_id})
        data = await self._api.download(info["file_path"])
        if path is None:
            return data
        path = os.fspath(path)
        if path.endswith(("/", os.sep)) or os.path.isdir(path):
            # path - папка: имя файла берём от Telegram
            path = os.path.join(path, os.path.basename(info["file_path"]))
        folder = os.path.dirname(path)

        def write():
            if folder:
                os.makedirs(folder, exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
        await asyncio.get_running_loop().run_in_executor(None, write)
        return path

    def call(self, method, **params):
        """Прямой вызов любого метода Bot API: bot.call("getMyName") -> сырой result.
        Для методов, которых нет в wgram."""
        return self._do(method, params, None, None)
