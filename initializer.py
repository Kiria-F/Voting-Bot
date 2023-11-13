import openpyexcel as xl
import json
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

wb = xl.Workbook()
sheet = wb.active
sheet['A2'] = 'next_id'
sheet['B2'] = 1
wb.save('stat.xlsx')

xl.Workbook().save('subscribed.xlsx')
