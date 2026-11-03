"""Проверки простых правил без декораторов."""

import unittest

import wgram
from test_wgram import make_bot, msg, upd


class EasyTests(unittest.TestCase):
    def test_first_bot_without_functions(self):
        bot, api = make_bot([[upd(1, message=msg('/start')),
                              upd(2, message=msg('КоТ'))]])
        bot.when('/start').say('Привет')
        bot.when_contains('кот', 'Мяу')
        bot.run()
        self.assertEqual([p['text'] for p in api.find('sendMessage')], ['Привет', 'Мяу'])

    def test_question_and_state(self):
        bot, api = make_bot([[upd(1, message=msg('привет')),
                              upd(2, message=msg('Вася'))]])
        bot.when('привет').ask('Как тебя зовут?', state='name')
        bot.when_state('name').say('Очень приятно', clear_state=True)
        bot.run()
        self.assertEqual([p['text'] for p in api.find('sendMessage')],
                         ['Как тебя зовут?', 'Очень приятно'])
        self.assertIsNone(bot.get_state(1))

    def test_buttons_and_media_rules(self):
        bot, api = make_bot([[upd(1, message=msg('/menu')),
                              upd(2, message=msg('/photo'))]])
        keyboard = wgram.menu(wgram.choice('Да', 'yes', color='success'),
                              wgram.choice('Нет', 'no', color='danger'))
        bot.when('/menu').say('Выбирай', buttons=keyboard)
        bot.when('/photo').picture('FILE_ID_123', caption='Фото')
        bot.run()
        markup = api.find('sendMessage')[0]['reply_markup']['inline_keyboard'][0]
        self.assertEqual(markup[0]['style'], 'success')
        self.assertEqual(markup[1]['style'], 'danger')
        self.assertEqual(api.find('sendPhoto')[0]['photo'], 'FILE_ID_123')

    def test_file_video_voice_shortcuts(self):
        bot, api = make_bot([[upd(1, message=msg(document={'file_id': 'doc'})),
                              upd(2, message=msg(video={'file_id': 'vid'})),
                              upd(3, message=msg(voice={'file_id': 'voice'}))]])
        bot.when_file().say('Документ получен')
        bot.when_video().say('Видео получено')
        bot.when_voice().say('Голосовое получено')
        bot.run()
        self.assertEqual([p['text'] for p in api.find('sendMessage')],
                         ['Документ получен', 'Видео получено', 'Голосовое получено'])

    def test_old_methods_and_simple_button(self):
        bot, api = make_bot([[upd(1, message=msg('/start')),
                              upd(2, callback_query={
                                  'id': 'abc', 'from': {'id': 1, 'first_name': 'V'},
                                  'data': 'yes', 'message': msg('posted')})]])
        bot.when('/start').say('Новый способ')
        bot.on('/old')(lambda message: message.reply('Старый способ'))
        bot.when_button('yes').say('Нажато')
        bot.run()
        self.assertEqual(api.find('answerCallbackQuery')[0]['text'], 'Нажато')
        self.assertEqual(api.find('sendMessage')[0]['text'], 'Новый способ')

    def test_remember_and_safe_template(self):
        bot, api = make_bot([[upd(1, message=msg('привет')),
                              upd(2, message=msg('<Вася>'))]], parse='html')
        bot.when('привет').ask('Как тебя зовут?', state='name')
        bot.when_state('name').remember('name').say('Привет, {name}!', clear_state=True)
        bot.run()
        self.assertEqual(api.find('sendMessage')[-1]['text'], 'Привет, &lt;Вася&gt;!')
        self.assertIsNone(bot.get_state(1))

    def test_post_to_channel_without_function(self):
        bot, api = make_bot([[upd(1, message=msg('/post'))]])
        bot.when('/post').post(-1001234567890, 'Пост', photo='FILE_ID_123')
        bot.run()
        self.assertEqual(api.find('sendPhoto')[0]['caption'], 'Пост')
        self.assertEqual(api.find('sendMessage')[-1]['text'], 'Опубликовано. ID: 101')

    def test_shortcuts_validate_input(self):
        bot = wgram.start('123:abc')
        with self.assertRaises(ValueError):
            bot.when('')
        with self.assertRaises(ValueError):
            bot.when_contains('')
        with self.assertRaises(ValueError):
            bot.when('/ask').ask('Вопрос', state='')
        self.assertIn('keyboard', wgram.buttons('Да', 'Нет').to_dict())
        with self.assertRaises(ValueError):
            wgram.choice('X', data='x', url='https://example.com')
