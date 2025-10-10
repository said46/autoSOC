# soc_importer.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, ElementNotInteractableException,
    NoSuchWindowException
)
import time
import openpyxl as xl
import json
import configparser

import logging

from base_web_bot import BaseWebBot
from soc_base_mixin import SOC_BaseMixin

class SOC_Importer(BaseWebBot, SOC_BaseMixin):
    def __init__(self):
        BaseWebBot.__init__(self)
        SOC_BaseMixin.__init__(self)
        self.load_configuration()  # Load from SOC.ini
        # SOC_base_link will be constructed from the configured base_link
        self.SOC_base_link = self.base_link + r"Soc/EditOverrides/"
        self.EXPECTED_HOME_PAGE_TITLE = "СНД - Домашняя страница"    

    @property
    def base_link(self) -> str:
        return self._base_link

    def load_configuration(self) -> None:
        """
        Load configuration settings from SOC.ini file
        """

        config = configparser.ConfigParser(interpolation=None)
        config.read(self.config_file, encoding="utf8")

        # Load user credentials from Settings section
        self.user_name = config.get('Settings', 'user_name', fallback='xxxxxx')
        
        # Use mixin's password processing for consistent password handling
        raw_password = config.get('Settings', 'password', fallback='******')
        self.password = self.process_password(raw_password)
        
        # Validate password processing
        if '\n' in self.password:
            self.password = 'INCORRECT PASSWORD'
            
        # Load base link for navigation
        self._base_link = config.get('Settings', 'base_link', fallback='http://eptw.sakhalinenergy.ru/')
        
        # Load timing configuration
        self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_PAGE_LOAD_DELAY_SECONDS', fallback=20)
        self.MAX_WAIT_USER_INPUT_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_USER_INPUT_DELAY_SECONDS', fallback=300)
        
        logging.info(f"✅ Configuration loaded from {self.config_file}")
    
    def load_config_from_excel(self):
        """Load configuration from Excel file with new structure"""
        try:
            logging.info("📂 Loading Excel configuration...")
            wb = xl.load_workbook('soc_resources/overrides.xlsx')
            
            # Get the first sheet (assuming it's the main data sheet)
            sheet = wb.active
            logging.info(f"📊 Using sheet: '{sheet.title}' with {sheet.max_row} rows")
            
            # Load overrides from the new structure
            self.list_of_overrides = []
            
            # Map the new Excel columns to our expected structure
            # A: Ид. форсировки (Override ID) - we'll ignore this as it's auto-generated
            # B: Бирка № (Tag Number)
            # C: Описание (Description) 
            # D: Комментарий (Comment)
            # E: Установленное состояние (Applied State)
            # F: Текущее состояние (Current State) - empty in your file
            # G: Удаленное состояние (Removed State)
            
            for row in range(2, sheet.max_row + 1):  # Start from row 2 (skip header)
                tag_number = sheet.cell(row, 2).value  # Column B
                if tag_number in (None, ""):
                    logging.info(f"🛑 Empty tag number at row {row}, stopping override loading")
                    break
                    
                # Extract values from the new structure
                description = sheet.cell(row, 3).value  # Column C
                comment = sheet.cell(row, 4).value      # Column D
                applied_state = sheet.cell(row, 5).value  # Column E
                removed_state = sheet.cell(row, 7).value  # Column G
                
                # Map to our existing override structure
                xlsx_override = {
                    "TagNumber": tag_number,
                    "Description": description or "FLT STATUS",  # Default if empty
                    "OverrideType": "Digital",  # Default based on FLT STATUS
                    "OverrideMethod": "Forced",  # Default based on "Форсировано"
                    "Comment": comment,
                    "AppliedState": applied_state or "Форсировано",  # Default from column E
                    "AdditionalValueAppliedState": None,  # Not in new structure
                    "RemovedState": removed_state or "Расфорсировано",  # Default from column G
                    "AdditionalValueRemovedState": None  # Not in new structure
                }
                self.list_of_overrides.append(xlsx_override)
            
            # Try to find SOC ID - might be in a different location now
            self.SOC_id = None
            soc_id_candidates = [
                (1, 1),  # A1
                (1, 2),  # B1  
                (1, 3),  # C1
                (2, 1),  # A2
            ]
            
            for row, col in soc_id_candidates:
                try:
                    candidate = sheet.cell(row, col).value
                    if candidate and str(candidate).strip():
                        self.SOC_id = str(candidate).strip()
                        logging.info(f"🔍 Found SOC ID at cell ({row},{col}): {self.SOC_id}")
                        break
                except:
                    continue
            
            if not self.SOC_id:
                logging.warning("⚠️  SOC ID not found in Excel, will need user input")
            else:
                logging.info(f"✅ SOC ID loaded: {self.SOC_id}")
            
            logging.info(f"✅ Configuration loaded successfully from Excel, {len(self.list_of_overrides)} overrides to add")                            
        except Exception as e:
            logging.error(f"❌ Failed to load configuration from Excel: {e}")
            self.inject_error_message("❌ Failed to load configuration from Excel")
            raise
    
    def get_kendo_selected_item(self, element_id: str) -> dict:
        """Get currently selected item from Kendo dropdown"""
        script = """
        var dropdown = $('#%s').data('kendoDropDownList');
        if (dropdown) {
            var selected = dropdown.dataItem();
            return selected ? JSON.stringify(selected) : null;
        }
        return null;
        """ % element_id
        
        try:
            result = self.driver.execute_script(script)
            return json.loads(result) if result else {}
        except Exception as e:
            logging.error(f"❌ Failed to get selected item: {e}")
            return {}    
    
    def get_kendo_dropdown_data(self, element_id: str) -> list[dict]:
        """Get Kendo DropDownList data as list of dictionaries"""
        script = """
            var dropdown = $('#%s').data('kendoDropDownList');
            if (dropdown) {
                var data = dropdown.dataItems();
                return JSON.stringify(data);
            }
            return null;
        """ % element_id

        try:
            result = self.driver.execute_script(script)
            if result:
                return json.loads(result)
            return []
        except Exception as e:
            logging.error(f"❌ Failed to get Kendo dropdown data: {e}")
            return []
    
    def set_kendo_dropdown_value(self, element_id: str, value: str) -> bool:
        """Set Kendo dropdown value using Kendo API"""
        script = """
            var dropdown = $('#%s').data('kendoDropDownList');
            if (dropdown) {
                dropdown.value(arguments[0]);
                dropdown.trigger('change');
                return true;
            }
            return false;
        """ % element_id
        
        try:
            result = self.driver.execute_script(script, value)
            if result:
                # Wait for value to be set
                WebDriverWait(self.driver, 5).until(
                    lambda _: self.driver.execute_script(
                        "return $('#%s').data('kendoDropDownList').value() === arguments[0];" % element_id,
                        value
                    )
                )
                logging.info(f"✅ Kendo dropdown {element_id} set to: {value}")
                return True
            return False
        except Exception as e:
            logging.error(f"❌ Failed to set Kendo dropdown {element_id}: {e}")
            return False
    
    def wait_for_kendo_dropdown_ready(self, element_id: str, timeout: int = 10) -> bool:
        """Wait for Kendo dropdown to be initialized and ready"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda _: self.driver.execute_script(
                    "return $('#%s').data('kendoDropDownList') !== undefined;" % element_id
                )
            )
            logging.info(f"✅ Kendo dropdown {element_id} is ready")
            return True
        except TimeoutException:
            logging.error(f"❌ Kendo dropdown {element_id} not ready within {timeout} seconds")
            return False
    
    def select_kendo_dropdown_by_text(self, element_id: str, text: str) -> bool:
        """Select Kendo dropdown item by displayed text"""
        try:
            # Wait for dropdown to be ready
            if not self.wait_for_kendo_dropdown_ready(element_id):
                return False
            
            # Get all dropdown data to find matching item
            dropdown_data = self.get_kendo_dropdown_data(element_id)
            if not dropdown_data:
                logging.error(f"❌ No data available in dropdown {element_id}")
                return False
            
            # Find item with matching text
            matching_item = None
            for item in dropdown_data:
                if item.get('Text') == text:
                    matching_item = item
                    break
            
            if not matching_item:
                logging.error(f"❌ Item with text '{text}' not found in dropdown {element_id}")
                logging.debug(f"Available items: {[item.get('Text') for item in dropdown_data]}")
                return False
            
            # Set the value using Kendo API
            value = matching_item.get('Value') or matching_item.get('Text')
            return self.set_kendo_dropdown_value(element_id, value)
            
        except Exception as e:
            logging.error(f"❌ Failed to select '{text}' in dropdown {element_id}: {e}")
            return False
    
    def initialize_and_login(self):
        """Initialize the bot and perform login using mixin methods"""
        self.navigate_to_base()
        self.perform_login()
    
    def wait_for_soc_input_and_complete_login(self):
        """Wait for SOC ID input and complete the login process"""
        soc_id = self.wait_for_soc_input_and_submit()
        if soc_id:
            self.submit_form_with_soc_id(soc_id)
        return soc_id
      
    def navigate_to_edit_overrides(self):
        """Navigate to Edit Overrides page"""
        try:
            self.driver.get(self.SOC_base_link + self.SOC_id)
            logging.info(f"👆 Navigated to Edit Overrides page for SOC {self.SOC_id}")                           
        except Exception as e:
            logging.error(f"❌ Error navigating to Edit Overrides: {e}")
            raise
    
    def add_override(self, override: dict[str, str]) -> None:
        """Add a single override to the SOC using Kendo API methods"""
        try:
            # Enter Tag Number and Description
            self.driver.find_element(By.ID, "TagNumber").send_keys(override["TagNumber"])
            self.driver.find_element(By.ID, "Description").send_keys(override["Description"])
            
            # Select Override Type using Kendo API
            if not self.select_kendo_dropdown_by_text("OverrideTypeId", override["OverrideType"]):
                logging.error(f"❌ Failed to set OverrideType: {override['OverrideType']}")
                raise Exception(f"Failed to set OverrideType: {override['OverrideType']}")
            
            # Select Override Method using Kendo API
            if not self.select_kendo_dropdown_by_text("OverrideMethodId", override["OverrideMethod"]):
                logging.error(f"❌ Failed to set OverrideMethod: {override['OverrideMethod']}")
                raise Exception(f"Failed to set OverrideMethod: {override['OverrideMethod']}")
            
            # Enter Comment if provided
            if override["Comment"] is not None:
                self.driver.find_element(By.ID, "Comment").send_keys(override["Comment"])
            
            # Select Applied State using Kendo API
            if not self.select_kendo_dropdown_by_text("OverrideAppliedStateId", override["AppliedState"]):
                logging.error(f"❌ Failed to set AppliedState: {override['AppliedState']}")
                raise Exception(f"Failed to set AppliedState: {override['AppliedState']}")
            
            # Enter Additional Value Applied State if provided
            if override["AdditionalValueAppliedState"] is not None:
                try:
                    self.driver.find_element(By.ID, "AdditionalValueAppliedState").send_keys(
                        override["AdditionalValueAppliedState"]
                    )
                except ElementNotInteractableException as e:
                    logging.error(f"❌ Failed to set AdditionalValueAppliedState: {e}")
                    raise
            
            # Select Removed State if provided using Kendo API
            if override["RemovedState"] is not None:
                if not self.select_kendo_dropdown_by_text("OverrideRemovedStateId", override["RemovedState"]):
                    logging.error(f"❌ Failed to set RemovedState: {override['RemovedState']}")
                    raise Exception(f"Failed to set RemovedState: {override['RemovedState']}")
            
            # Enter Additional Value Removed State if provided
            if override["AdditionalValueRemovedState"] is not None:
                self.driver.find_element(By.ID, "AdditionalValueRemovedState").send_keys(
                    override["AdditionalValueRemovedState"]
                )
            
            # Click Add button
            self.driver.find_element(By.ID, "AddOverrideBtn").click()
            
            logging.info(f"✅ Added override: {override['TagNumber']}")
            
        except Exception as e:
            logging.error(f"❌ Error adding override {override.get('TagNumber', 'Unknown')}: {e}")
            raise
    
    def process_all_overrides(self):
        """Process all overrides from the Excel file"""
        logging.info(f"📋 Starting to process {len(self.list_of_overrides)} overrides")
        try:
            for i, override in enumerate(self.list_of_overrides, 1):
                logging.info(f"🔄 Processing override {i}/{len(self.list_of_overrides)}: {override['TagNumber']}")           
                self.add_override(override)
                logging.info(f"✅ Successfully processed override {i}: {override['TagNumber']}")

            logging.info("✅ All overrides processed successfully")
            
        except Exception as e:
            logging.error(f"❌ Error processing overrides: {e}")
            raise

        self.wait_for_user_confirmation()
    
    def wait_for_user_confirmation(self):
        """Wait for user to press confirm button"""
        msg = '⚠️  Скрипт ожидает нажатия кнопки "Подтвердить".'
        xpath = "//div[@id='bottomWindowButtons']/div"
        self.inject_info_message(msg, (By.XPATH, xpath), {'color': 'lawngreen'})
        try:
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(EC.title_is(self.EXPECTED_HOME_PAGE_TITLE))
            logging.info("🏁  Confirm pressed, home page loaded")
        except NoSuchWindowException as e:
            logging.error(f"⚠️  User closed the browser window.")
            self.safe_exit()
        except Exception as e:
            logging.error(f"❌ Failed to wait for user input ('Confirm' button): {str(e)}")
            self.inject_error_message(f"❌ Failed to wait for user input ('Confirm' button)")
    
    def run(self):
        """Main method to run the automation"""
        try:            
            self.load_config_from_excel()
            
            logging.info("🚀 Starting SOC_Importer automation")
            
            self.initialize_and_login()
            self.wait_for_soc_input_and_complete_login()
            self.navigate_to_edit_overrides()
            self.SOC_locked_check()
            self.access_denied_check()
            self.process_all_overrides()
                       
            logging.info("🏁 SOC_Importer automation completed successfully")
        except Exception as e:
            logging.error(f"❌ SOC_Importer automation failed: {e}")
            self.inject_error_message("Error " + f"Automation failed: {e}")
        self.driver.quit() 

# Main execution
if __name__ == "__main__":
    auto_soc = SOC_Importer()
    auto_soc.run()