from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, ElementNotInteractableException,
    NoSuchWindowException, StaleElementReferenceException
)
import ctypes
import time
import openpyxl as xl
import logging

logging.basicConfig(
    filename='autoSOC.log', 
    filemode="w", 
    level=logging.INFO,
    format='%(asctime)s -  %(levelname)s -  %(message)s'
)

class autoSOC:
    def __init__(self):
        self.driver = None
        self.user_name = None
        self.password = None
        self.time_delay = None
        self.SOC_id = None
        self.list_of_overrides = []
        self.msg_title = "Что-то пошло не так, скрипт будет завершен..."
        self.SOC_base_link = "http://eptw.sakhalinenergy.ru/SOC/EditOverrides/"
    
    def message_box(self, title, text, style):
        """Display Windows message box"""
        return ctypes.windll.user32.MessageBoxW(0, text, title, style)
    
    def load_config_from_excel(self):
        """Load configuration from Excel file"""
        try:
            wb = xl.load_workbook('overrides.xlsx')
            
            # Load settings
            sheet = wb['Settings']
            self.user_name = sheet.cell(1, 2).value
            self.password = sheet.cell(2, 2).value
            self.time_delay = float(sheet.cell(4, 2).value)
            
            # Load overrides
            sheet = wb['overrides']
            self.list_of_overrides = []
            
            for row in range(2, sheet.max_row + 1):
                if sheet.cell(row, 1).value in (None, ""):
                    break
                xlsx_override = {
                    "TagNumber": sheet.cell(row, 1).value,
                    "Description": sheet.cell(row, 2).value,
                    "OverrideType": sheet.cell(row, 4).value,
                    "OverrideMethod": sheet.cell(row, 5).value,
                    "Comment": sheet.cell(row, 3).value,
                    "AppliedState": sheet.cell(row, 6).value,
                    "AdditionalValueAppliedState": sheet.cell(row, 7).value,
                    "RemovedState": sheet.cell(row, 8).value,
                    "AdditionalValueRemovedState": sheet.cell(row, 9).value
                }
                self.list_of_overrides.append(xlsx_override)
            
            # Load SOC ID
            self.SOC_id = str(sheet.cell(1, 12).value)
            
            logging.info("✓ Configuration loaded successfully from Excel")
            
        except Exception as e:
            logging.error(f"❌ Error loading configuration from Excel: {e}")
            self.message_box("Error", f"Failed to load configuration: {e}", 0)
            raise
    
    def initialize_driver(self):
        """Initialize Chrome WebDriver"""
        try:
            self.driver = webdriver.Chrome()
            self.driver.maximize_window()
            logging.info("✓ WebDriver initialized successfully")
        except Exception as e:
            logging.error(f"❌ Error initializing WebDriver: {e}")
            raise
    
    def switch_lang_if_not_eng(self):
        """Switch to English if not already selected"""
        xpath = "//img[contains(@src,'/images/gb.jpg')]"
        try:
            self.driver.find_element(By.XPATH, xpath)
            logging.info("switch_lang_if_not_eng: English! Good!")
            return
        except NoSuchElementException:
            logging.info("switch_lang_if_not_eng: Not English! Not Good!")
            # FUTURE: switch to English here
            return
    
    def is_menu_item_already_selected(self, parent_id, menu_item_text):
        """Check if menu item is already selected"""
        item_xpath = (
            f"//ul[@id='{parent_id}']/li[text()='{menu_item_text}' and "
            f"contains(@class ,'k-item') and contains(@class ,'k-state-selected')]"
        )
        try:
            self.driver.find_element(By.XPATH, item_xpath)
            logging.info(f"is_menu_item_already_selected: item_xpath for '{menu_item_text}', '{parent_id}' is: '{item_xpath}'")
            return True
        except NoSuchElementException:
            return False
    
    def select_menu_item(self, parent_id, menu_item_text):
        """Select an item from a menu"""
        try:
            item_xpath = f"//ul[@id='{parent_id}']/li[text()='{menu_item_text}' and contains(@class ,'k-item')]"
            logging.info(f"select_menu_item: item_xpath for '{menu_item_text}', '{parent_id}' is: '{item_xpath}'")        
            
            ignored_exceptions = (NoSuchElementException, StaleElementReferenceException)
            element = WebDriverWait(
                self.driver, 5, ignored_exceptions=ignored_exceptions
            ).until(expected_conditions.element_to_be_clickable((By.XPATH, item_xpath)))

            time.sleep(self.time_delay)
            self.driver.execute_script("arguments[0].click();", element)
            
        except NoSuchElementException:
            logging.info(f"select_menu_item: NoSuchElementException, XPATH = '{item_xpath}'")
            self.message_box(self.msg_title, 'NoSuchElementException: ' + item_xpath, 0)
            self.quit()
        except TimeoutException as e:
            exception_name = type(e).__name__
            logging.info(f"select_menu_item: {exception_name}, XPATH = '{item_xpath}'")
            self.message_box(self.msg_title, f"{exception_name}: {item_xpath}", 0)
            self.quit()
        except ElementNotInteractableException as e:
            exception_name = type(e).__name__
            logging.info(f"select_menu_item: {exception_name}, XPATH = '{item_xpath}'")
            self.message_box(self.msg_title, f"{exception_name}: {item_xpath}", 0)
            self.quit()
        except NoSuchWindowException as e:
            exception_name = type(e).__name__
            logging.info(f"select_menu_item: {exception_name}, XPATH = '{item_xpath}'")
            self.quit()
        except StaleElementReferenceException as e:
            exception_name = type(e).__name__
            logging.info(f"select_menu_item: {exception_name}, XPATH = '{item_xpath}'")
            self.message_box(
                self.msg_title, 
                f"Исключение {exception_name}, можно нажать Confirm, чтобы сохранить те точки, "
                "которые уже добавлены, и запустить скрипт снова (предвариельно удалив уже "
                "добавленные точки из overrides.xslx)", 0
            )
            self.quit()
    
    def login(self):
        """Perform login to the application"""
        try:
            self.driver.get('http://eptw.sakhalinenergy.ru/')
            self.switch_lang_if_not_eng()
            
            self.driver.find_element(By.ID, "UserName").send_keys(self.user_name)
            self.driver.find_element(By.ID, "Password").send_keys(self.password)
            self.driver.find_element(
                By.XPATH, 
                "//button[@type='submit' and @class='panel-line-btn btn-sm k-button k-primary']"
            ).click()
            
            logging.info("✓ Login completed successfully")
            
        except Exception as e:
            logging.error(f"❌ Error during login: {e}")
            raise
    
    def navigate_to_edit_overrides(self):
        """Navigate to Edit Overrides page"""
        try:
            self.driver.get(self.SOC_base_link + self.SOC_id)
            logging.info(f"✓ Navigated to Edit Overrides page for SOC {self.SOC_id}")
            
            # Check if SOC is locked
            try:
                li_locked = self.driver.find_element(By.XPATH, "//li[contains(text(), 'Locked')]")
                self.message_box('SOC is locked, the script will be terminated', li_locked.text, 0)
                self.quit()
            except NoSuchElementException:
                pass
            
            # Check for Access Denied
            try:
                access_denied = self.driver.find_element(By.XPATH, "//h1[text()='Access Denied']")
                self.message_box(
                    access_denied.text, 
                    f'Access denied, probably SOC {self.SOC_id} is archived or in improper state', 0
                )
                self.quit()
            except NoSuchElementException:
                pass
                
        except Exception as e:
            logging.error(f"❌ Error navigating to Edit Overrides: {e}")
            raise
    
    def add_override(self, override):
        """Add a single override to the SOC"""
        try:
            # Enter Tag Number and Description
            self.driver.find_element(By.ID, "TagNumber").send_keys(override["TagNumber"])
            self.driver.find_element(By.ID, "Description").send_keys(override["Description"])
            
            # Select Override Type
            OverrideTypeIdMenu_XPATH = '//span[@aria-owns="OverrideTypeId_listbox"]'
            self.driver.find_element(By.XPATH, OverrideTypeIdMenu_XPATH).click()
            self.select_menu_item('OverrideTypeId_listbox', override["OverrideType"])
            
            # Select Override Method if not already selected
            if not self.is_menu_item_already_selected('OverrideMethodId_listbox', override["OverrideMethod"]):
                OverrideMethodMenu_XPATH = '//span[@aria-owns="OverrideMethodId_listbox"]'
                self.driver.find_element(By.XPATH, OverrideMethodMenu_XPATH).click()
                self.select_menu_item('OverrideMethodId_listbox', override["OverrideMethod"])
            
            # Enter Comment if provided
            if override["Comment"] is not None:
                self.driver.find_element(By.ID, "Comment").send_keys(override["Comment"])
            
            # Select Applied State
            AppliedStateMenu_XPATH = '//span[@aria-owns="OverrideAppliedStateId_listbox"]'
            self.driver.find_element(By.XPATH, AppliedStateMenu_XPATH).click()
            self.select_menu_item('OverrideAppliedStateId_listbox', override['AppliedState'])
            
            # Enter Additional Value Applied State if provided
            if override["AdditionalValueAppliedState"] is not None:
                try:
                    self.driver.find_element(By.ID, "AdditionalValueAppliedState").send_keys(
                        override["AdditionalValueAppliedState"]
                    )
                except ElementNotInteractableException as e:
                    exception_name = type(e).__name__
                    logging.info(f"send_keys() for element with ID 'AdditionalValueAppliedState': {exception_name}")
                    self.quit()
            
            # Select Removed State if provided and not already selected
            if override["RemovedState"] is not None:
                if not self.is_menu_item_already_selected('OverrideRemovedStateId_listbox', override["RemovedState"]):
                    RemovedStateMenu_XPATH = '//span[@aria-owns="OverrideRemovedStateId_listbox"]'
                    self.driver.find_element(By.XPATH, RemovedStateMenu_XPATH).click()
                    self.select_menu_item('OverrideRemovedStateId_listbox', override["RemovedState"])
            
            # Enter Additional Value Removed State if provided
            if override["AdditionalValueRemovedState"] is not None:
                self.driver.find_element(By.ID, "AdditionalValueRemovedState").send_keys(
                    override["AdditionalValueRemovedState"]
                )
            
            # Click Add button
            self.driver.find_element(By.ID, "AddOverrideBtn").click()
            
            logging.info(f"✓ Added override: {override['TagNumber']}")
            
        except Exception as e:
            logging.error(f"❌ Error adding override {override.get('TagNumber', 'Unknown')}: {e}")
            raise
    
    def process_all_overrides(self):
        """Process all overrides from the Excel file"""
        try:
            for i, override in enumerate(self.list_of_overrides, 1):
                logging.info(f"Processing override {i}/{len(self.list_of_overrides)}: {override['TagNumber']}")
                self.add_override(override)
            
            logging.info("✓ All overrides processed successfully")
            
        except Exception as e:
            logging.error(f"❌ Error processing overrides: {e}")
            raise
    
    def run(self):
        """Main method to run the automation"""
        try:
            logging.info("🚀 Starting autoSOC automation")
            
            self.load_config_from_excel()
            self.initialize_driver()
            self.login()
            self.navigate_to_edit_overrides()
            self.process_all_overrides()
            
            self.message_box('WARNING!!!', "Don't press OK UNTIL you press Confirm button!", 0)
            logging.info("✅ autoSOC automation completed successfully")
            
        except Exception as e:
            logging.error(f"❌ autoSOC automation failed: {e}")
            self.message_box("Error", f"Automation failed: {e}", 0)
        finally:
            self.quit()
    
    def quit(self):
        """Cleanup and quit the driver"""
        if self.driver:
            self.driver.quit()
            logging.info("✓ WebDriver closed")


# Main execution
if __name__ == "__main__":
    auto_soc = autoSOC()
    auto_soc.run()