import openpyexcel as xl
import json

bot_token = input('Input bot token >>> ')
bot_holder = int(input('Input bot holder id >>> '))
json.dump({'bot_token': bot_token,
           'bot_holder': bot_holder,
           'admin_list': [bot_holder]},
          open("config.json", "w"),
          indent=4)

wb = xl.Workbook()
sheet = wb.active
sheet['B1'] = 1
wb.save('stat.xlsx')

xl.Workbook().save('subscribed.xlsx')
