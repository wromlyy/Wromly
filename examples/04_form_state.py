"""Анкета по шагам: состояния (FSM) и личные данные пользователя."""
import wgram

bot = wgram.start("ВАШ_ТОКЕН")


@bot.on("/form")
def form(msg):
    msg.set_state("name")                         # запоминаем, на каком шаге пользователь
    msg.reply("Как тебя зовут?")


@bot.on(state="name")                              # сработает, только если state == "name"
def got_name(msg):
    msg.user_data["name"] = msg.text               # личный словарь пользователя
    msg.set_state("age")
    msg.reply("Сколько тебе лет?")


@bot.on(state="age")
def got_age(msg):
    if not msg.text.isdigit():
        return "Нужно число. Попробуй ещё раз"    # состояние не меняем - спросим снова
    name = msg.user_data["name"]
    msg.clear_state()
    kb = wgram.InlineKeyboard([("Всё верно", "form_ok"), ("Заново", "form_again")])
    msg.reply("{}, {} лет. Верно?".format(name, msg.text), keyboard=kb)


@bot.on("/cancel")                                 # команды работают в любом состоянии
def cancel(msg):
    msg.clear_state()
    msg.reply("Отменено")


@bot.on_button("form_ok")
def ok(cb):
    cb.edit("Анкета сохранена!")


@bot.on_button("form_again")
def again(cb):
    cb.set_state("name")
    cb.edit("Начинаем заново. Как тебя зовут?")


bot.run()
