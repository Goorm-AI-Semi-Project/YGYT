from selenium import webdriver
from selenium.webdriver.chrome.service import Service
import pandas as pd
import time

#크롬창 호출
driver = webdriver.Chrome() 

# 옵션 생성
options = webdriver.ChromeOptions()

# 옵션 추가
options.add_argument('disable-gpu') # GPU를 사용하지 않도록 설정
options.add_argument('headless')

driver.get('https://www.google.com/maps/') #띄워진 크롬창에 불러오고 싶은 주소 입력

searchbox = driver.find_element_by_css_selector('input#searchboxinput')
searchbox.send_keys('경주 맛집') # 키워드 입력

searchbutton = driver.find_element_by_css_selector("button#searchbox-searchbutton")
searchbutton.click()

#첫 번째 리스트의 가게 클릭
driver.find_element_by_xpath('//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div[1]/div[3]/div').click()

title = driver.find_element_by_xpath('//*[@id="QA0Szd"]/div/div/div[1]/div[3]/div/div[1]/div/div/div[2]/div[2]/div/div[1]/div[1]/h1').text
address = driver.find_element_by_xpath('//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[9]/div[3]/button/div/div[3]/div[1]').text

SCROLL_PAUSE_TIME = 2

# Get scroll height
last_height = driver.execute_script("return document.body.scrollHeight")
number = 0

while True:
    number = number+1

    # Scroll down to bottom
    scroll = driver.find_element_by_xpath('//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div[1]')
    driver.execute_script('arguments[0].scrollBy(0, 5000);', scroll)

    # Wait to load page
    time.sleep(SCROLL_PAUSE_TIME)

    # Calculate new scroll height and compare with last scroll height
    print(f'last height: {last_height}')
    scroll = driver.find_element_by_xpath('//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div[1]')
    new_height = driver.execute_script("return arguments[0].scrollHeight", scroll)

    print(f'new height: {new_height}')

    if number == 3:
        break

    if new_height == last_height:
        break

    print('cont')
    last_height = new_height
    
    title_ = []
address_ = []

for i in range(3, 100, 2):  
    time.sleep(1)
    SCROLL_PAUSE_TIME = 5
    
    global last_height
    global new_height
    
    # Get scroll height
    last_height = driver.execute_script("return document.body.scrollHeight")
    number = 0
    
    while True:
        number = number+1 
    
        # Scroll down to bottom
        scroll = driver.find_element_by_xpath('//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div[1]')
        driver.execute_script('arguments[0].scrollBy(0, 1000);', scroll)

        # Wait to load page
        time.sleep(SCROLL_PAUSE_TIME)

        # Calculate new scroll height and compare with last scroll height
        print(f'last height: {last_height}')
        scroll = driver.find_element_by_xpath('//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div[1]')
        new_height = driver.execute_script("return arguments[0].scrollHeight", scroll)

        print(f'new height: {new_height}')
        
        if number == i:
            break

        if new_height == last_height:
            break

        print('cont')
        last_height = new_height

    
    
    driver.find_element_by_xpath(f'//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div[1]/div[{i}]/div/a').click()
    time.sleep(2)
    
    title = driver.find_element_by_xpath('//*[@id="QA0Szd"]/div/div/div[1]/div[3]/div/div[1]/div/div/div[2]/div[2]/div/div[1]/div[1]/h1').text
    
    try:
        address = driver.find_element_by_xpath('//*[@id="QA0Szd"]/div/div/div[1]/div[3]/div/div[1]/div/div/div[2]/div[9]/div[3]/button/div/div[3]/div[1]').text
       
    except:
        address = 'na'
        rating = 'na'
        price = 'na'

    title_.append(title)
    address_.append(address)
   
    driver.back()     
    print('complete')
    
import pandas as pd
data = pd.DataFrame(data=[], columns = ['title', 'address'])

data['title'] = title_
data['address'] = address_