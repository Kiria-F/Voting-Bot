import json
import pandas as pd
import os

bot_token = input('Input bot token >>> ')
bot_holder = int(input('Input bot holder id >>> '))
json.dump({'bot_token': bot_token,
           'bot_holder': bot_holder,
           'admin_list': [bot_holder]},
          open("config.json", "w"),
          indent=4)

if 'polls' not in os.listdir():
    os.mkdir('polls')

subscribed = pd.DataFrame(columns=['id'])
subscribed.to_csv('subscribed.csv', index=False)
