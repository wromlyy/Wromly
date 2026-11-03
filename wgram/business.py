"""Действия от имени подключённого Telegram Business аккаунта."""


class Business:
    """bot.business(connection_id): сообщения, чтение и управление аккаунтом."""

    def __init__(self, bot, connection_id):
        if not isinstance(connection_id, str) or not connection_id:
            raise ValueError("Нужен business_connection_id")
        self.bot = bot
        self.id = connection_id

    def info(self):
        return self.bot.get_business_connection(self.id)

    def say(self, chat_id, text, buttons=None, **options):
        return self.bot.say(chat_id, text, buttons=buttons,
                            business_connection_id=self.id, **options)

    def picture(self, chat_id, photo, caption=None, buttons=None, **options):
        return self.bot.picture(chat_id, photo, caption=caption, buttons=buttons,
                                business_connection_id=self.id, **options)

    def file(self, chat_id, document, caption=None, buttons=None, **options):
        return self.bot.file(chat_id, document, caption=caption, buttons=buttons,
                             business_connection_id=self.id, **options)

    def video(self, chat_id, video, caption=None, buttons=None, **options):
        return self.bot.send_video(chat_id, video, caption=caption, keyboard=buttons,
                                   business_connection_id=self.id, **options)

    def audio(self, chat_id, audio, caption=None, **options):
        return self.bot.send_audio(chat_id, audio, caption=caption,
                                   business_connection_id=self.id, **options)

    def voice(self, chat_id, voice, caption=None, **options):
        return self.bot.send_voice(chat_id, voice, caption=caption,
                                   business_connection_id=self.id, **options)

    def animation(self, chat_id, animation, caption=None, **options):
        return self.bot.send_animation(chat_id, animation, caption=caption,
                                       business_connection_id=self.id, **options)

    def sticker(self, chat_id, sticker, **options):
        return self.bot.send_sticker(chat_id, sticker,
                                     business_connection_id=self.id, **options)

    def location(self, chat_id, latitude, longitude, **options):
        return self.bot.send_location(chat_id, latitude, longitude,
                                      business_connection_id=self.id, **options)

    def contact(self, chat_id, phone, first_name, **options):
        return self.bot.send_contact(chat_id, phone, first_name,
                                     business_connection_id=self.id, **options)

    def poll(self, chat_id, question, options, **settings):
        return self.bot.send_poll(chat_id, question, options,
                                  business_connection_id=self.id, **settings)

    def action(self, chat_id, action="typing"):
        return self.bot.send_chat_action(chat_id, action,
                                         business_connection_id=self.id)

    def edit(self, chat_id, message_id, text, buttons=None, **options):
        return self.bot.edit_text(chat_id, message_id, text, keyboard=buttons,
                                  business_connection_id=self.id, **options)

    def edit_caption(self, chat_id, message_id, caption, buttons=None, **options):
        return self.bot.edit_caption(chat_id, message_id, caption, keyboard=buttons,
                                     business_connection_id=self.id, **options)

    def edit_keyboard(self, chat_id, message_id, buttons=None):
        return self.bot.edit_keyboard(chat_id, message_id, keyboard=buttons,
                                      business_connection_id=self.id)

    def read(self, chat_id, message_id):
        return self.call("readBusinessMessage", chat_id=chat_id, message_id=message_id)

    def delete(self, *message_ids):
        if not 1 <= len(message_ids) <= 100:
            raise ValueError("Передай от 1 до 100 ID сообщений")
        return self.call("deleteBusinessMessages", message_ids=list(message_ids))

    def set_name(self, first_name, last_name=None):
        return self.call("setBusinessAccountName", first_name=first_name,
                         last_name=last_name)

    def set_username(self, username):
        return self.call("setBusinessAccountUsername", username=username)

    def set_bio(self, bio):
        return self.call("setBusinessAccountBio", bio=bio)

    def set_profile_photo(self, photo, is_public=False):
        """Новый JPG-файл или InputProfilePhoto со свежим файлом."""
        data, files = self._upload_object(photo, "photo", "static")
        return self.bot._do("setBusinessAccountProfilePhoto", {
            "business_connection_id": self.id, "photo": data,
            "is_public": is_public}, files)

    def remove_profile_photo(self, is_public=False):
        return self.call("removeBusinessAccountProfilePhoto", is_public=is_public)

    def set_gift_settings(self, show_gift_button, accepted_gift_types):
        return self.call("setBusinessAccountGiftSettings",
                         show_gift_button=show_gift_button,
                         accepted_gift_types=accepted_gift_types)

    def transfer_stars(self, count):
        return self.call("transferBusinessAccountStars", star_count=count)

    def convert_gift(self, owned_gift_id):
        return self.call("convertGiftToStars", owned_gift_id=owned_gift_id)

    def upgrade_gift(self, owned_gift_id, **options):
        return self.call("upgradeGift", owned_gift_id=owned_gift_id, **options)

    def transfer_gift(self, owned_gift_id, new_owner_chat_id, **options):
        return self.call("transferGift", owned_gift_id=owned_gift_id,
                         new_owner_chat_id=new_owner_chat_id, **options)

    def post_story(self, content, active_period, **options):
        """Новый файл фото или InputStoryContent со свежим фото/видео."""
        data, files = self._upload_object(content, "photo", "photo")
        params = {"business_connection_id": self.id, "content": data,
                  "active_period": active_period}
        params.update(options)
        return self.bot._do("postStory", params, files)

    def repost_story(self, from_chat_id, from_story_id, active_period, **options):
        return self.call("repostStory", from_chat_id=from_chat_id,
                         from_story_id=from_story_id,
                         active_period=active_period, **options)

    def edit_story(self, story_id, content, **options):
        data, files = self._upload_object(content, "photo", "photo")
        params = {"business_connection_id": self.id, "story_id": story_id,
                  "content": data}
        params.update(options)
        return self.bot._do("editStory", params, files)

    def delete_story(self, story_id):
        return self.call("deleteStory", story_id=story_id)

    def send_checklist(self, chat_id, checklist, **options):
        return self.call("sendChecklist", chat_id=chat_id, checklist=checklist,
                         **options)

    def edit_checklist(self, chat_id, message_id, checklist, **options):
        return self.call("editMessageChecklist", chat_id=chat_id,
                         message_id=message_id, checklist=checklist, **options)

    def stars(self):
        return self.call("getBusinessAccountStarBalance")

    def gifts(self, **filters):
        return self.call("getBusinessAccountGifts", **filters)

    @staticmethod
    def _upload_object(value, default_field, default_type):
        """Собрать вложенный Bot API объект и multipart файл для него."""
        from .api import split_file
        data = dict(value) if isinstance(value, dict) else {
            "type": default_type, default_field: value}
        field = next((name for name in ("photo", "video", "animation") if name in data), None)
        if field is None:
            raise ValueError("Нужен файл photo, video или animation")
        ref, upload = split_file(data[field], field)
        if upload is None:
            raise ValueError("Для профиля и Stories нужен новый файл, не file_id или URL")
        data[field] = "attach://business_media"
        return data, {"business_media": upload}

    def call(self, method, **params):
        """Любой разрешённый Bot API метод для этого подключения."""
        params["business_connection_id"] = self.id
        return self.bot.call(method, **params)
