"""Бот-модератор для группы: приветствие, бан, мут, удаление спама."""
import wgram

bot = wgram.start("ВАШ_ТОКЕН", parse="html")


@bot.on_join
def welcome(msg):
    for user in msg.new_members:
        msg.reply("Добро пожаловать, {}!".format(user.mention))


@bot.on("/ban", chat="group")
def ban(msg):
    if not bot.is_admin(msg.chat_id, msg.user.id):
        return "Только для админов"
    if msg.reply_to is None:
        return "Ответьте командой /ban на сообщение нарушителя"
    bot.ban(msg.chat_id, msg.reply_to.user.id)
    msg.reply("Забанен: " + msg.reply_to.user.name)


@bot.on("/mute", chat="group")
def mute(msg):
    if not bot.is_admin(msg.chat_id, msg.user.id) or msg.reply_to is None:
        return "Ответьте на сообщение нарушителя (только админы)"
    minutes = int(msg.args) if msg.args.isdigit() else 10
    bot.mute(msg.chat_id, msg.reply_to.user.id, seconds=minutes * 60)
    msg.reply("Мут на {} мин".format(minutes))


@bot.on(contains=["http://", "https://"], chat="group")   # антиспам: ссылки только админам
def no_links(msg):
    if not bot.is_admin(msg.chat_id, msg.user.id):
        msg.delete()


@bot.on("/id")
def my_id(msg):
    msg.reply("Твой id: <code>{}</code>\nId чата: <code>{}</code>".format(msg.user.id, msg.chat_id))


bot.run()
