# Первый бот без сложного кода

Тут всё похоже на рассказ: **когда** человек что-то пишет, бот **говорит** ответ.
Для первого бота не нужны `@`, `def` и `async`.

## 1. Установи библиотеку

```bash
python -m pip install Wgram
```

Для разработки из этой папки:

```bash
python -m pip install -e .
```

## 2. Напиши бота

Создай файл `main.py`:

```python
import wgram

bot = wgram.start("ТОКЕН_ОТ_BOTFATHER")

bot.when("/start").say("Привет! Напиши мне: кот")
bot.when_contains("кот").say("Мяу!")

bot.run()
```

Вместо `ТОКЕН_ОТ_BOTFATHER` вставь свой токен. Не публикуй его в GitHub.
Запусти `python main.py`. Затем открой своего бота в Telegram и напиши `/start`.

## 3. Другие короткие правила

| Хочу сделать | Пишу |
|---|---|
| Поймать команду | `bot.when("/start").say("Привет")` |
| Поймать точное слово | `bot.when("привет").say("Привет")` |
| Найти слово в сообщении | `bot.when_contains("кот").say("Мяу")` |
| Показать обычные кнопки | `bot.when("/choose").say("Выбирай", buttons=wgram.buttons("Да", "Нет"))` |
| Получить документ | `bot.when_file().say("Файл получен")` |
| Получить видео | `bot.when_video().say("Видео получено")` |
| Получить голосовое | `bot.when_voice().say("Голосовое получено")` |
| Ответить на фото | `bot.when_photo().say("Красивое фото")` |
| Поймать нажатие кнопки | `bot.when_button("yes").say("Ты нажал Да")` |
| Спросить и ждать ответа | `bot.when("привет").ask("Как тебя зовут?", state="name")` |
| Ответить на следующий ответ | `bot.when_state("name").say("Спасибо", clear_state=True)` |
| Ответить фото | `bot.when("/photo").picture("photo.jpg")` |
| Ответить документом | `bot.when("/file").file("report.pdf")` |
| Написать в канал | `bot.say(CHANNEL_ID, "Привет")` |
| Отправить фото в канал | `bot.picture(CHANNEL_ID, "photo.jpg")` |
| Отправить документ в канал | `bot.file(CHANNEL_ID, "report.pdf")` |

Можно написать ещё короче: `bot.when("привет", "Привет")`.

Кнопки под сообщением:

```python
buttons = wgram.menu(
    wgram.choice("Да", "yes", color="success"),
    wgram.choice("Нет", "no", color="danger"),
)
bot.when("/menu").say("Выбирай:", buttons=buttons)
bot.when_button("yes").say("Ты выбрал Да")
```

[Полный рабочий пример](examples/10_easy_bot.py). Для бота с `.env` и несколькими файлами смотри [этот пример](examples/multi_file_bot/README.md).

Если нужны особые действия, можно передать свою функцию через `.do(моя_функция)`. Старые методы библиотеки тоже продолжают работать. Полное описание находится в [README](README.md).

## 4. Задачи посложнее, всё ещё без `@` и `def`

Бот может спросить имя, запомнить ответ и вставить его в текст:

```python
bot.when("/name").ask("Как тебя зовут?", state="name")
bot.when_state("name").remember("name").say("Привет, {name}!", clear_state=True)
```

`{name}` — сохранённый ответ. `{text}` — текст текущего сообщения, `{first_name}` — имя из Telegram, `{args}` — слова после команды. Значения пользователя безопасно экранируются для HTML и MarkdownV2. Память живёт до остановки бота.

Публикация фото в канал одной строкой:

```python
bot.when("/post").post(
    CHANNEL_ID, "<b>Новый пост</b>", photo="post.jpg", buttons=buttons
)
```

Бот проверяет, что команду отправил администратор канала. Сам бот тоже должен быть администратором канала с правом публикации. Положи фото `post.jpg` рядом со скриптом или замени путь на свой. Ошибка Telegram придёт в ответ на команду. [Полный пример](examples/11_easy_channel.py).
