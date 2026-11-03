import asyncio
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import conftest_stub
conftest_stub.install()

import wgram  # noqa: E402
from wgram.api import Upload  # noqa: E402
from wgram.keyboards import to_markup  # noqa: E402
from wgram.types import Message, Update  # noqa: E402


def msg(text="", chat_type="private", uid=1, username="vasya", **extra):
    d = {"message_id": 10, "date": 1, "chat": {"id": uid, "type": chat_type},
         "from": {"id": uid, "first_name": "Вася", "username": username}}
    if text:
        d["text"] = text
    d.update(extra)
    return d


class FakeAPI:
    """Поддельный Telegram: пишет вызовы и отдаёт заранее заготовленные ответы."""

    def __init__(self, batches):
        self.batches = list(batches)
        self.calls = []
        self.bot = None
        self.mid = 100

    async def call(self, method, params=None, files=None, request_timeout=None):
        params = {k: v for k, v in (params or {}).items() if v is not None}
        self.calls.append((method, params, files))
        if method == "getMe":
            return {"id": 777, "is_bot": True, "first_name": "T", "username": "test_bot"}
        if method == "getUpdates":
            if self.batches:
                return self.batches.pop(0)
            await asyncio.sleep(0.15)          # даём обработчикам доработать
            self.bot.stop()
            return []
        if (method.startswith("send") and method not in ("sendChatAction", "sendMediaGroup")) \
                or method in ("editMessageText", "forwardMessage"):
            self.mid += 1
            return {"message_id": self.mid, "date": 1,
                    "chat": {"id": params.get("chat_id", 1), "type": "private"}, "text": "x"}
        if method == "sendMediaGroup":
            return [{"message_id": 1, "date": 1, "chat": {"id": 1, "type": "private"}}]
        if method == "getChatMember":
            return {"status": "administrator", "user": {"id": 5, "first_name": "A"}}
        return True

    async def get_updates(self, offset=None, timeout=30, allowed_updates=None):
        return await self.call("getUpdates", {"offset": offset, "timeout": timeout,
                                              "allowed_updates": allowed_updates})

    async def download(self, path):
        return b"DATA"

    async def close(self):
        pass

    def names(self):
        return [c[0] for c in self.calls]

    def find(self, method):
        return [c[1] for c in self.calls if c[0] == method]


def make_bot(batches, **kw):
    bot = wgram.start("123:abc", **kw)
    api = FakeAPI(batches)
    api.bot = bot
    bot._api = api
    return bot, api


def upd(n, **kw):
    return dict(update_id=n, **kw)


class KeyboardTests(unittest.TestCase):
    def test_reply_keyboard(self):
        d = wgram.Keyboard(["Да", "Нет"], "Отмена", one_time=True, placeholder="?").to_dict()
        self.assertEqual(d["keyboard"], [[{"text": "Да"}, {"text": "Нет"}], [{"text": "Отмена"}]])
        self.assertTrue(d["one_time_keyboard"] and d["resize_keyboard"])

    def test_special_buttons(self):
        d = wgram.Keyboard([wgram.Button("Тел", contact=True), wgram.Button("Гео", location=True)]).to_dict()
        self.assertEqual(d["keyboard"][0][0]["request_contact"], True)
        self.assertEqual(d["keyboard"][0][1]["request_location"], True)

    def test_grid(self):
        d = wgram.Keyboard.grid(list("abcde"), columns=2).to_dict()
        self.assertEqual([len(r) for r in d["keyboard"]], [2, 2, 1])

    def test_inline_shorthand(self):
        d = wgram.InlineKeyboard([("Да", "yes"), ("Сайт", "https://x.io")]).to_dict()
        row = d["inline_keyboard"][0]
        self.assertEqual(row[0], {"text": "Да", "callback_data": "yes"})
        self.assertEqual(row[1], {"text": "Сайт", "url": "https://x.io"})

    def test_inline_button_variants(self):
        self.assertIn("web_app", wgram.InlineButton("a", web_app="https://x").to_dict())
        self.assertIn("copy_text", wgram.InlineButton("a", copy="X").to_dict())
        self.assertTrue(wgram.InlineButton("a", pay=True).to_dict()["pay"])
        with self.assertRaises(ValueError):
            wgram.InlineButton("a")
        with self.assertRaises(ValueError):
            wgram.InlineButton("a", data="x" * 65)
        with self.assertRaises(ValueError):
            wgram.InlineButton("a", data="1", url="https://x")

    def test_to_markup_inference(self):
        self.assertIn("keyboard", to_markup([["A", "B"]]))
        self.assertIn("keyboard", to_markup(["A", "B"]))
        self.assertIn("inline_keyboard", to_markup([[("A", "a")]]))
        self.assertEqual(to_markup(wgram.RemoveKeyboard()), {"remove_keyboard": True})
        self.assertEqual(to_markup(wgram.ForceReply())["force_reply"], True)
        self.assertIsNone(to_markup(None))
        with self.assertRaises(ValueError):
            wgram.Keyboard()


class ParseTests(unittest.TestCase):
    def test_message_kinds(self):
        photo = Message.from_dict(msg(photo=[{"file_id": "s", "width": 10, "height": 10},
                                              {"file_id": "big", "width": 100, "height": 100}],
                                       caption="подпись"))
        self.assertEqual((photo.kind, photo.photo.file_id, photo.text), ("photo", "big", "подпись"))
        doc = Message.from_dict(msg(document={"file_id": "d", "file_name": "a.pdf"}))
        self.assertEqual((doc.kind, doc.document.file_name), ("document", "a.pdf"))
        gif = Message.from_dict(msg(animation={"file_id": "g"}, document={"file_id": "g"}))
        self.assertEqual(gif.kind, "animation")
        loc = Message.from_dict(msg(location={"latitude": 1.5, "longitude": 2.5}))
        self.assertEqual((loc.kind, loc.location.latitude), ("location", 1.5))
        con = Message.from_dict(msg(contact={"phone_number": "+7", "first_name": "К"}))
        self.assertEqual(con.contact.phone_number, "+7")
        join = Message.from_dict(msg(new_chat_members=[{"id": 9, "first_name": "Н"}]))
        self.assertEqual((join.kind, join.new_members[0].id), ("new_members", 9))
        dice = Message.from_dict(msg(dice={"emoji": "🎲", "value": 6}))
        self.assertEqual(dice.dice.value, 6)

    def test_command_parts(self):
        m = Message.from_dict(msg("/Say@test_bot привет всем"))
        self.assertEqual((m.command, m.args, m.args_list), ("/say", "привет всем", ["привет", "всем"]))
        self.assertEqual(Message.from_dict(msg("/start")).args, "")

    def test_update_kinds(self):
        cb = Update.from_dict(upd(1, callback_query={"id": "c", "from": {"id": 1, "first_name": "a"},
                                                      "data": "yes", "message": msg("hi")}))
        self.assertEqual((cb.kind, cb.obj.data, cb.obj.chat_id), ("callback", "yes", 1))
        self.assertEqual(Update.from_dict(upd(2, message=msg("x"))).kind, "message")
        self.assertEqual(Update.from_dict(upd(3, edited_message=msg("x"))).kind, "edited")
        self.assertIsNone(Update.from_dict(upd(4, something_new={})).kind)
        cm = Update.from_dict(upd(5, my_chat_member={
            "chat": {"id": 1, "type": "private"}, "from": {"id": 1, "first_name": "a"}, "date": 1,
            "old_chat_member": {"status": "member", "user": {"id": 7, "first_name": "b"}},
            "new_chat_member": {"status": "kicked", "user": {"id": 7, "first_name": "b"}}}))
        self.assertTrue(cm.obj.blocked and cm.obj.left and not cm.obj.joined)


class RouterTests(unittest.TestCase):
    def pick(self, bot, text, state=None, **kw):
        m = Message.from_dict(msg(text, **kw), bot)
        rule = bot._router.find("message", m, state)
        return rule.handler.__name__ if rule else None

    def test_priority(self):
        bot = wgram.start("1:a")

        @bot.on()
        def fallback(m): pass

        @bot.on(contains="цена")
        def cont(m): pass

        @bot.on(starts="поиск ")
        def starts(m): pass

        @bot.on(regex=r"^\d+$")
        def number(m): pass

        @bot.on("привет")
        def hello(m): pass

        @bot.on("/start")
        def start(m): pass

        @bot.on_photo()
        def photo(m): pass

        self.assertEqual(self.pick(bot, "/start"), "start")
        self.assertEqual(self.pick(bot, "/START arg"), "start")
        self.assertEqual(self.pick(bot, "привет"), "hello")
        self.assertEqual(self.pick(bot, "42"), "number")
        self.assertEqual(self.pick(bot, "поиск кошки"), "starts")
        self.assertEqual(self.pick(bot, "какая цена?"), "cont")
        self.assertEqual(self.pick(bot, "что-то"), "fallback")
        self.assertEqual(self.pick(bot, "/unknown"), "fallback")
        m = Message.from_dict(msg(photo=[{"file_id": "p", "width": 1, "height": 1}]), bot)
        self.assertEqual(bot._router.find("message", m, None).handler.__name__, "photo")

    def test_other_bot_command_ignored(self):
        bot = wgram.start("1:a")
        bot.me = wgram.User(1, "B", username="test_bot")

        @bot.on("/start")
        def start(m): pass

        self.assertEqual(self.pick(bot, "/start@test_bot"), "start")
        self.assertIsNone(self.pick(bot, "/start@other_bot"))

    def test_state_beats_text_but_not_command(self):
        bot = wgram.start("1:a")

        @bot.on("привет")
        def hello(m): pass

        @bot.on(state="ждём_имя")
        def name(m): pass

        @bot.on("/cancel")
        def cancel(m): pass

        self.assertEqual(self.pick(bot, "привет"), "hello")
        self.assertEqual(self.pick(bot, "привет", state="ждём_имя"), "name")
        self.assertEqual(self.pick(bot, "/cancel", state="ждём_имя"), "cancel")

    def test_filters(self):
        bot = wgram.start("1:a")

        @bot.on("/admin", users=[42, "boss"])
        def admin(m): pass

        @bot.on("/g", chat="group")
        def grp(m): pass

        @bot.on("ПРИВЕТ", ignore_case=True)
        def hi(m): pass

        self.assertIsNone(self.pick(bot, "/admin", uid=1))
        self.assertEqual(self.pick(bot, "/admin", uid=42), "admin")
        self.assertEqual(self.pick(bot, "/admin", uid=5, username="Boss"), "admin")
        self.assertIsNone(self.pick(bot, "/g"))
        self.assertEqual(self.pick(bot, "/g", chat_type="supergroup"), "grp")
        self.assertEqual(self.pick(bot, "привет"), "hi")

    def test_decorator_errors(self):
        bot = wgram.start("1:a")
        with self.assertRaises(ValueError):
            bot.on(kind="photoo")(lambda m: None)
        with self.assertRaises(TypeError):
            bot.on(unknown=1)
        with self.assertRaises(ValueError):
            wgram.start("")  if False else bot.on(chat="nowhere")(lambda m: None)

    def test_buttons(self):
        bot = wgram.start("1:a")

        @bot.on_button("yes")
        def yes(c): pass

        @bot.on_button(prefix="item:")
        def item(c): pass

        @bot.on_button(regex=r"^n:(\d+)$")
        def num(c): pass

        @bot.on_button()
        def other(c): pass

        def find(data):
            cb = wgram.CallbackQuery("i", wgram.User(1, "a"), data)
            r = bot._router.find("callback", cb, None)
            return r.handler.__name__, cb

        self.assertEqual(find("yes")[0], "yes")
        name, cb = find("item:77")
        self.assertEqual((name, cb.arg), ("item", "77"))
        name, cb = find("n:5")
        self.assertEqual((name, cb.match.group(1)), ("num", "5"))
        self.assertEqual(find("zzz")[0], "other")


class BotRunTests(unittest.TestCase):
    def test_sync_handlers_end_to_end(self):
        bot, api = make_bot([[
            upd(1, message=msg("/start")),
            upd(2, message=msg("текст")),
            upd(3, message=msg("другое")),
        ]])

        @bot.on("/start")
        def hello(m):
            m.reply("Привет, это мой бот")

        @bot.on("текст")
        def echo(m):
            m.reply("Ты написал: " + m.text)

        @bot.on()
        def fb(m):
            return "fallback: " + m.text          # возврат строки = ответ

        bot.run()
        texts = sorted(p["text"] for p in api.find("sendMessage"))
        self.assertEqual(texts, sorted(["Ты написал: текст", "fallback: другое", "Привет, это мой бот"]))
        self.assertEqual(api.names()[:3], ["getMe", "deleteWebhook", "getUpdates"])
        self.assertEqual(bot.username, "test_bot")

    def test_offset_advances(self):
        bot, api = make_bot([[upd(5, message=msg("a"))], [upd(6, message=msg("b"))]])

        @bot.on()
        def h(m): pass

        bot.run()
        offsets = [p.get("offset") for p in api.find("getUpdates")]
        self.assertEqual(offsets[:3], [None, 6, 7])
        self.assertEqual(api.find("getUpdates")[0]["timeout"] if "timeout" in api.find("getUpdates")[0] else 30, 30)

    def test_async_handler_and_await_reply(self):
        bot, api = make_bot([[upd(1, message=msg("hi"))]])
        seen = {}

        @bot.on("hi")
        async def h(m):
            sent = await m.reply("a")
            seen["id"] = sent.message_id
            m.reply("b")                           # без await: всё равно отправится

        bot.run()
        self.assertEqual(sorted(p["text"] for p in api.find("sendMessage")), ["a", "b"])
        self.assertTrue(seen["id"] > 100)

    def test_handler_error_does_not_crash_and_on_error_called(self):
        bot, api = make_bot([[upd(1, message=msg("boom")), upd(2, message=msg("ok"))]])
        errors = []

        @bot.on("boom")
        def boom(m):
            raise RuntimeError("упс")

        @bot.on("ok")
        def ok(m):
            m.reply("жив")

        @bot.on_error
        def err(e, obj):
            errors.append((str(e), obj.text))

        bot.run()
        self.assertEqual(errors, [("упс", "boom")])
        self.assertEqual(api.find("sendMessage")[0]["text"], "жив")

    def test_callback_flow_auto_answer_and_edit(self):
        cbq = {"id": "cb1", "from": {"id": 1, "first_name": "a"}, "data": "yes",
               "message": msg("Вопрос?", **{"message_id": 55})}
        cbq2 = dict(cbq, id="cb2", data="no")
        bot, api = make_bot([[upd(1, callback_query=cbq), upd(2, callback_query=cbq2)]])

        @bot.on_button("yes")
        def yes(c):
            c.edit("Выбрано: да")

        @bot.on_button("no")
        def no(c):
            c.answer("Нет!", alert=True)

        bot.run()
        edit = api.find("editMessageText")[0]
        self.assertEqual((edit["chat_id"], edit["message_id"], edit["text"]), (1, 55, "Выбрано: да"))
        answers = {p["callback_query_id"]: p for p in api.find("answerCallbackQuery")}
        self.assertEqual(set(answers), {"cb1", "cb2"})          # cb1 ответили автоматически
        self.assertEqual(answers["cb2"]["text"], "Нет!")
        self.assertTrue(answers["cb2"]["show_alert"])

    def test_state_machine(self):
        bot, api = make_bot([[upd(1, message=msg("/form")), upd(2, message=msg("Вася")),
                              upd(3, message=msg("30"))]])

        @bot.on("/form")
        def form(m):
            m.set_state("name")
            m.reply("Имя?")

        @bot.on(state="name")
        def name(m):
            m.user_data["name"] = m.text
            m.set_state("age")
            m.reply("Возраст?")

        @bot.on(state="age")
        def age(m):
            m.reply("{}, {}".format(m.user_data["name"], m.text))
            m.clear_state()

        bot.run()
        texts = [p["text"] for p in api.find("sendMessage")]
        self.assertEqual(texts, ["Имя?", "Возраст?", "Вася, 30"])       # порядок сохранён
        self.assertIsNone(bot.get_state(1))

    def test_send_with_keyboard_and_options(self):
        bot, api = make_bot([[upd(1, message=msg("k"))]], parse="html")

        @bot.on("k")
        def k(m):
            m.reply("<b>x</b>", keyboard=[("Да", "y")], quote=True, silent=True, preview=False)
            m.reply("plain", parse=False)

        bot.run()
        first, second = api.find("sendMessage")
        self.assertEqual(first["parse_mode"], "HTML")
        self.assertEqual(first["reply_markup"]["inline_keyboard"][0][0]["callback_data"], "y")
        self.assertEqual(first["reply_parameters"]["message_id"], 10)
        self.assertTrue(first["disable_notification"])
        self.assertTrue(first["link_preview_options"]["is_disabled"])
        self.assertNotIn("parse_mode", second)

    def test_long_text_split(self):
        bot, api = make_bot([[upd(1, message=msg("long"))]])

        @bot.on("long")
        def h(m):
            m.reply(("слово " * 1500).strip(), keyboard=["ОК"])

        bot.run()
        calls = api.find("sendMessage")
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(len(c["text"]) <= 4096 for c in calls))
        self.assertNotIn("reply_markup", calls[0])
        self.assertIn("reply_markup", calls[-1])

    def test_media_sending(self):
        bot, api = make_bot([[upd(1, message=msg("m"))]])
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.write(b"PNG"); tmp.close()

        @bot.on("m")
        def h(m):
            m.reply_photo("FILE_ID_123", caption="по id")
            m.reply_photo(tmp.name, caption="с диска")
            m.reply_document(b"bytes!", caption="байты")
            m.reply_media_group([wgram.InputMedia.photo(tmp.name, "a"),
                                 wgram.InputMedia.photo("https://x/y.jpg")])
            m.reply_poll("Q?", ["a", "b"])
            m.reply_poll("Quiz?", ["a", "b"], quiz=True, correct=1)
            m.reply_location(1.0, 2.0)
            m.reply_dice("🎯")
            m.typing()

        bot.run()
        by_id, from_disk = api.find("sendPhoto")
        self.assertEqual(by_id["photo"], "FILE_ID_123")
        calls = [c for c in api.calls if c[0] == "sendPhoto"]
        self.assertIsInstance(calls[1][2]["photo"], Upload)
        self.assertNotIn("photo", calls[1][1])
        self.assertEqual(api.calls[[c[0] for c in api.calls].index("sendDocument")][2]["document"].data, b"bytes!")
        group = api.find("sendMediaGroup")[0]["media"]
        self.assertEqual(group[0]["media"], "attach://file0")
        self.assertEqual(group[1]["media"], "https://x/y.jpg")
        polls = api.find("sendPoll")
        self.assertEqual(polls[0]["options"], [{"text": "a"}, {"text": "b"}])
        self.assertEqual((polls[1]["type"], polls[1]["correct_option_id"]), ("quiz", 1))
        self.assertEqual(api.find("sendDice")[0]["emoji"], "🎯")
        self.assertEqual(api.find("sendChatAction")[0]["action"], "typing")
        os.unlink(tmp.name)

    def test_download_and_receive_photo(self):
        bot, api = make_bot([[upd(1, message=msg(photo=[{"file_id": "F", "width": 5, "height": 5}]))]])
        got = {}

        @bot.on_photo
        def h(m):
            got["bytes"] = m.photo.download()

        orig = api.call

        async def call(method, params=None, files=None, request_timeout=None):
            if method == "getFile":
                api.calls.append((method, params, files))
                return {"file_path": "photos/f.jpg"}
            return await orig(method, params, files, request_timeout)
        api.call = call
        bot.run()
        self.assertEqual(got["bytes"], b"DATA")

    def test_download_to_folder_and_file(self):
        import tempfile
        bot, api = make_bot([])

        async def call(method, params=None, files=None, request_timeout=None):
            return {"file_path": "photos/f.jpg"}
        api.call = call
        with tempfile.TemporaryDirectory() as tmp:
            p1 = bot.download("F", os.path.join(tmp, "new_dir") + "/")      # папки ещё нет
            self.assertEqual(p1, os.path.join(tmp, "new_dir", "f.jpg"))
            self.assertEqual(open(p1, "rb").read(), b"DATA")
            p2 = bot.download("F", os.path.join(tmp, "a", "b.bin"))        # путь к файлу
            self.assertEqual(open(p2, "rb").read(), b"DATA")
            p3 = bot.download("F", tmp)                                    # существующая папка
            self.assertEqual(p3, os.path.join(tmp, "f.jpg"))

    def test_moderation_and_admin_methods(self):
        bot, api = make_bot([[upd(1, message=msg("mod", chat_type="supergroup", uid=-100))]])
        out = {}

        @bot.on("mod")
        def h(m):
            out["admin"] = bot.is_admin(m.chat_id, 5)
            bot.ban(m.chat_id, 7, until=60)
            bot.mute(m.chat_id, 7, seconds=30)
            bot.kick(m.chat_id, 8)
            bot.react(m.chat_id, m.message_id, "🔥")
            bot.set_commands({"start": "Запуск", "/help": "Помощь"})
            m.pin()
            bot.send_invoice(m.chat_id, "Тест", "Описание", "p1", 50)
            bot.delete_messages(m.chat_id, [1, 2])

        bot.run()
        self.assertTrue(out["admin"])
        ban = api.find("banChatMember")
        self.assertIn("until_date", ban[0])
        self.assertEqual(api.find("restrictChatMember")[0]["permissions"], {"can_send_messages": False})
        self.assertEqual(len(ban), 2)                                    # ban + kick
        self.assertEqual(api.find("setMessageReaction")[0]["reaction"], [{"type": "emoji", "emoji": "🔥"}])
        self.assertEqual(api.find("setMyCommands")[0]["commands"][1]["command"], "help")
        inv = api.find("sendInvoice")[0]
        self.assertEqual((inv["currency"], inv["prices"]), ("XTR", [{"label": "Тест", "amount": 50}]))
        self.assertEqual(api.find("deleteMessages")[0]["message_ids"], [1, 2])

    def test_inline_query_and_checkout(self):
        bot, api = make_bot([[
            upd(1, inline_query={"id": "q1", "from": {"id": 1, "first_name": "a"}, "query": "кот", "offset": ""}),
            upd(2, pre_checkout_query={"id": "pc1", "from": {"id": 1, "first_name": "a"},
                                       "currency": "XTR", "total_amount": 50, "invoice_payload": "p1"}),
            upd(3, pre_checkout_query={"id": "pc2", "from": {"id": 2, "first_name": "b"},
                                       "currency": "XTR", "total_amount": 50, "invoice_payload": "bad"}),
        ]])

        @bot.on_inline
        def inl(q):
            q.answer([wgram.InlineArticle("Кот", "Вы искали: " + q.query)])

        @bot.on_checkout
        def pay(c):
            if c.payload == "bad":
                c.error("Товар закончился")
            else:
                c.ok()

        bot.run()
        res = api.find("answerInlineQuery")[0]
        self.assertEqual(res["results"][0]["input_message_content"]["message_text"], "Вы искали: кот")
        checks = {p["pre_checkout_query_id"]: p for p in api.find("answerPreCheckoutQuery")}
        self.assertTrue(checks["pc1"]["ok"])
        self.assertFalse(checks["pc2"]["ok"])

    def test_startup_shutdown_every_stop(self):
        bot, api = make_bot([[upd(1, message=msg("stop"))]])
        log = []

        @bot.on_startup
        def up():
            log.append("up")

        @bot.on_shutdown()
        async def down():
            log.append("down")

        @bot.every(0.05, first_run=True)
        def tick():
            if "tick" not in log:
                log.append("tick")

        @bot.on("stop")
        def h(m):
            log.append("stop-requested")
            bot.stop()

        bot.run()
        self.assertEqual(log[0], "up")
        self.assertIn("tick", log)
        self.assertEqual(log[-1], "down")
        self.assertLessEqual(len(api.find("getUpdates")), 2)

    def test_send_outside_run(self):
        bot, api = make_bot([])
        res = bot.send(555, "из скрипта", keyboard=wgram.RemoveKeyboard())
        self.assertEqual(res.message_id, 101)
        self.assertEqual(api.find("sendMessage")[0]["reply_markup"], {"remove_keyboard": True})
        self.assertTrue(bot.is_admin(1, 5))

    def test_raw_call_and_daily_validation(self):
        bot, api = make_bot([])
        self.assertTrue(bot.call("someNewMethod", a=1))
        self.assertEqual(api.find("someNewMethod")[0], {"a": 1})
        with self.assertRaises(ValueError):
            bot.daily("25:99")
        bot.daily("09:30", days=["mon", "fri"])(lambda: None)
        self.assertEqual(bot._jobs[0][1][1], {0, 4})
        self.assertGreater(bot._seconds_until((9, 30), None), 0)


class UtilsTests(unittest.TestCase):
    def test_utils(self):
        self.assertEqual(wgram.escape_html("<a&b>"), "&lt;a&amp;b&gt;")
        self.assertEqual(wgram.escape_md("a.b_c"), "a\\.b\\_c")
        self.assertIn("tg://user?id=5", wgram.mention(5, "Вася"))
        from wgram.utils import split_text
        parts = split_text("a\n" * 5000, 100)
        self.assertTrue(all(len(p) <= 100 for p in parts))
        self.assertEqual("".join(parts).replace("\n", ""), "a" * 5000)

    def test_token_validation(self):
        with self.assertRaises(ValueError):
            wgram.start("  ")


if __name__ == "__main__":
    unittest.main(verbosity=1)
