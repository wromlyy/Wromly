"""Business updates, отправка и управление чатами через Bot API."""

import unittest

import wgram
from test_wgram import make_bot, msg, upd
from wgram.types import Update


class BusinessTests(unittest.TestCase):
    def test_business_message_reply_keeps_connection(self):
        raw = msg('Привет')
        raw['business_connection_id'] = 'bc-123'
        bot, api = make_bot([[upd(1, business_message=raw)]])
        bot.when_business('Привет').say('Здравствуйте')
        bot.run()
        self.assertIn('business_message', api.find('getUpdates')[0]['allowed_updates'])
        sent = api.find('sendMessage')
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]['business_connection_id'], 'bc-123')
        self.assertEqual(sent[0]['chat_id'], 1)

    def test_business_outgoing_is_not_auto_replied(self):
        raw = msg('Привет')
        raw['business_connection_id'] = 'bc-123'
        raw['sender_business_bot'] = {'id': 777, 'is_bot': True, 'first_name': 'T'}
        bot, api = make_bot([[upd(1, business_message=raw)]])
        bot.when_business('Привет').say('Здравствуйте')
        bot.run()
        self.assertEqual(api.find('sendMessage'), [])

    def test_business_connection_and_deletion_updates(self):
        connection = {'id': 'bc-123', 'user': {'id': 7, 'first_name': 'Owner'},
                      'user_chat_id': 7, 'date': 1, 'is_enabled': True,
                      'rights': {'can_reply': True}}
        update = Update.from_dict(upd(1, business_connection=connection))
        self.assertEqual(update.kind, 'business_connection')
        self.assertTrue(update.obj.rights['can_reply'])
        update = Update.from_dict(upd(2, deleted_business_messages={
            'business_connection_id': 'bc-123',
            'chat': {'id': 8, 'type': 'private'}, 'message_ids': [10, 11]}))
        self.assertEqual(update.kind, 'business_deleted')
        self.assertEqual(update.obj.message_ids, [10, 11])

    def test_business_facade_uses_correct_methods(self):
        bot, api = make_bot([])
        business = bot.business('bc-123')
        business.say(42, 'Привет')
        business.picture(42, 'FILE_ID_123', caption='Фото')
        business.read(42, 1)
        business.delete(1, 2)
        business.set_bio('О нас')
        methods = [name for name, params, files in api.calls]
        self.assertEqual(methods,
                         ['sendMessage', 'sendPhoto', 'readBusinessMessage',
                          'deleteBusinessMessages', 'setBusinessAccountBio'])
        self.assertTrue(all(params['business_connection_id'] == 'bc-123'
                            for _, params, _ in api.calls))
        self.assertEqual(api.find('deleteBusinessMessages')[0]['message_ids'], [1, 2])
        with self.assertRaises(ValueError):
            business.delete()

    def test_join_request_and_chat_management(self):
        bot, api = make_bot([])
        request = Update.from_dict(upd(1, chat_join_request={
            'chat': {'id': -100, 'type': 'supergroup'},
            'from': {'id': 7, 'first_name': 'A'}, 'date': 1}), bot)
        self.assertEqual(request.kind, 'join_request')
        request.obj.approve()
        bot.set_chat_permissions(-100, can_send_messages=False)
        bot.decline_join(-100, 8)
        bot.export_invite_link(-100)
        self.assertEqual([name for name, _, _ in api.calls], [
            'approveChatJoinRequest', 'setChatPermissions',
            'declineChatJoinRequest', 'exportChatInviteLink'])
        self.assertEqual(api.find('setChatPermissions')[0]['permissions'],
                         {'can_send_messages': False})

    def test_business_events_reach_handlers(self):
        connection = {'id': 'bc-123', 'user': {'id': 7, 'first_name': 'Owner'},
                      'user_chat_id': 7, 'date': 1, 'is_enabled': True}
        deleted = {'business_connection_id': 'bc-123',
                   'chat': {'id': 8, 'type': 'private'}, 'message_ids': [10]}
        bot, api = make_bot([[upd(1, business_connection=connection),
                              upd(2, deleted_business_messages=deleted),
                              upd(3, chat_join_request={
                                  'chat': {'id': -100, 'type': 'channel'},
                                  'from': {'id': 9, 'first_name': 'A'}, 'date': 1})]])
        received = []
        bot.on_business_connection(lambda event: received.append(('connection', event.id)))
        bot.on_business_deleted(lambda event: received.append(('deleted', event.message_ids)))
        bot.on_join_request(lambda event: received.append(('join', event.chat_id)))
        bot.run()
        self.assertEqual(set((kind, str(value)) for kind, value in received), {
            ('connection', 'bc-123'), ('deleted', '[10]'), ('join', '-100')})

    def test_business_message_shortcuts(self):
        raw = msg('Привет', business_connection_id='bc-123')
        bot, api = make_bot([[upd(1, business_message=raw)]])
        bot.on_business('Привет')(lambda message: 'Ответ')
        bot.run()
        self.assertEqual(api.find('sendMessage')[0]['business_connection_id'], 'bc-123')
        message = Update.from_dict(upd(2, business_message=raw), bot).obj
        message.edit_keyboard(wgram.InlineKeyboard([('Да', 'yes')]))
        message.delete()
        self.assertEqual(api.find('editMessageReplyMarkup')[0]['business_connection_id'],
                         'bc-123')
        self.assertEqual(api.find('deleteBusinessMessages')[0]['message_ids'], [10])

    def test_auto_delete_channel_and_group(self):
        bot, api = make_bot([[upd(1, channel_post=msg('Спам', 'channel', uid=-100)),
                              upd(2, message=msg('Спам', 'supergroup', uid=-100)),
                              upd(3, channel_post=msg('Другое', 'channel', uid=-100))]])
        bot.auto_delete(-100, 'спам')
        bot.run()
        self.assertEqual(len(api.find('deleteMessage')), 2)

    def test_management_and_business_media_shortcuts(self):
        bot, api = make_bot([])
        business = bot.business('bc-123')
        business.voice(42, 'FILE_ID')
        business.action(42)
        business.edit_keyboard(42, 7)
        bot.edit_invite_link(-100, 'https://t.me/+abc', name='Новая')
        bot.set_admin_title(-100, 7, 'Помощник')
        self.assertEqual([name for name, _, _ in api.calls], [
            'sendVoice', 'sendChatAction', 'editMessageReplyMarkup',
            'editChatInviteLink', 'setChatAdministratorCustomTitle'])
        self.assertTrue(all(params['business_connection_id'] == 'bc-123'
                            for _, params, _ in api.calls[:3]))

    def test_business_profile_and_story_upload_new_files(self):
        bot, api = make_bot([])
        business = bot.business('bc-123')
        business.set_profile_photo(b'JPG')
        business.post_story(b'JPG', 86400)
        business.edit_story(7, {'type': 'video', 'video': b'MP4', 'duration': 5})
        self.assertEqual([name for name, _, _ in api.calls], [
            'setBusinessAccountProfilePhoto', 'postStory', 'editStory'])
        for _, params, files in api.calls:
            self.assertEqual(params['business_connection_id'], 'bc-123')
            self.assertIn('business_media', files)
        self.assertEqual(api.calls[0][1]['photo']['photo'], 'attach://business_media')
        self.assertEqual(api.calls[1][1]['content']['photo'], 'attach://business_media')
        self.assertEqual(api.calls[2][1]['content']['video'], 'attach://business_media')
        with self.assertRaises(ValueError):
            business.set_profile_photo('OLD_FILE_ID')
