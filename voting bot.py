import random
import string
import telebot
from telebot.types import *
import openpyexcel as xl
import json


class Poll:
    state = 'active'

    def __init__(self, question: str, answers: list[str]):
        self.question = question
        self.answers = answers


config = json.load(open('config.json'))
bot = telebot.TeleBot(config['bot_token'])
db = xl.load_workbook('stat.xlsx')
connected_user_chat_ids = []
poll_stack = []
invitations = []
command_list = \
    'Полный список команд:\n' \
    '/menu - отобразить меню\n' \
    '/somefunction [some parameters] - некоторая новая функция\n' \
    '/help - полный перечень команд'


def keyboard_builder(row_width: int, buttons: tuple[tuple[str, str]]):
    keyboard = InlineKeyboardMarkup(row_width=row_width)
    for button in buttons:
        keyboard.add(InlineKeyboardButton(button[0], callback_data=button[1]))
    return keyboard


def admin_permission(func):
    def wrapper(message, *args, **kwargs):
        if message.from_user.id not in config['admin_list']:
            bot.send_message(message.from_user.id, 'Только администраторы могут использовать эту команду')
            return
        return func(message, *args, **kwargs)

    return wrapper


def bot_holder_permission(func):
    def wrapper(message, *args, **kwargs):
        if message.from_user.id != config['bot_holder']:
            bot.send_message(message.from_user.id, 'Только владелец бота может использовать эту команду')
            return
        return func(message, *args, **kwargs)

    return wrapper


@bot.message_handler(commands=['menu'])
def menu_command(message: Message):
    bot.send_message(message.from_user.id, 'Меню', reply_markup=keyboard_markups['menu_keyboard'])


@bot.message_handler(commands=['start'])
def start_command(message: Message):
    bot.send_message(message.from_user.id,
                     "Привет, я чат-бот для проведения анонимного голосования.\n\n" + command_list,
                     reply_markup=keyboard_markups['go_to_menu_keyboard'])


@bot.message_handler(commands=['help'])
def start_command(message):
    bot.send_message(message.from_user.id, command_list)


@bot.callback_query_handler(lambda cb: cb.data == 'new_poll')
@admin_permission
def new_poll_command(callback: CallbackQuery):
    bot.answer_callback_query(callback.id)
    bot.send_message(callback.from_user.id, "Введите тему опроса")
    bot.register_next_step_handler(callback.message, poll_init_topic_handler)


def poll_init_topic_handler(message: Message):
    poll = Poll(message.text.strip())
    bot.send_message(message.chat.id, "Ведите варианты ответов (через точку с запятой [   ;   ])")
    bot.register_next_step_handler(message, poll_init_answers_handler, poll)


def poll_init_answers_handler(message: Message, poll: Poll):
    poll.answers = list(map(str.strip, message.text.split(";")))
    joiner = '\n '
    bot.send_message(message.from_user.id,
                     f"Ваш опрос:\n{poll.question}\n\nВарианты ответов:{joiner + joiner.join(poll.answers)}\n\nПодтвердить создание опроса?",
                     reply_markup=keyboard_markups['confirm_keyboard'])


@bot.message_handler(commands=['createinvitation'])
@bot_holder_permission
def create_invitation_command(message: Message):
    if message.from_user.id != config['bot_holder']:
        bot.send_message(message.from_user.id, 'Только владелец бота может создавать регистрационные приглашения')
        return
    invitation = '/register_' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=32))
    invitations.append(invitation)
    bot.send_message(message.from_user.id, f'Новое приглашение:\n{invitation}')


@bot.message_handler(regexp='/register_.*')
def register_command(message: Message):
    if message.from_user.id in config['admin_list']:
        bot.send_message(message.from_user.id, 'Пользователь уже зарегистрирован')
        return
    if message.text not in invitations:
        bot.send_message(message.from_user.id, 'Приглашение недействительно')
        return
    config['admin_list'].append(message.from_user.id)
    json.dump(config, open('config.json', 'w'), indent=4)
    invitations.remove(message.text)
    bot.send_message(message.from_user.id, 'Вы зарегистрированы как администратор!')


@bot.message_handler(commands=['subscribe'])
def subscribe_command(message: Message):
    if message.from_user.id in config['subscribed']:
        bot.send_message(message.from_user.id, 'Вы уже подписаны на голосования')
        return
    config['subscribed'].append(message.from_user.id)
    json.dump(config, open('config.json', 'w'), indent=4)
    bot.send_message(message.from_user.id, 'Вы подписались на голосования')


@bot.message_handler(commands=['unsubscribe'])
def subscribe_command(message: Message):
    if message.from_user.id not in config['subscribed']:
        bot.send_message(message.from_user.id, 'Вы и не были подписаны на голосования')
        return
    config['subscribed'].remove(message.from_user.id)
    json.dump(config, open('config.json', 'w'), indent=4)
    bot.send_message(message.from_user.id, 'Вы отписались от голосований')


bot.infinity_polling()
