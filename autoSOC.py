from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
import ctypes

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import ElementNotInteractableException
from selenium.common.exceptions import NoSuchWindowException
from selenium.common.exceptions import StaleElementReferenceException

import time
import openpyxl as xl

import logging

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

def is_menu_item_already_selected(parent_id, menu_item_text):
    # find <li> element with particular text and class containing 'k-item' and 'k-state-selected'
    # that element must have parent tag <ul> with id=parent_id
    item_xpath = f"//ul[@id='{parent_id}']/li[text()='{menu_item_text}' and contains(@class ,'k-item') and "\
                  "contains(@class ,'k-state-selected')]"
    try:
        driver.find_element(By.XPATH, item_xpath)
        logging.info(f"is_menu_item_already_selected: item_xpath for '{menu_item_text}', '{parent_id}' is: '{item_xpath}'")
        return True
    except NoSuchElementException:
        return False

def select_menu_item(parent_id, menu_item_text):
    # find <li> element with particular text and class containing 'k-item'
    # that element must have parent tag <ul> with id=parent_id
    try:
        item_xpath = f"//ul[@id='{parent_id}']/li[text()='{menu_item_text}' and contains(@class ,'k-item')]"
        logging.info(f"select_menu_item: item_xpath for '{menu_item_text}', '{parent_id}' is: '{item_xpath}'")        
        ignored_exceptions = (NoSuchElementException, StaleElementReferenceException)
        element = WebDriverWait(driver, 5, ignored_exceptions=ignored_exceptions).until(\
            expected_conditions.element_to_be_clickable((By.XPATH, item_xpath)))

        # this delay might be configurable, it is not required, but for some reason some menu items
        # are selected incorrectly without raising NoSuchElementException for the next menu
        # because dependencies become broken
        time.sleep(time_delay)

        # test variant via JavaScript
        driver.execute_script("arguments[0].click();", element)

        # main variant of clicking
        # element.click()

    except NoSuchElementException:
        logging.info(f"select_menu_item: NoSuchElementException, XPATH = '{item_xpath}'")
        message_box(msg_title, 'NoSuchElementException: ' + item_xpath, 0)
        quit()
    except TimeoutException as e:
        exception_name = type(e).__name__
        logging.info(f"select_menu_item: {exception_name}, XPATH = '{item_xpath}'")
        message_box(msg_title, f"{exception_name}: {item_xpath}", 0)
        quit()
    except ElementNotInteractableException as e:
        exception_name = type(e).__name__
        logging.info(f"select_menu_item: {exception_name}, XPATH = '{item_xpath}'")
        message_box(msg_title, f"{exception_name}: {item_xpath}", 0)
        quit()
    except NoSuchWindowException as e:
        exception_name = type(e).__name__
        logging.info(f"select_menu_item: {exception_name}, XPATH = '{item_xpath}'")
        quit()
    except StaleElementReferenceException as e:
        exception_name = type(e).__name__
        logging.info(f"select_menu_item: {exception_name}, XPATH = '{item_xpath}'")
        message_box(msg_title, f"Исключение {exception_name}, можно нажать Confirm, чтобы сохранить те точки, "\
                                "которые уже добавлены, и запустить скрипт снова (предвариельно удалив уже "\
                                "добавленные точки из overrides.xslx)", 0)
        quit()


wb = xl.load_workbook('overrides.xlsx')

sheet = wb['Settings']
user_name = sheet.cell(1, 2).value
password = sheet.cell(2, 2).value
time_delay = float(sheet.cell(4, 2).value)

sheet = wb['overrides']

list_of_overrides = []
for row in range(2, sheet.max_row + 1):
    if sheet.cell(row, 1).value in (None, ""):
        break
    xlsx_override = {"TagNumber": sheet.cell(row, 1).value, "Description": sheet.cell(row, 2).value,
                     "OverrideType": sheet.cell(row, 4).value, "OverrideMethod": sheet.cell(row, 5).value,
                     "Comment": sheet.cell(row, 3).value, "AppliedState": sheet.cell(row, 6).value,
                     "AdditionalValueAppliedState": sheet.cell(row, 7).value, "RemovedState": sheet.cell(row, 8).value,
                     "AdditionalValueRemovedState": sheet.cell(row, 9).value}
    list_of_overrides.append(xlsx_override)

# number of SOC
SOC_id = str(sheet.cell(1, 12).value)

driver: WebDriver = webdriver.Chrome()

driver.get('http://eptw.sakhalinenergy.ru/')
driver.maximize_window()

# check if English is chosen, otherwise switch the language
switch_lang_if_not_eng()

# login
driver.find_element(By.ID, "UserName").send_keys(user_name)
driver.find_element(By.ID, "Password").send_keys(password)
driver.find_element(By.XPATH, "//button[@type='submit' and @class='panel-line-btn btn-sm k-button k-primary']").click()

# navigate to Edit Overrides page
SOC_base_link = "http://eptw.sakhalinenergy.ru/SOC/EditOverrides/"
driver.get(SOC_base_link + SOC_id) #example: http://eptw.sakhalinenergy.ru/SOC/EditOverrides/1489636

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


for override in list_of_overrides:
    # print Tag Number and Description
    try:
        driver.find_element(By.ID, "TagNumber").send_keys(override["TagNumber"])
        driver.find_element(By.ID, "Description").send_keys(override["Description"])
    except NoSuchElementException as e:
        logging.info(f"{str(e)}")
        message_box(msg_title, f"{str(e)}", 0)
        quit()

    # click override type menu and select override type item
    OverrideTypeIdMenu_XPATH = '//span[@aria-owns="OverrideTypeId_listbox"]'
    try:
        driver.find_element(By.XPATH, OverrideTypeIdMenu_XPATH).click()
    except NoSuchElementException as e:
        exception_name = type(e).__name__
        logging.info(f"OverrideTypeId_listbox click(): {exception_name}, XPATH = '{OverrideTypeIdMenu_XPATH}'")
        message_box(msg_title, f"{exception_name}: {OverrideTypeIdMenu_XPATH}", 0)
        quit()
    except NoSuchWindowException:
        quit()
    select_menu_item('OverrideTypeId_listbox', override["OverrideType"])

    # click override method menu and select override method item
    # is_menu_item_already_selected function checks if the menu item
    # has already been chosen automatically
    if not is_menu_item_already_selected('OverrideMethodId_listbox', override["OverrideMethod"]):
        OverrideMethodMenu_XPATH = '//span[@aria-owns="OverrideMethodId_listbox"]'
        try:
            driver.find_element(By.XPATH, OverrideMethodMenu_XPATH).click()
        except NoSuchElementException as e:
            exception_name = type(e).__name__
            logging.info(f"OverrideMethodId_listbox click(): {exception_name}, XPATH = '{OverrideMethodMenu_XPATH}'")
            message_box(msg_title, f'{exception_name}: {OverrideMethodMenu_XPATH}', 0)
            quit()
        except NoSuchWindowException as e:            
            exception_name = type(e).__name__
            logging.info(f"OverrideMethodId_listbox click(): {exception_name}, XPATH = '{OverrideMethodMenu_XPATH}'")
            quit()
        select_menu_item('OverrideMethodId_listbox', override["OverrideMethod"])

    # print Comment
    if override["Comment"] is not None:
        driver.find_element(By.ID, "Comment").send_keys(override["Comment"])

    # click applied state menu and select the required item
    AppliedStateMenu_XPATH = '//span[@aria-owns="OverrideAppliedStateId_listbox"]'
    try:
        driver.find_element(By.XPATH, AppliedStateMenu_XPATH).click()
    except NoSuchElementException as e:
        exception_name = type(e).__name__
        logging.info(f"OverrideAppliedStateId_listbox click(): {exception_name}, XPATH = '{AppliedStateMenu_XPATH}'")
        message_box(msg_title, f'exception_name: {AppliedStateMenu_XPATH}', 0)
        quit()
    except NoSuchWindowException as e:
        exception_name = type(e).__name__
        logging.info(f"OverrideAppliedStateId_listbox click(): {exception_name}, XPATH = '{AppliedStateMenu_XPATH}'")
        quit()
    select_menu_item('OverrideAppliedStateId_listbox', override['AppliedState'])

    # AdditionalValueAppliedState
    if override["AdditionalValueAppliedState"] is not None:
        try:
            driver.find_element(By.ID, "AdditionalValueAppliedState").send_keys(override["AdditionalValueAppliedState"])
        except ElementNotInteractableException as e:
            exception_name = type(e).__name__
            logging.info(f"send_keys() for element with ID 'AdditionalValueAppliedState': {exception_name}")
            quit()
            
    # click Removed state menu and select the required item
    # 1. it is not required if RemovedState is not defined for the override
    # 2. is_menu_item_already_selected function checks if the menu item
    #    has already been chosen automatically
    if override["RemovedState"] is not None:
        if not is_menu_item_already_selected('OverrideRemovedStateId_listbox', override["RemovedState"]):
            RemovedStateMenu_XPATH = '//span[@aria-owns="OverrideRemovedStateId_listbox"]'
            try:
                element = driver.find_element(By.XPATH, RemovedStateMenu_XPATH)
            except NoSuchElementException as e:
                exception_name = type(e).__name__
                logging.info(f"OverrideRemovedStateId_listbox click(): {exception_name}, XPATH = '{RemovedStateMenu_XPATH}'")
                message_box(msg_title, f'{exception_name}: {RemovedStateMenu_XPATH}', 0)
                quit()
            except NoSuchWindowException as e:
                exception_name = type(e).__name__
                logging.info(f"OverrideRemovedStateId_listbox click(): {exception_name}, XPATH = '{RemovedStateMenu_XPATH}'")
                quit()
            select_menu_item('OverrideRemovedStateId_listbox', override["RemovedState"])

    # AdditionalValueRemovedState
    if override["AdditionalValueRemovedState"] is not None:
        driver.find_element(By.ID, "AdditionalValueRemovedState").send_keys(override["AdditionalValueRemovedState"])

    # press Add button
    driver.find_element(By.ID, "AddOverrideBtn").click()

message_box('WARNING!!!', "Don't press OK UNTIL you press Confirm button!", 0)

driver.quit()