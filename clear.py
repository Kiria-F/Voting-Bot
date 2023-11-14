import os

for file in os.listdir('polls'):
    os.remove(f'polls/{file}')
os.rmdir('polls')
os.remove('config.json')
os.remove('subscribed.csv')