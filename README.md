# wgram

Максимально простая библиотека для Telegram-ботов на Python.
Без `async`/`await` на виду, синтаксис почти как псевдокод.

```python
import wgram

bot = wgram.start("ТОКЕН_ОТ_BOTFATHER")

@bot.on("/start")
def hello(msg):
    msg.reply("Привет, это мой бот")

@bot.on("текст")
def echo(msg):
    msg.reply("Ты написал: " + msg.text)

bot.run()
```

Внутри работают `asyncio` и `aiohttp`, но вам про них знать не нужно. Других зависимостей нет.

[Готовый пример бота из нескольких файлов с `.env`](examples/multi_file_bot/README.md).

**Что умеет:** текст и команды, обычные и inline-кнопки, фото/видео/аудио/голосовые/стикеры/GIF/документы
(отправка и приём, скачивание), альбомы, опросы и викторины, кубики, геопозиция, контакты,
состояния (анкеты по шагам), редактирование/удаление/пересылка/реакции/закрепление, управление группами
(бан, мут, админы, ссылки), inline-режим, оплата Telegram Stars, задачи по расписанию,
рассылки из скриптов, любой метод Bot API напрямую.

---

## Содержание

1. [Установка и первый запуск](#1-установка-и-первый-запуск)
2. [Как это работает](#2-как-это-работает)
3. [Обработчики сообщений](#3-обработчики-сообщений)
4. [Объект `msg`](#4-объект-msg)
5. [Отправка текста и форматирование](#5-отправка-текста-и-форматирование)
6. [Кнопки](#6-кнопки)
7. [Медиа: отправка и приём](#7-медиа-отправка-и-приём)
8. [Опросы, кубики, геопозиция, контакты](#8-опросы-кубики-геопозиция-контакты)
9. [Состояния (анкеты по шагам)](#9-состояния-анкеты-по-шагам)
10. [Редактирование, удаление, реакции](#10-редактирование-удаление-реакции)
11. [Группы и модерация](#11-группы-и-модерация)
12. [Inline-режим](#12-inline-режим)
13. [Платежи (Telegram Stars)](#13-платежи-telegram-stars)
14. [Расписание, запуск, остановка, ошибки](#14-расписание-запуск-остановка-ошибки)
15. [Отправка без `bot.run()` (скрипты, рассылки)](#15-отправка-без-botrun-скрипты-рассылки)
16. [`async`-режим](#16-async-режим)
17. [Справочник методов `bot`](#17-справочник-методов-bot)
18. [Ошибки и исключения](#18-ошибки-и-исключения)
19. [Вопросы и ответы](#19-вопросы-и-ответы)

---

## 1. Установка и первый запуск

```bash
pip install wgram
```

Нужен Python 3.8+.

**Получить токен.** Откройте в Telegram [@BotFather](https://t.me/BotFather), отправьте `/newbot`,
придумайте имя. Он выдаст токен вида `123456:ABC-DEF...`. Никому его не показывайте и не выкладывайте в
публичный репозиторий. Лучше хранить в переменной окружения:

```python
import os
import wgram

bot = wgram.start(os.environ["BOT_TOKEN"])
```

**Запуск.** Сохраните код в `main.py` и выполните `python main.py`. Остановка: `Ctrl+C`.
Напишите боту `/start` в Telegram.

Готовые примеры лежат в папке `examples/` (есть в архиве исходников).

---

## 2. Как это работает

1. `wgram.start(token)` создаёт бота и **ничего не запускает**.
2. Декораторы `@bot.on(...)` регистрируют ваши функции-обработчики.
3. `bot.run()` запускает бесконечный цикл получения сообщений (long polling) и **блокирует программу**
   до `Ctrl+C`. Код внутри `@bot.on(...)` вызывается только при совпадении.

Важные правила:

- **На одно сообщение срабатывает один обработчик**, самый подходящий (порядок в разделе 3).
- Обработчик может быть обычной функцией или `async`-функцией, оба варианта работают.
- Если обработчик упал с ошибкой, она печатается в `stderr`, бот продолжает работать.
- Сообщения **одного пользователя** обрабатываются строго по очереди, сообщения разных
  пользователей параллельно.
- Если обработчик **вернул строку**, она отправляется как ответ:

  ```python
  @bot.on("/ping")
  def ping(msg):
      return "pong"          # то же самое, что msg.reply("pong")
  ```

---

## 3. Обработчики сообщений

### Что можно указать в `@bot.on(...)`

| Запись | Когда срабатывает |
|---|---|
| `@bot.on("/start")` | команда `/start` (также `/start арг` и `/start@имя_бота`) |
| `@bot.on("/help", "/помощь")` | любая из перечисленных команд или текстов |
| `@bot.on("привет")` | текст **ровно** «привет» |
| `@bot.on("привет", ignore_case=True)` | то же без учёта регистра |
| `@bot.on(contains="цена")` | текст содержит подстроку (можно списком: `contains=["цена", "купить"]`) |
| `@bot.on(starts="поиск ")` | текст начинается с подстроки |
| `@bot.on(regex=r"\d+")` | регулярное выражение (`re.search`), результат в `msg.match` |
| `@bot.on(kind="photo")` | сообщение определённого вида (раздел 7) |
| `@bot.on(chat="private")` | только личные чаты; также `"group"`, `"channel"` |
| `@bot.on(users=[123, "vasya"])` | только эти пользователи (id или username без `@`) |
| `@bot.on(state="ждём_имя")` | пользователь в этом состоянии (раздел 9) |
| `@bot.on()` | **любое** сообщение (запасной вариант) |

Условия можно комбинировать: `@bot.on("/admin", users=[123], chat="private")`.
Если указано несколько способов сопоставить **текст** (`"привет"`, `contains`, `starts`, `regex`),
достаточно любого. Остальные условия (`kind`, `chat`, `users`, `state`) должны выполниться все.

### Порядок выбора обработчика

1. Точные команды (`"/start"`).
2. Обработчики с `state=...`.
3. Остальные: точный текст → `regex` → `starts` → `contains` → `kind` → `@bot.on()`.

При равном приоритете побеждает тот, что объявлен раньше.

Команда без обработчика (`/неизвестная`) попадёт в `@bot.on()`, если он есть.

### Короткие декораторы по виду сообщения

```python
@bot.on_text        # обычный текст (не команда)
@bot.on_photo       @bot.on_video       @bot.on_audio      @bot.on_voice
@bot.on_document    @bot.on_animation   @bot.on_sticker    @bot.on_video_note
@bot.on_media       # любой файл из списка выше
@bot.on_location    @bot.on_contact     @bot.on_poll       @bot.on_dice
@bot.on_join        # в чат вступили новые участники (msg.new_members)
@bot.on_leave       # участник вышел (msg.left_member)
@bot.on_payment     # успешная оплата (msg.payment)
```

Скобки необязательны (`@bot.on_photo` и `@bot.on_photo()` одно и то же) и принимают те же
фильтры: `@bot.on_photo(chat="private")`.

### Другие события

```python
@bot.on_button("yes")       # нажатие inline-кнопки (раздел 6)
@bot.on_edit("привет")      # сообщение отредактировали (фильтры как у on)
@bot.on_channel()           # пост в канале, где бот админ
@bot.on_inline              # inline-запрос @бот текст (раздел 12)
@bot.on_checkout            # подтверждение оплаты (раздел 13)
@bot.on_poll_answer         # кто-то проголосовал в неанонимном опросе (upd.user, upd.option_ids)
@bot.on_my_chat_member      # бота добавили/удалили/заблокировали (upd.blocked, upd.joined, upd.left)
@bot.on_chat_member         # изменился статус участника (бот должен быть админом)
```

---

## 4. Объект `msg`

### Поля

| Поле | Что это |
|---|---|
| `msg.text` | текст (у фото/видео с подписью это подпись; у остальных `""`) |
| `msg.chat_id` | id чата |
| `msg.chat` | `Chat`: `id`, `type`, `title`, `username`, `name`, `is_private`, `is_group` |
| `msg.user` | `User`: `id`, `first_name`, `last_name`, `username`, `name`, `mention`, `is_bot` (в каналах `None`) |
| `msg.message_id` | id сообщения |
| `msg.kind` | вид: `text`, `command`, `photo`, `document`, `video`, `audio`, `voice`, `video_note`, `animation`, `sticker`, `location`, `venue`, `contact`, `poll`, `dice`, `new_members`, `left_member`, `payment`, `pinned`, `other` |
| `msg.command` | `"/start"` для `/start abc`, иначе `None` |
| `msg.args` / `msg.args_list` | текст после команды: `"привет всем"` / `["привет", "всем"]` |
| `msg.reply_to` | сообщение, на которое ответили (`Message` или `None`) |
| `msg.photo`, `msg.document`, `msg.video`, `msg.audio`, `msg.voice`, `msg.sticker`, `msg.animation`, `msg.video_note` | файл (`Media`) или `None` |
| `msg.location` | `.latitude`, `.longitude` |
| `msg.contact` | `.phone_number`, `.first_name`, `.last_name`, `.user_id` |
| `msg.poll`, `msg.dice` | опрос / кубик (`dice.emoji`, `dice.value`) |
| `msg.new_members` / `msg.left_member` | участники, вступившие / вышедший |
| `msg.forwarded`, `msg.date`, `msg.thread_id` | пересланное / время (unix) / тема форума |
| `msg.match` | результат `regex`, если сработал `@bot.on(regex=...)` |
| `msg.raw` | исходный словарь от Telegram, если нужно поле, которого нет выше |

`Media` (файл): `file_id`, `file_size`, `file_name`, `mime_type`, `duration`, `width`, `height`,
`title`, `performer`, `emoji`, метод `download()`.

### Методы

Все методы-ответы принимают одни и те же необязательные параметры:
`keyboard=`, `parse=`, `quote=True` (ответить цитатой), `silent=True` (без звука),
`protect=True` (запретить пересылку).

```python
msg.reply("текст")                          msg.reply_photo(photo, caption="...")
msg.reply_document(file)                    msg.reply_video(file)
msg.reply_audio(file)                       msg.reply_voice(file)
msg.reply_animation(file)                   msg.reply_video_note(file)
msg.reply_sticker(file_id)                  msg.reply_location(lat, lon)
msg.reply_venue(lat, lon, "Название", "Адрес")
msg.reply_contact("+79990001122", "Имя")    msg.reply_poll("Вопрос?", ["а", "б"])
msg.reply_dice("🎲")                        msg.reply_media_group([...])
msg.reply_invoice(...)                      # раздел 13
msg.typing()                                # «печатает…»
msg.action("upload_photo")                  # другие статусы

msg.edit("новый текст")      msg.edit_caption("...")     msg.edit_keyboard(kb)
msg.delete()                 msg.forward(chat_id)        msg.copy(chat_id)
msg.pin()                    msg.unpin()                 msg.react("👍")
msg.download("папка/")       # скачать файл сообщения

msg.set_state("имя")         msg.clear_state()           msg.state
msg.user_data                # личный словарь пользователя
```

`msg.reply(...)` в обычной функции **возвращает отправленное сообщение**, его можно потом изменить:

```python
sent = msg.reply("Считаю...")
sent.edit("Готово: 42")
```

---

## 5. Отправка текста и форматирование

```python
msg.reply("Обычный текст")
bot.send(chat_id, "Сообщение в любой чат")    # chat_id или "@имя_канала"
```

Параметры `send`/`reply`: `keyboard`, `parse`, `preview`, `reply_to`, `silent`, `protect`, `thread_id`.

**Форматирование.** Включите режим один раз при создании бота или для одного сообщения:

```python
bot = wgram.start(token, parse="html")        # для всех сообщений
msg.reply("<b>жирный</b> <i>курсив</i> <code>код</code> <a href='https://x.com'>ссылка</a>")
msg.reply("без форматирования <b>", parse=False)   # отключить для одного сообщения
```

Если в текст попадают данные пользователей, **экранируйте** их:

```python
text = "Привет, " + wgram.escape_html(msg.text)       # для html
text = "Привет, " + wgram.escape_md(msg.text)         # для parse="md" (MarkdownV2)
wgram.mention(msg.user.id, "Вася")                    # упоминание пользователя (html)
msg.user.mention                                      # то же для автора сообщения
wgram.link("https://example.com", "сайт")             # html-ссылка
```

- `preview=False` отключает превью ссылок.
- Текст длиннее 4096 символов автоматически режется на несколько сообщений (кнопки прикрепляются к последнему).

---

## 6. Кнопки

### 6.1 Обычная клавиатура (под полем ввода)

Нажатие на кнопку просто **отправляет её текст** как сообщение, поэтому ловите его через `@bot.on("Текст кнопки")`.

```python
kb = wgram.Keyboard(["Да", "Нет"], ["Отмена"])
msg.reply("Выбери:", keyboard=kb)
```

**Правило:** `list` = одна строка кнопок, всё остальное = строка из одной кнопки.

```python
wgram.Keyboard(["Да", "Нет"], ["Отмена"])     # 2 строки: [Да][Нет] / [Отмена]
wgram.Keyboard("Да", "Нет")                   # 2 строки по одной кнопке
wgram.Keyboard.grid(["1", "2", "3", "4", "5"], columns=3)   # сетка 3+2
```

Параметры: `resize=True`, `one_time=True` (скрыть после нажатия), `placeholder="..."` (подсказка в поле ввода),
`persistent=True` (не сворачивать).

Особые кнопки:

```python
wgram.Button("Отправить номер", contact=True)     # придёт msg.contact (@bot.on_contact)
wgram.Button("Где я?", location=True)             # придёт msg.location (@bot.on_location)
wgram.Button("Создать опрос", poll=True)          # poll="quiz" - викторина
wgram.Button("Приложение", web_app="https://...") # мини-приложение
```

Убрать клавиатуру и принудительный ответ:

```python
msg.reply("Готово", keyboard=wgram.RemoveKeyboard())
msg.reply("Напиши имя:", keyboard=wgram.ForceReply(placeholder="Имя"))
```

Для быстрого старта можно передать обычный список списков: `keyboard=[["Да", "Нет"], ["Отмена"]]`.

### 6.2 Inline-кнопки (под сообщением)

```python
kb = wgram.InlineKeyboard(
    [("Да", "yes"), ("Нет", "no")],                  # (текст, data)
    [("Сайт", "https://example.com")],               # (текст, ссылка) - если начинается с http(s):// или tg://
)
msg.reply("Тебе нравится?", keyboard=kb)
```

Полная форма кнопки с одним из действий:

```python
wgram.InlineButton("Да", data="yes")                      # нажатие -> @bot.on_button("yes")
wgram.InlineButton("Сайт", url="https://example.com")
wgram.InlineButton("Открыть", web_app="https://...")      # мини-приложение
wgram.InlineButton("Поделиться", switch="текст")          # выбор чата + inline-режим
wgram.InlineButton("Искать тут", switch_here="кот")       # inline-режим в текущем чате
wgram.InlineButton("Скопировать", copy="PROMO2026")       # копирует текст в буфер
wgram.InlineButton("Оплатить", pay=True)                  # для счетов (раздел 13)
```

`data` не длиннее 64 байт (библиотека проверит и скажет, если больше).
Сетка: `wgram.InlineKeyboard.grid([("1", "n:1"), ("2", "n:2"), ("3", "n:3")], columns=2)`.

### 6.3 Обработка нажатий

```python
@bot.on_button("yes")                # data == "yes"
def yes(cb):
    cb.answer("Спасибо!")            # всплывающая подсказка
    cb.edit("Ты ответил: Да")        # заменить текст сообщения с кнопками

@bot.on_button(prefix="item:")       # data начинается с "item:", остаток в cb.arg
def item(cb):
    cb.answer("Товар №" + cb.arg)

@bot.on_button(regex=r"^page:(\d+)$")    # cb.match.group(1)
def page(cb): ...

@bot.on_button()                     # все остальные кнопки
def other(cb): ...
```

Объект `cb` (`CallbackQuery`):

| | |
|---|---|
| `cb.data` | данные кнопки |
| `cb.user` | кто нажал |
| `cb.message` | сообщение с кнопками (`Message`); `cb.text`, `cb.chat_id`, `cb.message_id` |
| `cb.answer(text=None, alert=False, url=None)` | ответить на нажатие; `alert=True` показывает окно с OK |
| `cb.edit(text, keyboard=None)` | изменить текст (без `keyboard` кнопки пропадут: передайте их снова, чтобы оставить) |
| `cb.edit_keyboard(kb)` | изменить только кнопки (`None` убирает их) |
| `cb.edit_caption(text)` | изменить подпись у фото/видео |
| `cb.delete()` | удалить сообщение с кнопкой |
| `cb.reply("текст")` | новое сообщение в тот же чат |
| `cb.set_state(...)`, `cb.clear_state()`, `cb.user_data` | как у `msg` |

Если вы не вызвали `cb.answer()`, wgram сам ответит пустым ответом, чтобы у кнопки не крутились «часики».
Если обработчик кнопки **вернёт строку**, она покажется как всплывающая подсказка.

---

## 7. Медиа: отправка и приём

### Отправка

```python
msg.reply_photo("cat.jpg", caption="Кот")
msg.reply_document("report.pdf")
msg.reply_video("clip.mp4", caption="Видео")
msg.reply_audio("song.mp3", title="Песня", performer="Группа")
msg.reply_voice("voice.ogg")             # голосовое (лучше .ogg, кодек OPUS)
msg.reply_animation("funny.gif")
msg.reply_video_note("round.mp4")        # круглое видео
msg.reply_sticker("CAACAgIAAxkB...")     # file_id или файл .webp/.tgs/.webm
```

В качестве файла подойдёт любое из:

| Что передать | Пример |
|---|---|
| путь к файлу на диске | `"photos/cat.jpg"` |
| URL | `"https://example.com/cat.jpg"` (Telegram сам скачает) |
| `file_id` | `"AgACAgIAAxkBAA..."` (уже загруженный файл, самый быстрый вариант) |
| байты | `open("a.jpg","rb").read()` или `io.BytesIO(...).getvalue()` |
| открытый файл | `open("cat.jpg", "rb")` |

Дополнительно: `spoiler=True` (скрыть под спойлер, для фото/видео/GIF), `thumb="preview.jpg"`
(превью для документа/видео/аудио), `keyboard=`, `caption=`, `parse=`.

Статус «отправляет фото…»: `msg.action("upload_photo")`, перед долгой отправкой.

**Альбом** (2–10 файлов; фото и видео можно смешивать):

```python
msg.reply_media_group([
    wgram.InputMedia.photo("a.jpg", caption="Подпись альбома"),
    wgram.InputMedia.photo("b.jpg"),
    wgram.InputMedia.video("https://example.com/c.mp4"),
])
```

### Приём

```python
@bot.on_photo
def got_photo(msg):
    path = msg.download("downloads/")      # папка; имя файла возьмётся от Telegram
    msg.reply("Размер: {}x{}".format(msg.photo.width, msg.photo.height))

@bot.on_document
def got_doc(msg):
    data = msg.download()                  # без пути вернёт bytes
    msg.reply("{}: {} байт".format(msg.document.file_name, len(data)))

@bot.on_voice
def got_voice(msg):
    msg.reply("Длина: {} с".format(msg.voice.duration))

@bot.on_sticker
def got_sticker(msg):
    msg.reply(msg.sticker.emoji or "стикер")
```

- Для фото в `msg.photo` берётся **самый большой** размер.
- `msg.download(путь)`: если путь заканчивается на `/` или это существующая папка, файл сохранится
  внутрь с именем от Telegram (папка создастся сама); иначе путь считается именем файла. Возвращает итоговый путь.
- Боты могут скачивать файлы **до 20 МБ** (ограничение Telegram).
- Чтобы переслать файл дальше, используйте `file_id`: `bot.send_photo(other_chat, msg.photo.file_id)`.

---

## 8. Опросы, кубики, геопозиция, контакты

```python
msg.reply_poll("Любимый язык?", ["Python", "Rust", "Go"])                  # анонимный
msg.reply_poll("Любимый язык?", ["Python", "Rust"], anonymous=False,       # неанонимный,
               multiple=True)                                              # можно несколько
msg.reply_poll("2 + 2 = ?", ["3", "4", "5"], quiz=True, correct=1,         # викторина:
               explanation="Это арифметика")                               # correct - номер с нуля
bot.stop_poll(chat_id, message_id)                                         # закрыть, вернёт Poll

msg.reply_dice("🎲")      # 🎲 🎯 🏀 ⚽ 🎳 🎰 : результат придёт пользователю случайный
msg.reply_location(55.7558, 37.6173)
msg.reply_venue(55.7558, 37.6173, "Красная площадь", "Москва")
msg.reply_contact("+79990001122", "Иван", last_name="Иванов")
```

Результат бросков кубика бот видит у пользователя: `@bot.on_dice` → `msg.dice.value`.
Голосование в неанонимном опросе: `@bot.on_poll_answer` → `upd.user`, `upd.option_ids`.

---

## 9. Состояния (анкеты по шагам)

Состояние это «пометка» о том, на каком шаге диалога находится пользователь. Так делаются анкеты, заказы, регистрации.

```python
@bot.on("/form")
def form(msg):
    msg.set_state("name")
    msg.reply("Как тебя зовут?")

@bot.on(state="name")                      # сработает, только если состояние "name"
def got_name(msg):
    msg.user_data["name"] = msg.text       # личный словарь пользователя
    msg.set_state("age")
    msg.reply("Сколько лет?")

@bot.on(state="age")
def got_age(msg):
    if not msg.text.isdigit():
        return "Нужно число, попробуй ещё раз"
    msg.reply("{}, {} лет. Спасибо!".format(msg.user_data["name"], msg.text))
    msg.clear_state()

@bot.on("/cancel")                         # команды сильнее состояний: работают всегда
def cancel(msg):
    msg.clear_state()
    msg.reply("Отменено")
```

- `state="a"`, `state=["a", "b"]` или `state=wgram.ANY_STATE` (любое состояние).
- Состояния и `user_data` привязаны к **id пользователя** и хранятся **в памяти**. После перезапуска бота
  они пропадут. Для постоянного хранения сохраняйте данные в файл или базу сами.
- Работает и в обработчиках кнопок: `cb.set_state(...)`, `cb.user_data`.
- Вне обработчика: `bot.set_state(user_id, "x")`, `bot.get_state(user_id)`, `bot.clear_state(user_id)`, `bot.user_data[user_id]`.

---

## 10. Редактирование, удаление, реакции

```python
sent = msg.reply("Загрузка...")
sent.edit("Готово!", keyboard=kb)        # изменить текст (только сообщения самого бота)
sent.edit_caption("Новая подпись")
sent.edit_keyboard(None)                 # убрать кнопки
sent.delete()

msg.forward(other_chat_id)               # с пометкой «Переслано от...»
msg.copy(other_chat_id)                  # без пометки (вернёт id нового сообщения)
msg.pin()   msg.unpin()                  # закрепить (бот должен быть админом в группе)
msg.react("🔥")                          # реакция на сообщение; msg.react(None) - снять

bot.delete_messages(chat_id, [1, 2, 3])  # до 100 сообщений
bot.unpin_all(chat_id)
```

Те же действия есть у `bot` с явными id: `bot.edit_text(chat_id, message_id, "текст")`,
`bot.delete_message(chat_id, message_id)`, `bot.react(chat_id, message_id, "👍")`.

Telegram позволяет боту удалять свои сообщения без ограничений, а чужие в группе только если он админ с правом удаления.

---

## 11. Группы и модерация

Добавьте бота в группу и сделайте администратором с нужными правами. У @BotFather командой `/setprivacy`
можно отключить «режим приватности», иначе в группе бот видит только команды и ответы на свои сообщения.

```python
@bot.on_join
def welcome(msg):
    for u in msg.new_members:
        msg.reply("Добро пожаловать, {}!".format(u.mention))     # при parse="html"

@bot.on("/ban", chat="group")
def ban(msg):
    if not bot.is_admin(msg.chat_id, msg.user.id):
        return "Только для админов"
    if msg.reply_to is None:
        return "Ответьте командой на сообщение нарушителя"
    bot.ban(msg.chat_id, msg.reply_to.user.id)
    return "Забанен"
```

| Метод | Что делает |
|---|---|
| `bot.is_admin(chat_id, user_id)` | `True`, если админ или владелец |
| `bot.get_member(chat_id, user_id)` | `ChatMember`: `.status`, `.is_admin`, `.is_owner`, `.is_member`, `.user` |
| `bot.get_admins(chat_id)` / `bot.member_count(chat_id)` / `bot.get_chat(chat_id)` | список админов / число участников / информация о чате |
| `bot.ban(chat_id, user_id, until=секунды, delete_history=False)` | бан (без `until` навсегда) |
| `bot.unban(chat_id, user_id)` | разбан |
| `bot.kick(chat_id, user_id)` | исключить без бана (сможет вернуться) |
| `bot.mute(chat_id, user_id, seconds=None)` / `bot.unmute(...)` | запретить / разрешить писать |
| `bot.restrict(chat_id, user_id, until=..., can_send_photos=False, ...)` | тонкие ограничения (названия `can_*` из документации Telegram) |
| `bot.promote(chat_id, user_id, can_delete_messages=True, ...)` | назначить админом (все права `False` снимают админа) |
| `bot.set_title(...)`, `bot.set_description(...)`, `bot.set_chat_photo(chat_id, "a.jpg")` | настройки чата |
| `bot.invite_link(chat_id, limit=10, expire=3600)` | пригласительная ссылка |
| `bot.leave(chat_id)` | выйти из чата |

Узнать, что бота добавили, удалили или заблокировали:

```python
@bot.on_my_chat_member
def changed(upd):
    if upd.blocked:        # пользователь заблокировал бота в личке
        forget_user(upd.chat_id)
    elif upd.joined:       # бота добавили в чат
        bot.send(upd.chat_id, "Всем привет!")
```

---

## 12. Inline-режим

Пользователь пишет `@имя_бота запрос` в **любом** чате и выбирает результат. Включите режим у
@BotFather: `/setinline`.

```python
@bot.on_inline
def search(q):                  # q.query - что набрал пользователь
    text = q.query or "привет"
    q.answer([
        wgram.InlineArticle("Крупно", text.upper(), description="ЗАГЛАВНЫМИ"),
        wgram.InlineArticle("Мелко", text.lower()),
        wgram.InlinePhoto("https://example.com/cat.jpg", title="Кот"),
    ], cache=10)
```

- `InlineArticle(title, text, description=None, keyboard=None, parse=None, thumb_url=None)`: карточка, при выборе отправляется `text`.
- `InlinePhoto(photo_url, thumb_url=None, title=None, caption=None)`: фото по URL (JPEG до 5 МБ).
- `q.answer(results, cache=300, personal=False, next_offset=None)`: максимум 50 результатов за раз.

---

## 13. Платежи (Telegram Stars)

Оплата цифровых товаров звёздами не требует подключения платёжного провайдера.

```python
@bot.on("/buy")
def buy(msg):
    msg.reply_invoice(
        "Премиум на месяц", "Доступ ко всем функциям", "premium_month",   # заголовок, описание, payload
        50,                                                                # цена в звёздах
        keyboard=wgram.InlineKeyboard([wgram.InlineButton("Оплатить 50 ⭐", pay=True)]),
    )

@bot.on_checkout                # на ответ даётся 10 секунд
def checkout(c):                # c.payload, c.total_amount, c.currency, c.user
    if c.payload == "premium_month":
        c.ok()
    else:
        c.error("Такого товара нет")

@bot.on_payment                 # деньги получены
def paid(msg):
    msg.reply("Спасибо! Выдан: " + msg.payment["invoice_payload"])
```

- Цена можно задать списком: `[("Подписка", 40), ("Бонус", 10)]`.
- Если `@bot.on_checkout` не ответил, wgram подтвердит оплату сам (а при ошибке в обработчике отклонит).
- Для обычных валют укажите `currency="RUB"`, `provider_token="токен_провайдера_от_BotFather"` и цены в **копейках**.
- Возврат звёзд и прочие методы доступны через `bot.call("refundStarPayment", user_id=..., telegram_payment_charge_id=...)`.

---

## 14. Расписание, запуск, остановка, ошибки

```python
@bot.on_startup                 # один раз после запуска (функция без аргументов)
def started():
    bot.set_commands({"start": "Запуск", "help": "Помощь"})     # меню команд бота
    bot.send(ADMIN_ID, "Бот запущен")

@bot.on_shutdown                # при остановке
def stopped():
    bot.send(ADMIN_ID, "Бот остановлен")

@bot.every(3600)                # каждый час (first_run=True - ещё и сразу при старте)
def hourly():
    cleanup()

@bot.daily("09:00", days=["mon", "tue", "wed", "thu", "fri"])    # по будням в 9:00 (время компьютера)
def morning():
    for chat_id in subscribers:
        bot.send(chat_id, "Доброе утро!")

@bot.on_error                   # любая ошибка в обработчиках и задачах
def handle(error, obj):         # obj - Message / CallbackQuery / ... или None для задач
    bot.send(ADMIN_ID, "Ошибка: {!r}".format(error))
```

- `bot.run(skip_old=True)` не обрабатывает сообщения, накопившиеся, пока бот был выключен.
- `bot.stop()` останавливает бота из любого обработчика.
- Ошибки сети и временные ошибки Telegram переживаются автоматически (повтор через 3 секунды). При `429 Too Many Requests` wgram сам ждёт и повторяет запрос.
- Логи идут в `stderr`. Настроить уровень и формат можно стандартным `logging` до `bot.run()`:
  `logging.basicConfig(level=logging.DEBUG)`.

---

## 15. Отправка без `bot.run()` (скрипты, рассылки)

Все методы `bot.*` работают и в обычном скрипте, без запуска приёма сообщений:

```python
import wgram

bot = wgram.start("ТОКЕН")
bot.send(123456789, "Привет из скрипта!")
bot.send_photo("@my_channel", "poster.jpg", caption="Новый пост")

for user_id in [1, 2, 3]:
    try:
        bot.send(user_id, "Рассылка")
    except wgram.TelegramAPIError as e:
        print(user_id, "не доставлено:", e.description)    # например, пользователь заблокировал бота
```

Бот может написать пользователю **только после того, как тот сам написал боту** (`/start`).
Лимиты Telegram: не чаще ~30 сообщений в секунду в разные чаты и 1 сообщение в секунду в один чат.

---

## 16. `async`-режим

Если вы привыкли к `async`, всё работает так же. Обработчики могут быть `async def`, а вызовы методов
можно ждать через `await`:

```python
@bot.on("/slow")
async def slow(msg):
    sent = await msg.reply("Думаю...")      # await возвращает отправленное Message
    await asyncio.sleep(2)
    await sent.edit("Готово")
    msg.reply("Это сообщение тоже уйдёт, даже без await")
```

- Блокирующий код (`time.sleep`, `requests`) в `async`-обработчике **замораживает всех**: используйте
  `await asyncio.sleep` или обычную `def`-функцию.
- Обычные `def`-обработчики выполняются в потоках, там блокирующий код безопасен.
- Запуск внутри своего event loop (Jupyter, FastAPI): `await bot.run_async()`.

---

## 17. Справочник методов `bot`

Первый параметр везде `chat_id` (число или `"@канал"`). Все они возвращают результат прямо в обычном коде
(в `async`-обработчике возвращают то, что можно `await`).

**Отправка:** `send`, `send_photo`, `send_document`, `send_video`, `send_audio`, `send_voice`,
`send_animation`, `send_video_note`, `send_sticker`, `send_location`, `send_venue`, `send_contact`,
`send_poll`, `send_dice`, `send_media_group`, `send_chat_action` (`typing`), `send_invoice`.

**Изменение сообщений:** `edit_text`, `edit_caption`, `edit_keyboard`, `delete_message`, `delete_messages`,
`forward`, `copy`, `pin`, `unpin`, `unpin_all`, `react`, `stop_poll`.

**Ответы на события:** `answer_callback`, `answer_inline`, `answer_checkout`.

**Чаты:** `get_chat`, `get_member`, `get_admins`, `member_count`, `is_admin`, `ban`, `unban`, `kick`,
`mute`, `unmute`, `restrict`, `promote`, `set_title`, `set_description`, `set_chat_photo`, `invite_link`, `leave`.

**Бот и файлы:** `get_me`, `set_commands`, `delete_commands`, `get_file`, `download`, `call`.

**Состояния:** `set_state`, `get_state`, `clear_state`, `user_data`.

**Управление:** `run`, `run_async`, `stop`.

Общие необязательные параметры отправки: `keyboard`, `parse`, `reply_to`, `silent`, `protect`, `thread_id`
(тема форума), плюс любые `**extra`, которые уходят в Telegram как есть.
Например: `bot.send(chat_id, "Привет", message_effect_id="...")`.

**Метода нет в wgram?** Вызовите напрямую, названия и параметры берутся из
[документации Bot API](https://core.telegram.org/bots/api):

```python
result = bot.call("getUserProfilePhotos", user_id=123, limit=1)
```

**Типы:** `Message`, `CallbackQuery`, `InlineQuery`, `PollAnswer`, `ChatMemberUpdate`, `PreCheckoutQuery`,
`User`, `Chat`, `ChatMember`, `Media`, `Location`, `Contact`, `Poll`, `Dice`: все лежат в `wgram.*`,
а исходный словарь Telegram доступен в `.raw`.

---

## 18. Ошибки и исключения

```python
try:
    bot.send(user_id, "Привет")
except wgram.TelegramAPIError as e:
    print(e.error_code, e.description)       # 403 Forbidden: bot was blocked by the user
except wgram.NetworkError as e:
    print("Нет связи:", e)
```

- `TelegramAPIError`: Telegram вернул ошибку. `description` текст от Telegram, `error_code` код, `retry_after` пауза при 429.
- `NetworkError`: таймаут, обрыв соединения, битый ответ.
- Общий предок обоих: `wgram.WgramError`.
- Токен не попадает в тексты ошибок и логи.
- Неверный токен останавливает `bot.run()` с понятной ошибкой `401 Unauthorized`.

---

## 19. Вопросы и ответы

**Бот молчит.** Проверьте токен; что вы пишете именно этому боту; что запущен только один экземпляр
(две копии с одним токеном мешают друг другу, Telegram вернёт `409 Conflict`).

**В группе бот не видит обычные сообщения.** Отключите режим приватности: @BotFather → `/setprivacy` → Disable,
затем удалите бота из группы и добавьте снова. Или сделайте его админом.

**Можно ли использовать вебхуки?** Нет, wgram работает только через long polling (этого достаточно для
большинства ботов). При запуске `bot.run()` вебхук, если он был, выключается.

**Данные пропадают после перезапуска.** `states` и `user_data` хранятся в памяти. Сохраняйте важное в файл (`json`, `sqlite3`) или базу.

**Как отправить сообщение конкретному пользователю?** `bot.send(user_id, "текст")`. Узнать `id` можно из `msg.user.id`.
Написать первым нельзя: пользователь должен сначала запустить бота.

**Как узнать file_id уже загруженного файла?** Отправьте файл боту, в обработчике возьмите `msg.photo.file_id`
(или `msg.document.file_id` и т.д.) и используйте его вместо пути: так отправка мгновенная.

**Почему при нажатии кнопки `cb.edit()` убирает кнопки?** Так работает Telegram: сообщение без указанной
клавиатуры редактируется без неё. Передайте `keyboard=` снова.

**Одинаковые тексты в `on("текст")` и кнопке.** Точный текст сравнивается с полным совпадением и учитывает
регистр. Для нечувствительности к регистру добавьте `ignore_case=True`.

---

Лицензия MIT.
