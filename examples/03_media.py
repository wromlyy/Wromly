"""Отправка и приём фото, документов, голосовых, стикеров, альбомов, опросов."""
import wgram

bot = wgram.start("ВАШ_ТОКЕН", parse="html")      # parse="html" - форматирование по умолчанию


@bot.on("/photo")
def photo(msg):
    msg.action("upload_photo")                    # "отправляет фото..."
    msg.reply_photo("https://picsum.photos/600/400", caption="<b>Случайное фото</b>")
    # Можно путь к файлу, bytes, открытый файл или file_id:
    # msg.reply_photo("cat.jpg"); msg.reply_photo(open("cat.jpg", "rb"))


@bot.on("/album")
def album(msg):
    msg.reply_media_group([
        wgram.InputMedia.photo("https://picsum.photos/400/300", caption="Первое"),
        wgram.InputMedia.photo("https://picsum.photos/401/300"),
    ])


@bot.on("/poll")
def poll(msg):
    msg.reply_poll("Любимый язык?", ["Python", "Rust", "Go"], anonymous=False)


@bot.on("/quiz")
def quiz(msg):
    msg.reply_poll("2 + 2 = ?", ["3", "4", "5"], quiz=True, correct=1,
                   explanation="Это же арифметика!")


@bot.on("/dice")
def dice(msg):
    sent = msg.reply_dice("🎯")


@bot.on("/where")
def where(msg):
    msg.reply_location(55.7558, 37.6173)


# ---------- приём файлов ----------

@bot.on_photo
def got_photo(msg):
    path = msg.download("downloads/")            # папка создастся сама
    msg.reply("Сохранил фото: {} ({}x{})".format(path, msg.photo.width, msg.photo.height))


@bot.on_document
def got_doc(msg):
    data = msg.download()                         # без пути - вернёт bytes
    msg.reply("Файл {} - {} байт".format(msg.document.file_name, len(data)))


@bot.on_voice
def got_voice(msg):
    msg.reply("Голосовое: {} сек".format(msg.voice.duration))


@bot.on_sticker
def got_sticker(msg):
    msg.reply_sticker(msg.sticker.file_id)        # отправляем тот же стикер обратно


bot.run()
