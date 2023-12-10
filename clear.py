import os

if 'polls' in os.listdir():
    if 'active' in os.listdir('polls'):
        for file in os.listdir('polls/active'):
            os.remove(f'polls/active/{file}')
        os.rmdir('polls/active')
    if 'archive' in os.listdir('polls'):
        for file in os.listdir('polls/archive'):
            os.remove(f'polls/archive/{file}')
        os.rmdir('polls/archive')
    os.rmdir('polls')
if 'config.json' in os.listdir():
    os.remove('config.json')
if 'subscribed.csv' in os.listdir():
    os.remove('subscribed.csv')
