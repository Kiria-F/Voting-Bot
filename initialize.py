import json
import pandas as pd
import os

if 'config.json' not in os.listdir():

    bot_token = input('Input bot token >>> ')
    if bot_token.strip() == '':
        bot_token = dict(json.load(open('local_setup.json', encoding='utf-8'))).get('bot_token', '')

    bot_holder = input('Input bot holder id >>> ')
    if bot_holder == '':
        bot_holder = dict(json.load(open('local_setup.json', encoding='utf-8'))).get('bot_holder', '')
    bot_holder = int(bot_holder)

    json.dump({'bot_token': bot_token,
               'bot_holder': bot_holder,
               'admin_list': [bot_holder]},
              open("config.json", "w"),
              indent=4)

if 'polls' not in os.listdir():
    os.mkdir('polls')
if 'active' not in os.listdir('polls'):
    os.mkdir('polls/active')
if 'archive' not in os.listdir('polls'):
    os.mkdir('polls/archive')

if 'subscribed.csv' not in os.listdir():
    subscribed = pd.DataFrame(columns=['id'])
    subscribed.to_csv('subscribed.csv', index=False)
