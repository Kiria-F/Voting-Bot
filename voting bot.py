import os
import random
import string
from dataclasses import dataclass

import telebot
from telebot.types import *
import pandas as pd
import json


@dataclass
class Poll:
    question: str = None
    answers: list[str] = None
    anonymous: bool = None
    multi_choice: bool = None
    filename: str = None
    stat: list[int] = None

    @staticmethod
    def load(filename: str):
        with open(filename, encoding='utf-8') as file:
            return Poll(**json.load(file))

    def dump(self, filename: str):
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(self.__dict__, file, indent=4, ensure_ascii=False)

    def __str__(self):
        return f'Тема опроса:\n*{self.question}*' + \
            '\n\nВарианты ответов:' + \
            '\n- ' + '\n- '.join(self.answers) + \
            f'\n\nФайл: {self.filename}.csv' + \
            f'\n\nАнонимный: {"Да" if self.anonymous else "Нет"}' + \
            f'\nМультивыбор: {"Да" if self.multi_choice else "Нет"}'


config = json.load(open('config.json'))
bot = telebot.TeleBot(config['bot_token'])
connected_user_chat_ids = []
new_creating_polls: dict[int, Poll] = {}
stashed_polls: dict[int, list[Poll]] = {}
invitations = []
command_list = 'Полный список команд:\n' \
               '/menu - отобразить меню\n' \
               '/somefunction [some parameters] - некоторая новая функция\n' \
               '/help - полный перечень команд'


def keyboard_builder(*button_rows: list[tuple[str, str]], max_row_width=3) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=max_row_width)
    for button_row in button_rows:
        keyboard.add(
            *map(
                lambda button: InlineKeyboardButton(button[0], callback_data=button[1]), button_row),
            row_width=len(button_row))
    return keyboard


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                                   Декораторы                                   ║
# ╚════════════════════════════════════════════════════════════════════════════════╝

# TODO: Ещё кучу валидаторов

def admin_permission(func):
    def wrapper(mes_cb: Message | CallbackQuery, *args, **kwargs):
        if mes_cb.from_user.id not in config['admin_list']:
            if isinstance(mes_cb, CallbackQuery):
                bot.answer_callback_query(mes_cb.id)
            bot.send_message(mes_cb.from_user.id, 'Только администраторы могут использовать эту команду')
            return
        return func(mes_cb, *args, **kwargs)

    return wrapper


def bot_holder_permission(func):
    def wrapper(mes_cb: Message | CallbackQuery, *args, **kwargs):
        if mes_cb.from_user.id != config['bot_holder']:
            if isinstance(mes_cb, CallbackQuery):
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


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                                     Общее                                      ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


@bot.message_handler(commands=['start'])
def start_command(message: Message):
    bot.send_message(
        message.from_user.id,
        'Привет, я чат-бот для проведения анонимных опросов.\n\n' + command_list,
        reply_markup=keyboard_builder([('Меню', 'menu')]))


@bot.message_handler(commands=['help'])
def help_command(message: Message):
    bot.send_message(message.from_user.id, command_list)


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                            Меню управления опросами                            ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


@bot.message_handler(commands=['menu'])
@admin_permission
def menu_command(message: Message):
    bot.send_message(
        message.from_user.id,
        'Меню управления опросами',
        reply_markup=keyboard_builder(
            [('Создать новый', 'new_poll'), ('Мои отложенные', 'stashed_polls')],
            [('Активные', 'active_polls'), ('Архив', 'archive_polls')]))


@bot.callback_query_handler(lambda cb: cb.data.startswith('menu'))
@instant_callback_answer
@admin_permission
def menu_handler(callback: CallbackQuery):
    if len(callback.data.split(maxsplit=1)) > 1:
        param = callback.data.split(maxsplit=1)[1]
        if param == 'clear_new_poll':
            del new_creating_polls[callback.from_user.id]
    bot.edit_message_text(
        'Меню управления опросами:',
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder(
            [('Создать новый', 'new_poll'), ('Мои отложенные', 'stashed_polls')],
            [('Активные', 'active_polls'), ('Архив', 'archive_polls')]))


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                             Создание нового опроса                             ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


# def check_admin_id_in_new_creating_polls(func):
#     error_message = 'Ваш прогресс создания нового опроса был сброшен.\n' \
#                     'Возможно, это было вызвано перезапуском сервера.\n' \
#                     'Если вы уверены, что это ошибка бота, свяжитесь с разработчиками.'
#
#     def wrapper(cb_mes: CallbackQuery | Message, *args, **kwargs):
#         if cb_mes.from_user.id in new_creating_polls:
#             return func(cb_mes, *args, **kwargs)
#         if isinstance(cb_mes, CallbackQuery):
#             bot.answer_callback_query(cb_mes.id)
#             bot.edit_message_text(error_message,
#                                   cb_mes.message.chat.id,
#                                   cb_mes.message.id,
#                                   reply_markup=keyboard_builder([('Меню', 'menu')]))
#         elif isinstance(cb_mes, Message):
#             bot.send_message(cb_mes.from_user.id, error_message)
#
#     return wrapper


@bot.callback_query_handler(lambda cb: cb.data == 'new_poll')
@instant_callback_answer
def new_poll_handler(callback: CallbackQuery):
    new_creating_polls[callback.from_user.id] = Poll()
    bot.send_message(callback.from_user.id, 'Введите тему опроса')
    bot.register_next_step_handler(callback.message, poll_init_topic_handler)


def poll_init_topic_handler(message: Message):
    new_creating_polls[message.from_user.id].question = message.text.strip()
    bot.send_message(message.chat.id, 'Ведите варианты ответов (через точку с запятой [   ;   ])')
    bot.register_next_step_handler(message, poll_init_answers_handler)


# TODO: add validation
def poll_init_answers_handler(message: Message):
    poll = new_creating_polls[message.from_user.id]
    poll.answers = list(map(str.strip, message.text.split(';')))
    poll.stat = [0] * len(poll.answers)
    bot.send_message(message.from_user.id, 'Введите название соответствующего .csv файла')
    bot.register_next_step_handler(message, poll_init_filename_handler)


def poll_init_filename_handler(message: Message):
    filename = message.text.strip()
    if filename + '.json' in os.listdir('polls/active') or filename + '.json' in os.listdir('polls/archive'):
        bot.send_message(
            message.from_user.id,
            'Файл с таким названием уже существует, выберите другое название')
        bot.register_next_step_handler(message, poll_init_filename_handler)
        return
    filename_limit = 20  # callback.data is limited to 64 bytes
    if len(filename) > filename_limit:
        bot.send_message(
            message.from_user.id,
            f'Название слишком длинное (максимум {filename_limit} символов), выберите другое название')
        bot.register_next_step_handler(message, poll_init_filename_handler)
        return
    new_creating_polls[message.from_user.id].filename = filename
    bot.send_message(
        message.from_user.id,
        'Анонимность опроса:',
        reply_markup=keyboard_builder(
            [('Анонимный', 'new_poll_set_anon anon'), ('Открытый', 'new_poll_set_anon open')],
        ))


@bot.callback_query_handler(lambda cb: cb.data.startswith('new_poll_set_anon '))
@instant_callback_answer
def poll_init_anon_handler(callback: CallbackQuery):
    poll_type = callback.data.split(maxsplit=1)[1]
    if poll_type == 'anon':
        new_creating_polls[callback.from_user.id].anonymous = True
    elif poll_type == 'open':
        new_creating_polls[callback.from_user.id].anonymous = False
    bot.edit_message_text(
        'Возможность выбора нескольких вариантов:',
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder(
            [('Один вариант', 'new_poll_set_multi single'),
             ('Несколько вариантов', 'new_poll_set_multi multi')],
        ))


@bot.callback_query_handler(lambda cb: cb.data.startswith('new_poll_set_multi '))
@instant_callback_answer
def poll_init_multi_handler(callback: CallbackQuery):
    poll_type = callback.data.split(maxsplit=1)[1]
    poll = new_creating_polls[callback.from_user.id]
    if poll_type == 'multi':
        poll.multi_choice = True
    elif poll_type == 'single':
        poll.multi_choice = False

    bot.edit_message_text(
        str(poll) + f'\n\nПодтвердить создание опроса?',
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder(
            [('Подтвердить', 'confirm_new_poll')],
            [('Отмена', 'menu clear_new_poll')]),
        parse_mode='Markdown')


@bot.callback_query_handler(lambda cb: cb.data == 'confirm_new_poll')
@instant_callback_answer
def confirm_new_poll_handler(callback: CallbackQuery):
    if callback.from_user.id not in stashed_polls:
        stashed_polls[callback.from_user.id] = []
    stashed_polls[callback.from_user.id].append(new_creating_polls[callback.from_user.id])
    bot.edit_message_text(
        'Начать опрос сейчас?',
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder([('Да', 'start_new_poll'), ('Нет', 'stash_poll')]))


@bot.callback_query_handler(lambda cb: cb.data == 'stash_poll')
@instant_callback_answer
def stash_poll_handler(callback: CallbackQuery):
    del new_creating_polls[callback.from_user.id]
    bot.edit_message_text(
        'Опрос сохранен.',
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder([('Меню', 'menu')]))


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                        Управление отложенными опросами                         ║
# ╚════════════════════════════════════════════════════════════════════════════════╝

def check_admin_id_in_stash(func):
    def wrapper(callback: CallbackQuery, *args, **kwargs):
        if callback.from_user.id in stashed_polls:
            return func(callback, *args, **kwargs)
        bot.answer_callback_query(callback.id)
        bot.edit_message_text(
            'Ваши сохраненные опросы не найдены.\n'
            'Возможно, это было вызвано перезапуском сервера.\n',
            callback.message.chat.id,
            callback.message.id,
            reply_markup=keyboard_builder([('Меню', 'menu')]))

    return wrapper


def check_poll_index_in_stash(func):
    def wrapper(callback: CallbackQuery, *args, **kwargs):
        callback_separated = callback.data.split()
        if len(callback_separated) > 1:
            poll_id = callback_separated[1]
            if poll_id.isnumeric():
                poll_id = int(poll_id)
                if poll_id < len(stashed_polls[callback.from_user.id]):
                    return func(callback, *args, **kwargs)
        bot.answer_callback_query(callback.id)
        bot.edit_message_text(
            'Искомый опрос не найден.\n'
            'Возможно, это было вызвано перезапуском сервера.\n',
            callback.message.chat.id,
            callback.message.id,
            reply_markup=keyboard_builder([('Меню', 'menu')]))

    return wrapper


@bot.callback_query_handler(lambda cb: cb.data == 'stashed_polls')
@check_admin_id_in_stash
@instant_callback_answer
def stashed_polls_handler(callback: CallbackQuery):
    bot.edit_message_text(
        'Список отложенных опросов:',
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder(
            *map(
                lambda poll: [(poll[1].question, 'stashed_poll ' + str(poll[0]))],  # 13+NAME
                enumerate(stashed_polls[callback.from_user.id])),
            [('Назад', 'menu')],
            max_row_width=2))


@bot.callback_query_handler(lambda cb: cb.data.startswith('stashed_poll '))
@check_admin_id_in_stash
@check_poll_index_in_stash
@instant_callback_answer
def stashed_poll_handler(callback: CallbackQuery):
    poll_index = int(callback.data.split()[1])
    poll = stashed_polls[callback.from_user.id][poll_index]
    joiner = '\n- '
    bot.edit_message_text(
        f'Тема опроса:\n*{poll.question}*'
        f'\n\nВарианты ответов:{joiner + joiner.join(poll.answers)}'
        f'\n\nФайл: {poll.filename}.csv'
        f'\n\nАнонимный: {"Да" if poll.anonymous else "Нет"}'
        f'\nМультивыбор: {"Да" if poll.multi_choice else "Нет"}',
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder(
            [('Запустить', f'start_poll {poll_index}'),  # 11+INDEX
             ('Удалить', f'remove_stashed_poll {poll_index}')],  # 20+INDEX
            [('Назад', 'stashed_polls')]),
        parse_mode='Markdown')


@bot.callback_query_handler(lambda cb: cb.data.startswith('remove_stashed_poll '))
@check_admin_id_in_stash
@check_poll_index_in_stash
@instant_callback_answer
def remove_stashed_poll_handler(callback: CallbackQuery):
    del stashed_polls[callback.from_user.id][int(callback.data.split()[1])]
    bot.edit_message_text(
        'Опрос удален.',
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder([('Назад', 'stashed_polls')]))


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                                 Запуск опроса                                  ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


@bot.callback_query_handler(lambda cb: cb.data == 'start_new_poll')
@instant_callback_answer
def start_new_poll_handler(callback: CallbackQuery):
    if callback.from_user.id not in new_creating_polls:
        return
    bot.edit_message_text(
        'Опрос запущен',
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder([('Меню', 'menu')]), )
    start_poll(new_creating_polls.pop(callback.from_user.id))


@bot.callback_query_handler(lambda cb: cb.data.startswith('start_poll '))
@check_admin_id_in_stash
@check_poll_index_in_stash
@instant_callback_answer
def start_stashed_poll_handler(callback: CallbackQuery):
    bot.edit_message_text(
        'Опрос запущен',
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder([('Меню', 'menu')]), )
    start_poll(stashed_polls[callback.from_user.id].pop(int(callback.data.split()[1])))


def gen_m_poll_text_cb(poll: Poll, choice_state: list[int], index: int) -> tuple[str, str]:
    b_state = choice_state.copy()
    text = ('✅' if b_state[index] else '◻') + ' ' + poll.answers[index]
    b_state[index] = 1 - b_state[index]
    cb = ' '.join(('m_vote', poll.filename, ''.join(map(str, b_state))))
    return text, cb


def start_poll(poll: Poll):

    # Creating JSON
    poll.dump(f'polls/active/{poll.filename}.json')

    # Creating CSV
    if poll.anonymous:
        df = pd.DataFrame(columns=['id'])
    elif not poll.multi_choice:
        df = pd.DataFrame(columns=['id', 'answer'])
    else:
        df = pd.DataFrame(columns=['id'] + [index for index in range(len(poll.answers))])
    df.to_csv(f'polls/active/{poll.filename}.csv', index=False)

    # Generating keyboard
    if poll.multi_choice:
        init_choice_state = [0] * len(poll.answers)
        keyboard = keyboard_builder(
            *[[gen_m_poll_text_cb(poll, init_choice_state, index)] for index in range(len(poll.answers))],
            [('Подтвердить', ' '.join(('vote', poll.filename, ''.join(map(str, init_choice_state)))))])
    else:
        keyboard = keyboard_builder(
            *map(
                lambda ans: [(ans[1], f'vote {poll.filename} {str(ans[0])}')],
                enumerate(poll.answers)))

    # Sending poll
    subscribed = pd.read_csv('subscribed.csv')['id'].to_list()
    for receiver in subscribed:
        bot.send_message(
            receiver,
            poll.question,
            reply_markup=keyboard)


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                         Управление активными опросами                          ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


@bot.callback_query_handler(lambda cb: cb.data == 'active_polls')
@instant_callback_answer
def active_polls_handler(callback: CallbackQuery):
    polls = [name[:-5] for name in os.listdir('polls/active') if name.endswith('.json')]
    if not polls:
        bot.edit_message_text(
            'Список опросов пуст.',
            callback.message.chat.id,
            callback.message.id,
            reply_markup=keyboard_builder([('Меню', 'menu')]))
        return
    bot.edit_message_text(
        'Список активных опросов:',
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder(
            list(map(lambda poll: (poll, 'active_poll ' + poll), polls)),  # 12+NAME
            [('Назад', 'menu')],
        ))


@bot.callback_query_handler(lambda cb: cb.data.startswith('active_poll '))
@instant_callback_answer
def active_poll_handler(callback: CallbackQuery):
    poll = Poll.load(f'polls/active/{callback.data.split()[1]}.json')
    bot.edit_message_text(
        str(poll),
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder(
            [('Статистика', 'poll_stat a ' + callback.data.split()[1])],  # 12+NAME
            [('Завершить', 'stop_poll_sure ' + callback.data.split()[1])],  # 15+NAME
            [('Назад', 'active_polls')]),
        parse_mode='Markdown')


def get_poll_stat(poll: Poll) -> str:
    poll_stat = [(poll.answers[i], poll.stat[i]) for i in range(len(poll.answers))]
    sorted(poll_stat, key=lambda x: x[1], reverse=True)
    total_voices = sum(poll.stat)
    lines = []
    for ans_stat in poll_stat:
        line = f'{ans_stat[0]}: {ans_stat[1]}'
        if total_voices and len(poll_stat) > 1:
            line += f' ({ans_stat[1] * 100 // total_voices}%)'
        lines.append(line)
    return '- ' + '\n- '.join(lines)


# Works both with active and archive polls
@bot.callback_query_handler(lambda cb: cb.data.startswith('poll_stat '))
@instant_callback_answer
def poll_stat_handler(callback: CallbackQuery):
    poll_state = 'active' if callback.data.split()[1] == 'a' else 'archive'
    poll_name = callback.data.split()[2]
    poll = Poll.load(f'polls/{poll_state}/{poll_name}.json')
    bot.edit_message_text(
        get_poll_stat(poll),
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder([('Назад', f'{poll_state}_poll {poll_name}')]))


@bot.callback_query_handler(lambda cb: cb.data.startswith('stop_poll_sure '))
@instant_callback_answer
def stop_poll_sure_handler(callback: CallbackQuery):
    bot.edit_message_text(
        'Вы уверены, что хотите завершить опрос?'
        '\nОпрос будет помещен в архив и его нельзя будет восстановить.',
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder(
            [('Да', 'stop_poll ' + callback.data.split()[1]),  # 10+NAME
             ('Назад', 'active_poll ' + callback.data.split()[1])]))  # 12+NAME


@bot.callback_query_handler(lambda cb: cb.data.startswith('stop_poll '))
@instant_callback_answer
def stop_poll_handler(callback: CallbackQuery):
    poll = Poll.load(f'polls/active/{callback.data.split()[1]}.json')
    if not poll.anonymous:
        df = pd.read_csv(f'polls/active/{callback.data.split()[1]}.csv')
        df = df.drop_duplicates(subset='id')
        if poll.multi_choice:
            ser = df.iloc[:, 1:].sum()
            state_sums = [ser[index] for index in range(len(poll.answers))]
        else:
            ser = df['answer'].value_counts()
            state_sums = [0] * len(poll.answers)
            for index in ser.index:
                state_sums[index] = ser[index]
        state_sums = list(map(int, state_sums))
        if poll.stat != state_sums:
            print('Consistency repaired:', f'json stat: {poll.stat}', f'csv stat: {state_sums}', sep='\n')
            poll.stat = state_sums
            os.remove(f'polls/active/{poll.filename}.json')
            poll.dump(f'polls/active/{poll.filename}.json')

    os.replace(
        'polls/active/' + callback.data.split()[1] + '.json',
        'polls/archive/' + callback.data.split()[1] + '.json')
    os.replace(
        'polls/active/' + callback.data.split()[1] + '.csv',
        'polls/archive/' + callback.data.split()[1] + '.csv')
    bot.edit_message_text(
        'Опрос завершен.',
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder([('Назад', 'active_polls')]))


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                               Управление архивом                               ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


@bot.callback_query_handler(lambda cb: cb.data == 'archive_polls')
@instant_callback_answer
def archive_polls_handler(callback: CallbackQuery):
    polls = [name[:-5] for name in os.listdir('polls/archive') if name.endswith('.json')]
    if not polls:
        bot.edit_message_text(
            'Архив пуст.',
            callback.message.chat.id,
            callback.message.id,
            reply_markup=keyboard_builder([('Меню', 'menu')]))
        return
    bot.edit_message_text(
        'Список архивных опросов:',
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder(
            *[[(poll, 'archive_poll ' + poll)] for poll in polls],  # 14+NAME
            # list(map(lambda poll: (poll, 'archive_poll ' + poll), polls)),
            [('Меню', 'menu')]))


@bot.callback_query_handler(lambda cb: cb.data.startswith('archive_poll '))
@instant_callback_answer
def archive_poll_handler(callback: CallbackQuery):
    poll = Poll.load(f'polls/archive/{callback.data.split()[1]}.json')
    bot.edit_message_text(
        str(poll),
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder(
            [('Статистика', 'poll_stat h ' + callback.data.split()[1])],  # 12+NAME
            [('Назад', 'archive_polls')]),
        parse_mode='Markdown')


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
    subscribed = pd.read_csv('subscribed.csv')
    if message.from_user.id in subscribed['id'].values:
        bot.send_message(message.from_user.id, 'Вы уже подписаны на опросы')
        return
    subscribed = pd.concat([subscribed, pd.DataFrame([message.from_user.id], columns=['id'])])
    subscribed.to_csv('subscribed.csv', index=False)
    bot.send_message(message.from_user.id, 'Вы подписались на опросы')


@bot.message_handler(commands=['unsubscribe'])
def subscribe_command(message: Message):
    subscribed = pd.read_csv('subscribed.csv')
    if message.from_user.id not in subscribed['id'].values:
        bot.send_message(message.from_user.id, 'Вы не были подписаны на опросы')
        return
    subscribed = subscribed[subscribed['id'] != message.from_user.id]
    subscribed.to_csv('subscribed.csv', index=False)
    bot.send_message(message.from_user.id, 'Вы отписались от опросов')


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                               Обработка голосов                                ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


@bot.callback_query_handler(lambda cb: cb.data.startswith('m_vote '))
@instant_callback_answer
def m_vote_handler(callback: CallbackQuery):
    poll = Poll.load(f'polls/active/{callback.data.split()[1]}.json')
    choice_state = list(map(int, callback.data.split()[2]))
    bot.edit_message_text(
        poll.question,
        callback.message.chat.id,
        callback.message.id,
        reply_markup=keyboard_builder(
            *[[gen_m_poll_text_cb(poll, choice_state, index)] for index in range(len(poll.answers))],
            [('Подтвердить', ' '.join(('vote', poll.filename, ''.join(map(str, choice_state)))))],
        )
    )


@bot.callback_query_handler(lambda cb: cb.data.startswith('vote '))
def vote_handler(callback: CallbackQuery):
    filename, answer = callback.data.split(maxsplit=3)[1:]
    poll = Poll.load(f'polls/active/{filename}.json')
    if poll.multi_choice:
        answer = list(map(int, list(answer)))
    else:
        answer = int(answer)

    # CSV updating
    with open(f'polls/active/{filename}.csv', 'a', newline='', encoding='utf-8') as storage:
        if poll.anonymous:
            print(callback.from_user.id, file=storage)
        else:
            if poll.multi_choice:
                print(
                    callback.from_user.id,
                    *answer,
                    file=storage, sep=',')
            else:
                print(
                    callback.from_user.id,
                    answer,
                    file=storage, sep=',')

    # JSON updating
    if not poll.multi_choice:
        poll.stat[answer] += 1
    else:
        for index in range(len(poll.answers)):
            if answer[index]:
                poll.stat[index] += 1
    poll.dump(f'polls/active/{filename}.json')

    # Callback
    bot.answer_callback_query(callback.id, 'Спасибо, Ваш голос учтен!')
    bot.delete_message(callback.message.chat.id, callback.message.message_id)


# ╔════════════════════════════════════════════════════════════════════════════════╗
# ║                                   Служебное                                    ║
# ╚════════════════════════════════════════════════════════════════════════════════╝


@bot.message_handler(commands=['info'])
def echo_command(message: Message):
    print(
        f'\nID: {message.from_user.id}\n'
        f'Имя: {message.from_user.first_name}\n'
        f'Фамилия: {message.from_user.last_name}\n'
        f'Ссылка: @{message.from_user.username}\n')


@bot.message_handler(regexp=r'^/echo .+$')
def echo_command(message: Message):
    print(message.text[6:])


bot.infinity_polling()
