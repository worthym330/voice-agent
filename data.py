from bs4 import BeautifulSoup
import requests


url = "https://wise.com/help/topics/5bVKT0uQdBrDp6T62keyfz/sending-money"

page = requests.get(url)

soup = BeautifulSoup(page.text,'html.parser')
var = soup.select_one('div',xpath='//*[@id="__next"]/div/div/main/div[2]/div/div/div[2]')


print(var)

