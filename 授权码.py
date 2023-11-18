import json
import time
import requests
import urllib.parse
from selenium import webdriver
from selenium.webdriver.common.by import By

# 输入必要信息
client_id = "" # 此处填入您应用的AppKey
device_id = "" # 此处填入您应用的AppID
client_secret = "" # 此处填入您应用的SecretKey
""" 
以上必填信息请根据 https://pan.baidu.com/union/doc/ol0rsap9s 在 https://pan.baidu.com/union/console/applist 中获取
"""

# 获取授权页面
code_url = "http://openapi.baidu.com/oauth/2.0/authorize?response_type=code&client_id=" + urllib.parse.quote(client_id) + "&redirect_uri=oob&scope=basic,netdisk&qrcode=1"
code_response = requests.request("GET", code_url)


driver = webdriver.Chrome()
# driver.set_page_load_timeout(20) # 设置页面加载超时时间

try:
    driver.get(code_response.url)
except Exception:
    pass

element = driver.find_element( By.XPATH , "/html/body/section/div/div/div[1]/h3" )
text = element.text

# 寻找授权码code
while text != "找到了！":
    try:
        driver.find_element( By.XPATH , "//*[@id='d_clip_button']" ).text
        text = "找到了！"
    except:
        time.sleep(1)
 
element = driver.find_element( By.XPATH , "//*[@id='Verifier']" )
code = element.get_attribute("value")

# 获取Access_token
url = "https://openapi.baidu.com/oauth/2.0/token?grant_type=authorization_code&code=" + code + "&client_id=" + client_id + "&client_secret=" + client_secret + "&redirect_uri=oob"

payload = {}
headers = {
  'User-Agent': 'pan.baidu.com'
}

response = requests.request("GET", url, headers=headers, data = payload)

s = json.loads(response.text.encode('utf8')) # 解析获取的json

print ("您的授权码为：",s["access_token"]) # 提取access_token的值

input()