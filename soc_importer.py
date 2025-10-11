# soc_importer.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (TimeoutException, NoSuchWindowException, WebDriverException)
import openpyxl as xl
import configparser
import time
import logging

from base_web_bot import BaseWebBot
from soc_base_mixin import SOC_BaseMixin


class SOC_Importer(BaseWebBot, SOC_BaseMixin):
    """SOC overrides importer."""

    def __init__(self, soc_id=None):
        BaseWebBot.__init__(self)
        SOC_BaseMixin.__init__(self)
        self.load_configuration()
        self.SOC_base_link = self.base_link + r"Soc/EditOverrides/"
        self.SOC_id = soc_id
        self.import_file_name: str = "soc_import_export/overrides.xlsx"

    @property
    def base_link(self) -> str:
        return self._base_link
   
    def load_configuration(self) -> None:
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.config_file, encoding="utf8")

        self.user_name = config.get('Settings', 'user_name', fallback='xxxxxx')
        raw_password = config.get('Settings', 'password', fallback='******')
        self.password = self.process_password(raw_password)

        if '\n' in self.password:
            self.password = 'INCORRECT PASSWORD'

        self._base_link = config.get('Settings', 'base_link', fallback='http://eptw.sakhalinenergy.ru/')
        self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_PAGE_LOAD_DELAY_SECONDS', fallback=20)

    def load_overrides_from_export(self) -> None:
        """Load overrides from Excel file."""
        try:
            wb = xl.load_workbook(self.import_file_name)
            sheet = wb.active

            self.list_of_overrides = []
            for row in range(7, sheet.max_row + 1):
                tag_number = sheet.cell(row, 1).value
                if not tag_number:
                    continue

                override = {
                    'TagNumber': tag_number,
                    'Description': sheet.cell(row, 2).value,
                    'OverrideType': sheet.cell(row, 3).value,
                    'OverrideMethod': sheet.cell(row, 4).value,
                    'Comment': sheet.cell(row, 5).value,
                    'AppliedState': sheet.cell(row, 6).value,
                    'AdditionalValueAppliedState': sheet.cell(row, 7).value,
                    'RemovedState': sheet.cell(row, 8).value,
                    'AdditionalValueRemovedState': sheet.cell(row, 9).value
                }
                
                self.list_of_overrides.append(override)

            logging.info(f"✅ Loaded {len(self.list_of_overrides)} overrides")
        except Exception as e:
            msg = f"❌ Failed to load overrides from {self.import_file_name}"
            logging.error(f"{msg}: {e}")
            raise RuntimeError(msg)
 
    def get_dropdown_items_count(self, dropdown_id: str) -> int:
        """Get number of items in a dropdown."""
        try:
            count = self.driver.execute_script(f"""
                var dd = $('#{dropdown_id}').data('kendoDropDownList');
                return dd ? dd.dataItems().length : 0;
            """)
            return count
        except Exception:
            return 0

    def get_first_dropdown_value(self, dropdown_id: str):
        """Get the value of the first item in dropdown."""
        try:
            value = self.driver.execute_script(f"""
                var dd = $('#{dropdown_id}').data('kendoDropDownList');
                if (dd && dd.dataItems().length > 0) {{
                    var item = dd.dataItems()[0];
                    return item.Value || item.Id;
                }}
                return null;
            """)
            return value
        except Exception:
            return None

    def auto_select_first_options(self) -> None:
        """Fixed auto-select based on successful cascade sequence."""
        try:
            # Step 1: First ensure Method dropdown has items
            method_count = self.get_dropdown_items_count("OverrideMethodId")
            if method_count == 0:
                logging.warning("⚠️ Method dropdown empty - may need Type cascade first")
                return

            # Step 2: Get and select first method value
            method_value = self.get_first_dropdown_value("OverrideMethodId")
            if method_value:
                # Trigger Method → States cascade
                self.cascade_dropdown("OverrideMethodId", method_value)
                
                # Wait for states to populate
                time.sleep(2)
                
                # Step 3: Now select first states
                self.driver.execute_script("""
                    // Select first Applied State
                    var ddApplied = $('#OverrideAppliedStateId').data('kendoDropDownList');
                    if (ddApplied && ddApplied.dataItems().length > 0) {
                        var appliedItem = ddApplied.dataItems()[0];
                        ddApplied.value(appliedItem.Value || appliedItem.Id);
                        console.log('✅ Selected applied state:', appliedItem.Text);
                    }
                    
                    // Select first Removed State  
                    var ddRemoved = $('#OverrideRemovedStateId').data('kendoDropDownList');
                    if (ddRemoved && ddRemoved.dataItems().length > 0) {
                        var removedItem = ddRemoved.dataItems()[0];
                        ddRemoved.value(removedItem.Value || removedItem.Id);
                        console.log('✅ Selected removed state:', removedItem.Text);
                    }
                """)
                
                # Log results
                applied_count = self.get_dropdown_items_count("OverrideAppliedStateId")
                removed_count = self.get_dropdown_items_count("OverrideRemovedStateId")
                logging.info(f"✅ Auto-selected: {applied_count} applied, {removed_count} removed states")
                
        except Exception as e:
            logging.error(f"❌ Fixed auto-select failed: {e}")

    def cascade_dropdown(self, source_id: str, target_value: int) -> bool:
        """Fixed cascade dropdown function based on successful JS test."""
        try:
            self.driver.execute_script(f"""
                var source = $('#{source_id}').data('kendoDropDownList');
                var element = $('#{source_id}')[0];
                
                if (source && element) {{
                    var events = $._data(element, 'events');
                    if (events && events.change && events.change[0]) {{
                        var handler = events.change[0].handler;
                        source.value({target_value});
                        
                        var event = $.Event('change');
                        Object.assign(event, {{
                            target: element,
                            currentTarget: element,
                            sender: source,
                            value: {target_value}
                        }});
                        
                        handler.call(element, event);
                        return true;
                    }}
                }}
                return false;
            """)
            time.sleep(2)  # Wait for cascade to complete
            return True
        except Exception as e:
            logging.error(f"❌ Cascade failed for {source_id}: {e}")
            return False

    def add_override(self, override: dict):
        """Fixed override addition with proper cascade sequence."""
        try:
            # Fill basic fields first
            self.fill_text_field("TagNumber", override["TagNumber"])
            self.fill_text_field("Description", override["Description"])
            
            # Step 1: Set Override Type (triggers Type → Method cascade)
            if override["OverrideType"]:
                type_value = self.map_override_type_to_value(override["OverrideType"])
                logging.info(f"🔄 Setting type {type_value} for {override['TagNumber']}")
                self.cascade_dropdown("OverrideTypeId", type_value)
                
                # Wait for Method dropdown to populate
                time.sleep(2)
            
            # Step 2: Auto-select Method and States (triggers Method → States cascade)
            self.auto_select_first_options()
                
            # Fill optional fields
            if override["Comment"]:
                self.fill_text_field("Comment", override["Comment"])

            if override["AdditionalValueAppliedState"]:
                self.fill_text_field("AdditionalValueAppliedState", override["AdditionalValueAppliedState"])

            if override["AdditionalValueRemovedState"]:
                self.fill_text_field("AdditionalValueRemovedState", override["AdditionalValueRemovedState"])

            # Add the override
            self.click_button((By.ID, "AddOverrideBtn"))
            time.sleep(1)
            
            logging.info(f"✅ Added: {override['TagNumber']}")

        except (WebDriverException, NoSuchWindowException):
            logging.warning("🏁 Browser closed during override addition")
            self.safe_exit()
        except Exception as e:
            self.process_exception(f"❌ Failed: {override.get('TagNumber', 'Unknown')}", e)

    # Replace the existing methods in your class
    def process_all_overrides(self):
        """Process all loaded overrides using fixed cascade."""
        try:
            total_count = len(self.list_of_overrides)
            logging.info(f"📋 Processing {total_count} overrides")
            
            success_count = 0
            
            for override in self.list_of_overrides:                    
                try:
                    self.add_override(override)  # Use fixed version
                    success_count += 1
                    time.sleep(1)  # Slightly longer delay between overrides
                except Exception as e:
                    msg = f"❌ Failed to add override {override.get('TagNumber', 'Unknown')}"
                    logging.error(f"{msg}: {str(e)}")
                    self.inject_info_message(msg)
                    continue            
            logging.info(f"🎉 Completed: {success_count}/{total_count} successful")
        except (WebDriverException, NoSuchWindowException):
            logging.warning("🏁 Browser closed during processing")
            self.safe_exit()

    def wait_for_user_confirmation(self):
        """Wait for user confirmation with proper connection handling."""
        try:
            msg = '⚠️  Скрипт ожидает нажатия кнопки "Подтвердить".'
            xpath = "//div[@id='bottomWindowButtons']/div"
            self.inject_info_message(msg, (By.XPATH, xpath), {'color': 'lawngreen'})
            
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(
                EC.title_is(self.EXPECTED_HOME_PAGE_TITLE)
            )
            logging.info("🏁 Confirm pressed, home page loaded")
            return True
        except NoSuchWindowException:
            logging.warning("🏁 Browser closed by user during confirmation")
            self.safe_exit()
        except Exception as e:           
            self.process_exception("❌ Failed waiting for confirm", e)

    def navigate_to_edit_overrides(self) -> None:
        """Navigate to SOC Edit Overrides page."""
        try:
            url = self.SOC_base_link + (self.SOC_id or "")
            self.driver.get(url)
            
            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                EC.presence_of_element_located((By.ID, "OverrideTypeId"))
            )
            time.sleep(1)
        except TimeoutException as e:
            self.process_exception("❌ Page load timeout", e)
        except (WebDriverException, NoSuchWindowException):
            logging.warning("🏁 Browser closed during navigation")
            self.safe_exit()
        except Exception as e:
            self.process_exception("❌ Failure while navigating to edit overrides page", e)

    def fill_text_field(self, field_id: str, value: str) -> None:
        """Fill text field with value."""           
        try:
            element = self.driver.find_element(By.ID, field_id)
            element.clear()
            element.send_keys(str(value))
        except Exception as e:
            self.process_exception(f"⚠️ Could not fill {field_id}", e)

    def map_override_type_to_value(self, override_type_text: str) -> int:
        """Map override type text to numeric value."""
        mapping = {"байпас": 1, "блокировка": 2, "форсировка": 3, "логики": 4, "сигнализации": 5}
        text_lower = str(override_type_text).lower()
        return next((v for k, v in mapping.items() if k in text_lower), 1)            

    def run(self, standalone=False):
        """Main execution workflow."""
        if standalone:
            self.navigate_to_base()
            self.enter_credentials_and_prepare_soc_input()
            self.wait_for_soc_input_and_submit()

        self.load_overrides_from_export()            
        self.navigate_to_edit_overrides()
            
        self.SOC_locked_check()
        self.access_denied_check()
        
        self.process_all_overrides()
        self.wait_for_user_confirmation()

if __name__ == "__main__":
    auto_soc = SOC_Importer()
    auto_soc.run(standalone=True)