# soc_importer.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import (TimeoutException, NoSuchWindowException)
import openpyxl as xl
import json
import configparser
import time

import logging

from base_web_bot import BaseWebBot
from soc_base_mixin import SOC_BaseMixin


class SOC_Importer(BaseWebBot, SOC_BaseMixin):
    """
    Specialized bot for importing SOC (Safety Override Control) overrides from Excel files.
    """

    def __init__(self, soc_id=None):
        BaseWebBot.__init__(self)
        SOC_BaseMixin.__init__(self)
        self.load_configuration()
        self.SOC_base_link = self.base_link + r"Soc/EditOverrides/"
        
        if soc_id:
            self.SOC_id = soc_id

    def set_soc_id(self, soc_id: str) -> None:
        self.SOC_id = soc_id

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
        self.MAX_WAIT_USER_INPUT_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_USER_INPUT_DELAY_SECONDS', fallback=300)

        logging.info(f"✅ Configuration loaded from {self.config_file}")

    def load_overrides_from_export(self) -> None:
        try:
            excel_file_path = 'soc_import_export/overrides.xlsx'
            logging.info(f"📂 Loading overrides from: {excel_file_path}")
            wb = xl.load_workbook(excel_file_path)
            sheet = wb.active

            # Read headers and data
            headers = [sheet.cell(6, col).value for col in range(1, sheet.max_column + 1) if sheet.cell(6, col).value]
            logging.info(f"📋 Columns: {', '.join(headers)}")

            # Simple column mapping
            column_indices = {}
            for idx, header in enumerate(headers):
                column_indices[header] = idx

            # Load overrides
            self.list_of_overrides = []
            for row in range(7, sheet.max_row + 1):
                tag_number = sheet.cell(row, column_indices['TagNumber'] + 1).value if 'TagNumber' in column_indices else None
                if not tag_number:
                    continue

                override = {
                    "TagNumber": tag_number,
                    "Description": sheet.cell(row, column_indices['Description'] + 1).value if 'Description' in column_indices else "",
                    "OverrideType": sheet.cell(row, column_indices['OverrideType'] + 1).value if 'OverrideType' in column_indices else "",
                    "OverrideMethod": sheet.cell(row, column_indices['OverrideMethod'] + 1).value if 'OverrideMethod' in column_indices else "",
                    "Comment": sheet.cell(row, column_indices['Comment'] + 1).value if 'Comment' in column_indices else None,
                    "AppliedState": sheet.cell(row, column_indices['AppliedState'] + 1).value if 'AppliedState' in column_indices else "",
                    "AdditionalValueAppliedState": sheet.cell(row, column_indices['AdditionalValueAppliedState'] + 1).value if 'AdditionalValueAppliedState' in column_indices else None,
                    "RemovedState": sheet.cell(row, column_indices['RemovedState'] + 1).value if 'RemovedState' in column_indices else None,
                    "AdditionalValueRemovedState": sheet.cell(row, column_indices['AdditionalValueRemovedState'] + 1).value if 'AdditionalValueRemovedState' in column_indices else None
                }

                # Convert empty strings to None
                for field in ['Comment', 'AdditionalValueAppliedState', 'AdditionalValueRemovedState', 'RemovedState']:
                    if override[field] == "":
                        override[field] = None

                self.list_of_overrides.append(override)

            logging.info(f"✅ Loaded {len(self.list_of_overrides)} overrides")

        except Exception as e:
            logging.error(f"❌ Failed to load overrides: {e}")
            self.inject_error_message("❌ Failed to load overrides from export file")
            raise

    # ===== KENDO UI METHODS =====

    def execute_kendo_script(self, script: str, *args):
        """Helper to execute Kendo scripts with error handling"""
        try:
            return self.driver.execute_script(script, *args)
        except Exception as e:
            logging.error(f"❌ Kendo script failed: {e}")
            return None

    def get_kendo_dropdown_data(self, element_id: str) -> list[dict]:
        result = self.execute_kendo_script("""
            var dropdown = $('#%s').data('kendoDropDownList');
            return dropdown ? JSON.stringify(dropdown.dataItems()) : null;
        """ % element_id)
        return json.loads(result) if result else []

    def set_kendo_dropdown_value(self, element_id: str, value: str) -> bool:
        result = self.execute_kendo_script("""
            var dropdown = $('#%s').data('kendoDropDownList');
            if (dropdown) {
                dropdown.value(arguments[0]);
                dropdown.trigger('change');
                return true;
            }
            return false;
        """ % element_id, value)
        
        if result:
            WebDriverWait(self.driver, 5).until(
                lambda _: self.execute_kendo_script(
                    "return $('#%s').data('kendoDropDownList').value() === arguments[0];" % element_id, value
                )
            )
            logging.info(f"✅ {element_id} set to: {value}")
        return bool(result)

    def wait_for_kendo_dropdown_data(self, element_id: str, timeout: int = 10) -> bool:
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda _: self.execute_kendo_script(
                    "var d = $('#%s').data('kendoDropDownList'); return d && d.dataItems().length > 0;" % element_id
                )
            )
            return True
        except TimeoutException:
            logging.error(f"❌ {element_id} has no data within {timeout}s")
            return False

    def select_kendo_dropdown_by_text(self, element_id: str, text: str) -> bool:
        if not self.wait_for_kendo_dropdown_data(element_id):
            return False

        dropdown_data = self.get_kendo_dropdown_data(element_id)
        for item in dropdown_data:
            if any(item.get(field) == text for field in ['Title', 'Text', 'ShortForm']):
                value = item.get('Value') or item.get('Text') or item.get('Title')
                return self.set_kendo_dropdown_value(element_id, value)

        logging.error(f"❌ '{text}' not found in {element_id}")
        return False

    def trigger_dependent_dropdowns(self) -> bool:
        """Trigger updates for dependent dropdowns"""
        result = self.execute_kendo_script("""
            var d = $('#OverrideTypeId').data('kendoDropDownList');
            if (d) {
                d.trigger('change');
                $('#OverrideTypeId').change();
                return true;
            }
            return false;
        """)
        time.sleep(1)  # Brief pause for events to process
        return bool(result)

    def wait_for_dependent_dropdowns(self, timeout: int = 15) -> bool:
        self.trigger_dependent_dropdowns()
        
        for dropdown in ["OverrideMethodId", "OverrideAppliedStateId", "OverrideRemovedStateId"]:
            if not self.wait_for_kendo_dropdown_data(dropdown, timeout):
                logging.error(f"❌ {dropdown} not populated")
                return False
        
        logging.info("✅ All dependent dropdowns ready")
        return True

    # ===== NAVIGATION =====

    def navigate_to_edit_overrides(self):
        self.driver.get(self.SOC_base_link + self.SOC_id)
        logging.info(f"👆 Navigated to Edit Overrides for SOC {self.SOC_id}")

    # ===== OVERRIDE PROCESSING =====

    def clear_form_fields(self):
        """Clear all form fields"""
        fields = ["TagNumber", "Description", "Comment", "AdditionalValueAppliedState", "AdditionalValueRemovedState"]
        for field in fields:
            try:
                self.driver.find_element(By.ID, field).clear()
            except:
                pass  # Ignore if field doesn't exist or can't be cleared

    def add_override(self, override: dict[str, str]) -> None:
        try:
            self.clear_form_fields()

            # Set basic fields
            self.driver.find_element(By.ID, "TagNumber").send_keys(override["TagNumber"])
            self.driver.find_element(By.ID, "Description").send_keys(override["Description"])

            # Set override type and wait for dependencies
            if not self.select_kendo_dropdown_by_text("OverrideTypeId", override["OverrideType"]):
                raise Exception(f"Failed to set OverrideType: {override['OverrideType']}")

            if not self.wait_for_dependent_dropdowns():
                raise Exception("Dependent dropdowns failed to populate")

            # Set dependent fields
            if not self.select_kendo_dropdown_by_text("OverrideMethodId", override["OverrideMethod"]):
                raise Exception(f"Failed to set OverrideMethod: {override['OverrideMethod']}")

            if override["Comment"]:
                self.driver.find_element(By.ID, "Comment").send_keys(override["Comment"])

            if not self.select_kendo_dropdown_by_text("OverrideAppliedStateId", override["AppliedState"]):
                raise Exception(f"Failed to set AppliedState: {override['AppliedState']}")

            if override["AdditionalValueAppliedState"]:
                self.driver.find_element(By.ID, "AdditionalValueAppliedState").send_keys(override["AdditionalValueAppliedState"])

            if override["RemovedState"] and not self.select_kendo_dropdown_by_text("OverrideRemovedStateId", override["RemovedState"]):
                raise Exception(f"Failed to set RemovedState: {override['RemovedState']}")

            if override["AdditionalValueRemovedState"]:
                self.driver.find_element(By.ID, "AdditionalValueRemovedState").send_keys(override["AdditionalValueRemovedState"])

            # Add the override
            self.driver.find_element(By.ID, "AddOverrideBtn").click()
            time.sleep(1)  # Wait for form reset
            logging.info(f"✅ Added: {override['TagNumber']}")

        except Exception as e:
            logging.error(f"❌ Error adding {override.get('TagNumber', 'Unknown')}: {e}")
            raise

    def process_all_overrides(self):
        logging.info(f"📋 Processing {len(self.list_of_overrides)} overrides")
        for i, override in enumerate(self.list_of_overrides, 1):
            logging.info(f"🔄 {i}/{len(self.list_of_overrides)}: {override['TagNumber']}")
            self.add_override(override)
        
        logging.info("✅ All overrides processed")
        self.wait_for_user_confirmation()

    def wait_for_user_confirmation(self):
        msg = '⚠️  Скрипт ожидает нажатия кнопки "Подтвердить".'
        xpath = "//div[@id='bottomWindowButtons']/div"
        self.inject_info_message(msg, (By.XPATH, xpath), {'color': 'lawngreen'})
        
        try:
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(
                EC.title_is(self.EXPECTED_HOME_PAGE_TITLE)
            )
            logging.info("🏁 Confirm pressed, home page loaded")
        except NoSuchWindowException:
            logging.info("⚠️ User closed browser")
            self.safe_exit()
        except Exception as e:
            logging.error(f"❌ Failed waiting for confirm: {e}")

    # ===== MAIN WORKFLOW =====

    def run(self, standalone=False):
        try:
            logging.info("🚀 Starting SOC_Importer")

            if standalone:
                self.navigate_to_base()
                self.enter_credentials_and_prepare_soc_input()
                self.wait_for_soc_input_and_submit()

            self.load_overrides_from_export()
            self.navigate_to_edit_overrides()
            self.SOC_locked_check()
            self.access_denied_check()
            self.process_all_overrides()

            logging.info("🏁 SOC_Importer completed")
        except Exception as e:
            logging.error(f"❌ SOC_Importer failed: {e}")
            self.inject_error_message(f"Automation failed: {e}")
        finally:
            self.driver.quit()


if __name__ == "__main__":
    auto_soc = SOC_Importer()
    auto_soc.run(standalone=True)