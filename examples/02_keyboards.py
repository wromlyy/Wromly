"""Кнопки: обычные под полем ввода и inline под сообщением."""
import wgram

bot = wgram.start("ВАШ_ТОКЕН")


@bot.on("/start")
def start(msg):
    # Обычная клавиатура: нажатие просто отправляет текст кнопки
    kb = wgram.Keyboard(["Меню", "Помощь"],
                        [wgram.Button("Отправить телефон", contact=True),
                         wgram.Button("Где я?", location=True)],
                        placeholder="Выберите действие")
    msg.reply("Привет! Выбери кнопку:", keyboard=kb)


@bot.on("Меню")
def menu(msg):
    # Inline-кнопки: нажатие вызывает @bot.on_button
    kb = wgram.InlineKeyboard(
        [("Да", "yes"), ("Нет", "no")],
        [("Открыть сайт", "https://example.com")],
        [wgram.InlineButton("Скопировать промокод", copy="PROMO2026")],
    )
    msg.reply("Тебе нравится wgram?", keyboard=kb)


@bot.on("Помощь")
def help_(msg):
    msg.reply("Помощь тут", keyboard=wgram.RemoveKeyboard())   # убрать клавиатуру


@bot.on_button("yes")
def yes(cb):
    cb.answer("Спасибо!")                  # всплывашка
    cb.edit("Ты ответил: Да")              # заменяем текст (кнопки исчезнут)


@bot.on_button("no")
def no(cb):
    cb.answer("Жаль :(", alert=True)       # окно с кнопкой OK
    cb.edit("Ты ответил: Нет")


# Счётчик: одна кнопка, которая сама обновляет сообщение
@bot.on("/counter")
def counter(msg):
    msg.reply("Счёт: 0", keyboard=[[("+1", "count:1"), ("+5", "count:5")]])


@bot.on_button(prefix="count:")            # cb.arg - то, что после "count:"
def count(cb):
    n = int(cb.text.split(":")[1]) + int(cb.arg)
    cb.edit("Счёт: {}".format(n), keyboard=[[("+1", "count:1"), ("+5", "count:5")]])


@bot.on_contact
def got_contact(msg):
    msg.reply("Твой номер: " + msg.contact.phone_number, keyboard=wgram.RemoveKeyboard())


@bot.on_location
def got_location(msg):
    msg.reply("Координаты: {}, {}".format(msg.location.latitude, msg.location.longitude))


bot.run()
