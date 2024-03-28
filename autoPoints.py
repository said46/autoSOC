from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
import ctypes

from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException

import time
import logging
import configparser

logging.basicConfig(filename='autoSOC.log', filemode="w", level=logging.INFO,
                    format='%(asctime)s -  %(levelname)s -  %(message)s')

def message_box(title, text, style):
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)

#  Styles:
#  0 : OK *** #  1 : OK | Cancel *** 2 : Abort | Retry | Ignore *** 3 : Yes | No | Cancel ***  
# 4 : Yes | No *** 5 : Retry | Cancel *** 6 : Cancel | Try Again | Continue

msg_title = "Что-то пошло не так, скрипт будет завершен..."

def switch_lang_if_not_eng():
    xpath = "//img[contains(@src,'/images/gb.jpg')]"
    try:
        driver.find_element(By.XPATH, xpath)
        # if gb.jpg is on the page, it's English, no actions required
        logging.info("switch_lang_if_not_eng: English! Good!")
        return
    except NoSuchElementException:
        # if gb.jpg is NOT on the page, it's not English, need to switch to it
        logging.info("switch_lang_if_not_eng: Not English! Not Good!")
        # FUTURE: switch to English here
        return

config = configparser.ConfigParser()
config.read('autoPoints.ini')

user_name = config['Settings']['user_name']
password = config['Settings']['password']

# number of SOC
SOC_id = config['Settings']['SOC_id']

SOC_roles = config['Roles']['SOC_roles'].split(',')

driver: WebDriver = webdriver.Chrome()

driver.get('http://eptw.sakhalinenergy.ru/')
driver.maximize_window()

# check if English is chosen, otherwise switch the language
switch_lang_if_not_eng()

# login
driver.find_element(By.ID, "UserName").send_keys(user_name)
driver.find_element(By.ID, "Password").send_keys(password)
driver.find_element(By.XPATH, "//button[@type='submit' and @class='panel-line-btn btn-sm k-button k-primary']").click()

SOC_view_base_link = "http://eptw.sakhalinenergy.ru/Soc/Details/"
driver.get(SOC_view_base_link + SOC_id) # http://eptw.sakhalinenergy.ru/Soc/Details/1458894

good_statuses = ['accepted for apply', 'requested for removal', 'applied, not verified', 'removed, not verified']

try: 
    # item_xpath = "//label[@for='CertificateState']/.."
    cmd = """return document.evaluate("//label[@for='CertificateState']/following-sibling::text()", document, null, """ \
          """ XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.textContent;"""

    SOC_status = driver.execute_script(cmd).strip().lower()

except Exception as e:
    logging.info(f"{str(e)}")
    message_box(msg_title, f"{str(e)}", 0)
    quit()

if SOC_status not in good_statuses:
    message_box('Error', f'SOC status is "{SOC_status}", the script will be terminated', 0)
    quit()

for SOC_role in SOC_roles:
    driver.get(r"http://eptw.sakhalinenergy.ru/User/ChangeRole")
    input_text = driver.find_element(By.ID, 'CurrentRoleName')
    driver.execute_script(f'arguments[0].value="{SOC_role}"', input_text)
    # driver.execute_script("arguments[0].style.display = 'block';", input_text)
    driver.find_element(By.ID, 'ConfirmHeader').click()

    # navigate to Edit Overrides page
    SOC_update_base_link = "http://eptw.sakhalinenergy.ru/Soc/UpdateOverride/"
    driver.get(SOC_update_base_link + SOC_id) #example: http://eptw.sakhalinenergy.ru/Soc/UpdateOverride/1458894

    # check if the SOC is locked
    try:
        li_locked = driver.find_element(By.XPATH, "//li[contains(text(), 'Locked')]")
        message_box('SOC is locked, the script will be terminated', li_locked.text, 0)
        quit()
    except NoSuchElementException:
        # the pass is put here on purpose
        pass

    # check for Access Denied
    try:
        access_denied = driver.find_element(By.XPATH, "//h1[text()='Access Denied']")
        message_box(access_denied.text, f'Access denied, probably SOC {SOC_id} is archived or in improper state', 0)
        quit()
    except NoSuchElementException:
        # the pass is put here on purpose
        pass

    time.sleep(1)

    try:
        # item_xpath = f"//select[@id='CurrentStateSelect']"
        sel_items = driver.find_elements(By.ID, 'CurrentStateSelect')
        for sel_item in sel_items:
            drop = Select(sel_item)
            drop.select_by_index(1) # Applied
    except NoSuchElementException as e:
        logging.info(f"{str(e)}")
        message_box(msg_title, f"{str(e)}", 0)
        quit()

    message_box('WARNING!!!', "Don't press OK UNTIL you press Confirm button!", 0)

driver.quit()