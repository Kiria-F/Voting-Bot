import random
import string
import telebot
from telebot.types import *
import openpyexcel as xl
import json


class Poll:
    id: int
    question: str
    answers: list[str]
    state: str

    def __init__(self, question: str, answers: list[str], state: str = 'local'):
        self.question = question
        self.answers = answers
        self.state = state
        self.id = -1


config = json.load(open('config.json'))
bot = telebot.TeleBot(config['bot_token'])
db_book = xl.load_workbook('stat.xlsx')
db_sheet = db_book.active
connected_user_chat_ids = []
new_creating_polls: dict[int, Poll] = {}
stashed_polls: dict[int, list[Poll]] = {}
invitations = []
command_list = \
    'Полный список команд:\n' \
    '/menu - отобразить меню\n' \
    '/somefunction [some parameters] - некоторая новая функция\n' \
    '/help - полный перечень команд'


def keyboard_builder(*button_rows: list[tuple[str, str]], max_row_width=3) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=max_row_width)
    for button_row in button_rows:
        keyboard.add(*map(lambda button: InlineKeyboardButton(button[0], callback_data=button[1]), button_row),
                     row_width=len(button_row))
    return keyboard


def admin_permission(func):
    def wrapper(mes_cb: Message | CallbackQuery, *args, **kwargs):
        if mes_cb.from_user.id not in config['admin_list']:
            if mes_cb is CallbackQuery:
                bot.answer_callback_query(mes_cb.id)
            bot.send_message(mes_cb.from_user.id, 'Только администраторы могут использовать эту команду')
            return
        return func(mes_cb, *args, **kwargs)

    return wrapper


def bot_holder_permission(func):
    def wrapper(mes_cb: Message | CallbackQuery, *args, **kwargs):
        if mes_cb.from_user.id != config['bot_holder']:
            if mes_cb is CallbackQuery:
                bot.answer_callback_query(mes_cb.id)
            bot.send_message(mes_cb.from_user.id, 'Только владелец бота может использовать эту команду')
            return
        return func(mes_cb, *args, **kwargs)

    return wrapper


def instant_callback_answer(func):
    def wrapper(callback: CallbackQuery, *args, **kwargs):
        bot.answer_callback_query(callback.id)
        return func(callback, *args, **kwargs)

    return wrapper


def get_next_id() -> int:
    next_id = db_sheet['B1'].value
    next_id += 1
    db_sheet['B1'].value = next_id
    db_book.save('stat.xlsx')
    return next_id


@bot.message_handler(commands=['start'])
def start_command(message: Message):
    bot.send_message(message.from_user.id,
                     "Привет, я чат-бот для проведения анонимных опросов.\n\n" + command_list,
                     reply_markup=keyboard_builder([('Меню', 'menu')]))


@bot.message_handler(commands=['help'])
def help_command(message: Message):
    bot.send_message(message.from_user.id, command_list)


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                            Меню управления опросами                            ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


@bot.message_handler(commands=['menu'])
def menu_command(message: Message):
    bot.send_message(message.from_user.id,
                     'Меню управления опросами',
                     reply_markup=keyboard_builder(
                         [('Создать новый', 'new_poll'), ('Мои отложенные', 'stashed_polls')],
                         [('Активные', 'active_polls'), ('Архив', 'archived_polls')]))


@bot.callback_query_handler(lambda cb: cb.data.startswith('menu'))
@instant_callback_answer
def menu_handler(callback: CallbackQuery):
    if len(callback.data.split(maxsplit=1)) > 1:
        param = callback.data.split(maxsplit=1)[1]
        if param == 'clear_new_poll':
            new_creating_polls.pop(callback.from_user.id)
    bot.edit_message_text('Меню управления опросами:',
                          callback.message.chat.id,
                          callback.message.id,
                          reply_markup=keyboard_builder(
                              [('Создать новый', 'new_poll'), ('Мои отложенные', 'stashed_polls')],
                              [('Активные', 'active_polls'), ('Архив', 'archived_polls')]))


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                             Создание нового опроса                             ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


@bot.callback_query_handler(lambda cb: cb.data == 'new_poll')
@admin_permission
@instant_callback_answer
def new_poll_handler(callback: CallbackQuery):
    bot.send_message(callback.from_user.id, "Введите тему опроса")
    bot.register_next_step_handler(callback.message, poll_init_topic_handler)


def poll_init_topic_handler(message: Message):
    question = message.text.strip()
    bot.send_message(message.chat.id, "Ведите варианты ответов (через точку с запятой [   ;   ])")
    bot.register_next_step_handler(message, poll_init_answers_handler, question)


def poll_init_answers_handler(message: Message, question: str):
    poll_json = {'question': question, 'answers': list(map(str.strip, message.text.split(";")))}
    poll = Poll(**poll_json)
    new_creating_polls[message.from_user.id] = poll
    joiner = '\n- '
    bot.send_message(message.from_user.id,
                     f"Тема опроса:\n*{poll.question}*"
                     f"\n\nВарианты ответов:{joiner + joiner.join(poll.answers)}"
                     f"\n\nПодтвердить создание опроса?",
                     reply_markup=keyboard_builder(
                         [('Подтвердить', 'confirm_new_poll')],
                         [('Назад', 'menu clear_new_poll')]),
                     parse_mode='Markdown')


@bot.callback_query_handler(lambda cb: cb.data == 'confirm_new_poll')
@instant_callback_answer
def confirm_new_poll_handler(callback: CallbackQuery):
    if new_creating_polls[callback.from_user.id].id == -1:
        new_creating_polls[callback.from_user.id].id = get_next_id()
    bot.edit_message_text('Начать опрос сейчас?',
                          callback.message.chat.id,
                          callback.message.id,
                          reply_markup=keyboard_builder([('Да', 'start_poll new'), ('Нет', 'save_poll')]))


@bot.callback_query_handler(lambda cb: cb.data == 'save_poll')
@instant_callback_answer
def save_poll_to_stack_handler(callback: CallbackQuery):
    poll = new_creating_polls.pop(callback.from_user.id)
    if callback.from_user.id not in stashed_polls:
        stashed_polls[callback.from_user.id] = []
    stashed_polls[callback.from_user.id].append(poll)
    bot.edit_message_text('Опрос сохранен.',
                          callback.message.chat.id,
                          callback.message.id,
                          reply_markup=keyboard_builder([('Вернуться в меню', 'menu')]))


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                        Управление отложенными опросами                         ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


def check_admin_id_in_stash(func):
    def wrapper(callback: CallbackQuery, *args, **kwargs):
        if callback.from_user.id not in stashed_polls:
            bot.answer_callback_query(callback.id)
            bot.edit_message_text('Ваши сохраненные опросы не найдены.\n'
                                  'Возможно, это было вызвано перезапуском сервера.\n'
                                  'Если вы уверены, что это ошибка бота, свяжитесь с разработчиками.',
                                  callback.message.chat.id,
                                  callback.message.id,
                                  reply_markup=keyboard_builder([('Меню', 'menu')]))
            return
        return func(callback, *args, **kwargs)

    return wrapper


def check_and_get_poll_id_in_stash(func):
    def wrapper(callback: CallbackQuery, *args, **kwargs):
        callback_separated = callback.data.split()
        poll = None
        if len(callback_separated) > 1:
            poll_id = callback_separated[1]
            if poll_id.isnumeric():
                poll_id = int(poll_id)
                poll = next((poll for poll in stashed_polls[callback.from_user.id] if poll.id == poll_id), None)
                if poll is None:
                    bot.answer_callback_query(callback.id)
                    bot.edit_message_text('Искомый опрос не найден.\n'
                                          'Возможно, это было вызвано перезапуском сервера.\n'
                                          'Если вы уверены, что это ошибка бота, свяжитесь с разработчиками.',
                                          callback.message.chat.id,
                                          callback.message.id,
                                          reply_markup=keyboard_builder([('Меню', 'menu')]))
                    return
        return func(callback, poll, *args, **kwargs)

    return wrapper


@bot.callback_query_handler(lambda cb: cb.data == 'stashed_polls')
@check_admin_id_in_stash
@instant_callback_answer
def stashed_polls_handler(callback: CallbackQuery):
    bot.edit_message_text('Список отложенных опросов:',
                          callback.message.chat.id,
                          callback.message.id,
                          reply_markup=keyboard_builder(
                              list(map(lambda poll: (poll.question, 'stashed_poll ' + str(poll.id)),
                                       stashed_polls[callback.from_user.id])),
                              [('Назад', 'menu')],
                              max_row_width=2))


@bot.callback_query_handler(lambda cb: cb.data.startswith('stashed_poll '))
@check_admin_id_in_stash
@check_and_get_poll_id_in_stash
@instant_callback_answer
def stashed_poll_handler(callback: CallbackQuery, poll: Poll):
    joiner = '\n- '
    bot.edit_message_text(f"Тема опроса:\n*{poll.question}*"
                          f"\n\nВарианты ответов:{joiner + joiner.join(poll.answers)}",
                          callback.message.chat.id,
                          callback.message.id,
                          reply_markup=keyboard_builder(
                              [('Запустить', f'start_poll {poll.id}'), ('Удалить', f'remove_stashed_poll {poll.id}')],
                              [('Назад', 'stashed_polls')]),
                          parse_mode='Markdown')


@bot.callback_query_handler(lambda cb: cb.data.startswith('remove_stashed_poll '))
@check_admin_id_in_stash
@check_and_get_poll_id_in_stash
def remove_stashed_poll_handler(callback: CallbackQuery, poll: Poll):
    plug_handler(callback, 'menu')


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                                 Запуск опроса                                  ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


@bot.callback_query_handler(lambda cb: cb.data == 'start_new_poll')
@instant_callback_answer
def start_new_poll_handler(callback: CallbackQuery):
    if callback.from_user.id not in new_creating_polls:
        return
    plug_handler(callback, 'menu')


@bot.callback_query_handler(lambda cb: cb.data.startswith('start_poll '))
@check_admin_id_in_stash
@check_and_get_poll_id_in_stash
def start_stashed_poll_handler(callback: CallbackQuery, poll: Poll):
    plug_handler(callback, f'stashed_poll {poll.id}')


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                         Управление активными опросами                          ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


@bot.callback_query_handler(lambda cb: cb.data == 'active_polls')
def active_polls_handler(callback: CallbackQuery):
    plug_handler(callback, 'menu')


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                               Управление архивом                               ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


@bot.callback_query_handler(lambda cb: cb.data == 'archived_polls')
def archived_polls_handler(callback: CallbackQuery):
    plug_handler(callback, 'menu')


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                           Добавление администраторов                           ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


@bot.message_handler(commands=['createinvitation'])
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


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                      Подписка и отписка от новых опросов                       ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


@bot.message_handler(commands=['subscribe'])
def subscribe_command(message: Message):
    if message.from_user.id in config['subscribed']:
        bot.send_message(message.from_user.id, 'Вы уже подписаны на опросы')
        return
    config['subscribed'].append(message.from_user.id)
    json.dump(config, open('config.json', 'w'), indent=4)
    bot.send_message(message.from_user.id, 'Вы подписались на опросы')


@bot.message_handler(commands=['unsubscribe'])
def subscribe_command(message: Message):
    if message.from_user.id not in config['subscribed']:
        bot.send_message(message.from_user.id, 'Вы и не были подписаны на опросы')
        return
    config['subscribed'].remove(message.from_user.id)
    json.dump(config, open('config.json', 'w'), indent=4)
    bot.send_message(message.from_user.id, 'Вы отписались от опросов')


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                                   Служебное                                    ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


def plug_command(message: Message):
    bot.send_message(message.from_user.id, 'В разработке.')


@instant_callback_answer
def plug_handler(callback: CallbackQuery, home: str):
    bot.edit_message_text('В разработке.',
                          callback.message.chat.id,
                          callback.message.id,
                          reply_markup=keyboard_builder([('Назад', home)]))


@bot.message_handler(commands=['echo'])
def echo_command(message: Message):
    print(f'\nID: {message.from_user.id}\n'
          f'Имя: {message.from_user.first_name}\n'
          f'Фамилия: {message.from_user.last_name}\n'
          f'Ссылка: @{message.from_user.username}\n')


bot.infinity_polling()
