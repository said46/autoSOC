# soc_importer.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (TimeoutException, NoSuchWindowException, NoSuchElementException, WebDriverException)
import openpyxl as xl
import configparser
import time
import logging

from base_web_bot import BaseWebBot, ErrorLevel
from soc_base_mixin import SOC_BaseMixin
from error_types import ErrorLevel, OperationResult

class SOC_Importer(BaseWebBot, SOC_BaseMixin):
    """SOC overrides importer with proper cascade handling."""

    # =========================================================================
    # INITIALIZATION & CONFIGURATION
    # =========================================================================

    def __init__(self, soc_id=None):
        BaseWebBot.__init__(self)
        SOC_BaseMixin.__init__(self)
        self._initialized = False
        
        # Load configuration - critical for operation
        success, error_msg, severity = self.load_configuration()
        if not success:
            logging.error(f"❌ Importer initialization failed: {error_msg}")
            # Can't use inject_error_message here - browser not ready yet
            print(f"❌ FATAL: {error_msg}")
            raise RuntimeError(f"Importer initialization failed: {error_msg}")
            
        self.SOC_base_link = self.base_link + r"Soc/EditOverrides/"
        if soc_id:
            self.SOC_id = soc_id        
        self.import_file_name: str = "soc_import_export/overrides.xlsx"
        self.override_records = []
        
        self._initialized = True

    @property
    def base_link(self) -> str:
        return self._base_link

    def load_configuration(self) -> OperationResult:
        """Returns (success, error_message, severity)"""
        try:
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

            return True, None, ErrorLevel.RECOVERABLE

        except Exception as e:
            return False, f"Configuration failed: {e}", ErrorLevel.FATAL

    # =========================================================================
    # DATA LOADING & MAPPING
    # =========================================================================

    def load_override_records(self) -> OperationResult:
        """Load override records from Excel with proper data mapping. Returns (success, error_message, severity)"""
        try:
            wb = xl.load_workbook(self.import_file_name)
            sheet = wb.active

            self.override_records = []
            for row in range(7, sheet.max_row + 1):
                tag_number = sheet.cell(row, 1).value
                if not tag_number:
                    continue

                record = {
                    'tag_number': str(tag_number).strip(),
                    'description': str(sheet.cell(row, 2).value or '').strip(),
                    'type_text': str(sheet.cell(row, 3).value or '').strip(),
                    'method_text': str(sheet.cell(row, 4).value or '').strip(),
                    'comment': str(sheet.cell(row, 5).value or '').strip(),
                    'applied_state_text': str(sheet.cell(row, 6).value or '').strip(),
                    'applied_additional_value': str(sheet.cell(row, 7).value or '').strip(),
                    'removed_state_text': str(sheet.cell(row, 8).value or '').strip(),
                    'removed_additional_value': str(sheet.cell(row, 9).value or '').strip()
                }
                
                self.override_records.append(record)

            logging.info(f"📋 Loaded {len(self.override_records)} override records")
            return True, None, ErrorLevel.RECOVERABLE
        except Exception as e:
            error_msg = f"Failed to load override records from {self.import_file_name}: {e}"
            logging.error(error_msg)
            return False, error_msg, ErrorLevel.FATAL

    def map_override_type(self, type_text: str) -> int:
        """Using generator expression for memory efficiency."""
        if not type_text:
            return None
            
        mapping_rules = (
            ("байпас", 1),
            ("блокировка", 2),
            ("форсировка", 3),
            ("логики", 4),
            ("сигнализации", 5)
        )
        
        text_lower = type_text.lower()
        
        # Generator expression - stops at first match
        match = next((value for key, value in mapping_rules if key in text_lower), None)
        return match

    # =========================================================================
    # WEB ELEMENT INTERACTION METHODS
    # =========================================================================

    def fill_text_field(self, field_id: str, value: str) -> OperationResult:
        """Fill text field with value. Returns (success, error_message, severity)"""
        try:
            element = self.driver.find_element(By.ID, field_id)
            element.clear()
            element.send_keys(str(value))
            logging.info(f"✅ Text field filled: {field_id} = {value}")
            return True, None, ErrorLevel.RECOVERABLE
        except NoSuchElementException:
            error_msg = f"Text field not found: {field_id}"
            logging.warning(error_msg)
            return False, error_msg, ErrorLevel.RECOVERABLE
        except Exception as e:
            error_msg = f"Failed to fill text field {field_id}: {e}"
            logging.error(error_msg)
            return False, error_msg, ErrorLevel.RECOVERABLE

    def wait_for_element_visibility(self, element_id: str, timeout: int = 5) -> bool:
        """Wait for element to become visible."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((By.ID, element_id))
            )
            return True
        except TimeoutException:
            return False

    # =========================================================================
    # DROPDOWN MANAGEMENT METHODS
    # =========================================================================

    def get_dropdown_data(self, dropdown_id: str) -> dict:
        """Get complete dropdown data including items and selection."""
        try:
            data = self.driver.execute_script(f"""
                var dd = $('#{dropdown_id}').data('kendoDropDownList');
                if (!dd) return {{error: 'not_initialized'}};
                
                var items = dd.dataItems();
                var selectedValue = dd.value();
                var selectedText = dd.text();
                
                return {{
                    items: items.map(item => ({{
                        text: item.Text || item.Title,
                        value: item.Value || item.Id
                    }})),
                    selected_value: selectedValue,
                    selected_text: selectedText,
                    item_count: items.length
                }};
            """)
            return data
        except Exception as e:
            logging.error(f"❌ Failed to get dropdown data for {dropdown_id}: {e}")
            return {'error': str(e)}

    def find_dropdown_item_by_text(self, dropdown_id: str, search_text: str) -> dict:
        """Find dropdown item by partial text match."""
        data = self.get_dropdown_data(dropdown_id)
        if data.get('error') or not data.get('items'):
            return None
            
        search_lower = search_text.lower()
        for item in data['items']:
            if search_lower in item['text'].lower():
                return item
        return None

    def set_dropdown_value(self, dropdown_id: str, value: int) -> bool:
        """Set dropdown value without triggering cascade."""
        try:
            self.driver.execute_script(f"""
                var dd = $('#{dropdown_id}').data('kendoDropDownList');
                if (dd) {{
                    dd.value({value});
                }}
            """)
            logging.info(f"✅ Dropdown set: {dropdown_id} = {value}")
            return True
        except Exception as e:
            logging.error(f"❌ Failed to set {dropdown_id}: {e}")
            return False

    def trigger_cascade_change(self, dropdown_id: str, new_value: int) -> bool:
        """Trigger cascade by simulating dropdown change event."""
        try:
            success = self.driver.execute_script(f"""
                var source = $('#{dropdown_id}').data('kendoDropDownList');
                var element = $('#{dropdown_id}')[0];
                
                if (source && element) {{
                    var events = $._data(element, 'events');
                    if (events && events.change && events.change[0]) {{
                        var handler = events.change[0].handler;
                        source.value({new_value});
                        
                        var event = $.Event('change');
                        Object.assign(event, {{
                            target: element,
                            currentTarget: element,
                            sender: source,
                            value: {new_value}
                        }});
                        
                        handler.call(element, event);
                        return true;
                    }}
                }}
                return false;
            """)
            
            if success:
                time.sleep(2)  # Wait for cascade completion
                logging.info(f"🔄 Cascade triggered: {dropdown_id} → {new_value}")
            return success
            
        except Exception as e:
            logging.error(f"❌ Cascade failed for {dropdown_id}: {e}")
            return False

    # =========================================================================
    # FORM FILLING & VALIDATION METHODS
    # =========================================================================

    def handle_dynamic_additional_fields(self, record: dict) -> OperationResult:
        """Handle additional value fields that have dynamic visibility. Returns (success, error_message, severity)"""
        try:
            # Applied additional value
            if record['applied_additional_value']:
                if self.wait_for_element_visibility("AdditionalValueAppliedState", timeout=3):
                    success, error_msg, severity = self.fill_text_field("AdditionalValueAppliedState", record['applied_additional_value'])
                    if not success:
                        return False, error_msg, severity
                    logging.info(f"✅ Applied Additional Value set: {record['applied_additional_value']}")
                else:
                    logging.warning("⚠️ Applied Additional Value field not visible - may need different state selection")
            
            # Removed additional value  
            if record['removed_additional_value']:
                if self.wait_for_element_visibility("AdditionalValueRemovedState", timeout=3):
                    success, error_msg, severity = self.fill_text_field("AdditionalValueRemovedState", record['removed_additional_value'])
                    if not success:
                        return False, error_msg, severity
                    logging.info(f"✅ Removed Additional Value set: {record['removed_additional_value']}")
                else:
                    logging.warning("⚠️ Removed Additional Value field not visible - may need different state selection")
            
            return True, None, ErrorLevel.RECOVERABLE
            
        except Exception as e:
            error_msg = f"Failed to handle dynamic additional fields: {e}"
            logging.error(error_msg)
            return False, error_msg, ErrorLevel.RECOVERABLE

    def fill_override_form(self, record: dict) -> OperationResult:
        """Fill the override form with dynamic field visibility handling. Returns (success, error_message, severity)"""
        try:
            logging.info(f"🔧 Processing: {record['tag_number']}")
            
        # Step 1: Fill basic fields
            success, error_msg, severity = self.fill_text_field("TagNumber", record['tag_number'])
            if not success:
                return False, error_msg, severity
                
            success, error_msg, severity = self.fill_text_field("Description", record['description'])
            if not success:
                return False, error_msg, severity
            
            # Track which additional fields should be visible
            additional_fields_expected = {
                'applied': bool(record['applied_additional_value']),
                'removed': bool(record['removed_additional_value'])
            }
            
            # Step 2: Handle Type → Method cascade
            if record['type_text']:
                type_value = self.map_override_type(record['type_text'])
                if type_value and self.trigger_cascade_change("OverrideTypeId", type_value):
                    time.sleep(1)  # Wait for Method dropdown
                    
                    # Step 3: Select specific Method
                    if record['method_text']:
                        method_item = self.find_dropdown_item_by_text("OverrideMethodId", record['method_text'])
                        if method_item and self.trigger_cascade_change("OverrideMethodId", method_item['value']):
                            time.sleep(1)  # Wait for States
                            
                            # Step 4: MANUALLY select Applied State
                            if record['applied_state_text']:
                                applied_item = self.find_dropdown_item_by_text("OverrideAppliedStateId", record['applied_state_text'])
                                if applied_item:
                                    self.set_dropdown_value("OverrideAppliedStateId", applied_item['value'])
                                    self.trigger_cascade_change("OverrideAppliedStateId", applied_item['value'])
                                    
                                    # Wait for potential UI changes (additional fields visibility)
                                    time.sleep(1)
                                    
                                    # Step 5: Handle Removed State selection
                                    removed_data = self.get_dropdown_data("OverrideRemovedStateId")
                                    if (removed_data.get('item_count', 0) > 0 and 
                                        not removed_data.get('selected_value')):
                                        if record['removed_state_text']:
                                            removed_item = self.find_dropdown_item_by_text("OverrideRemovedStateId", record['removed_state_text'])
                                            if removed_item:
                                                self.set_dropdown_value("OverrideRemovedStateId", removed_item['value'])
                                    else:
                                        logging.info(f"✅ Removed State auto-selected: {removed_data.get('selected_text')}")
            
            # Step 6: Fill optional fields with visibility awareness
            if record['comment']:
                success, error_msg, severity = self.fill_text_field("Comment", record['comment'])
                if not success:
                    return False, error_msg, severity
                
            # Handle dynamic additional value fields
            self.handle_dynamic_additional_fields(record)
            
            return True, None, ErrorLevel.RECOVERABLE
            
        except Exception as e:
            error_msg = f"Form fill failed for {record['tag_number']}: {e}"
            logging.error(error_msg)
            return False, error_msg, ErrorLevel.RECOVERABLE

    def submit_override(self, record: dict) -> OperationResult:
        """Submit the completed override form. Returns (success, error_message, severity)"""
        try:
            self.click_button((By.ID, "AddOverrideBtn"))
            return True, None, ErrorLevel.RECOVERABLE
        except Exception as e:
            error_msg = f"Submit override failed for {record['tag_number']}: {e}"
            logging.error(error_msg)
            return False, error_msg, ErrorLevel.RECOVERABLE

    # =========================================================================
    # WORKFLOW EXECUTION METHODS
    # =========================================================================

    def process_single_override(self, record: dict) -> OperationResult:
        """Process a single override record end-to-end. Returns (success, error_message, severity)"""
        try:
            logging.info(f"🔍 START process_single_override for: {record['tag_number']}")
            
            # Fill the form
            logging.info(f"🔍 Calling fill_override_form for: {record['tag_number']}")
            success, error_msg, severity = self.fill_override_form(record)
            if not success:
                logging.error(f"❌ fill_override_form returned False for: {record['tag_number']}")
                return False, error_msg, severity
            
            logging.info(f"🔍 fill_override_form completed, calling submit_override for: {record['tag_number']}")
            
            # Submit the override
            success, error_msg, severity = self.submit_override(record)
            if not success:
                logging.error(f"❌ submit_override returned False for: {record['tag_number']}")
                return False, error_msg, severity
            
            logging.info(f"✅ process_single_override completed successfully for: {record['tag_number']}")
            return True, None, ErrorLevel.RECOVERABLE
            
        except Exception as e:
            error_msg = f"Uncaught exception in process_single_override for {record['tag_number']}: {e}"
            logging.error(error_msg)
            return False, error_msg, ErrorLevel.RECOVERABLE

    def execute_import_workflow(self) -> OperationResult:
        """Main import workflow execution. Returns (success, error_message, severity)"""
        try:
            total_count = len(self.override_records)
            success_count = 0
            
            logging.info(f"🚀 Starting import of {total_count} overrides")
            
            for i, record in enumerate(self.override_records, 1):
                logging.info(f"📝 Processing {i}/{total_count}: {record['tag_number']}")
                
                success, error_msg, severity = self.process_single_override(record)
                if success:
                    success_count += 1
                else:
                    logging.error(f"❌ Failed: {record['tag_number']}: {error_msg}")
                    # Inject error message
                    self.inject_info_message(f"Failed: {record['tag_number']}")
            
            logging.info(f"🎉 Import completed: {success_count}/{total_count} successful")
            return True, None, ErrorLevel.RECOVERABLE
            
        except (WebDriverException, NoSuchWindowException):
            error_msg = "Browser closed during import"
            logging.warning(error_msg)
            return False, error_msg, ErrorLevel.TERMINAL
        except Exception as e:
            error_msg = f"Import workflow failed: {e}"
            logging.error(error_msg)
            return False, error_msg, ErrorLevel.FATAL

    # =========================================================================
    # NAVIGATION & WAIT METHODS
    # =========================================================================

    def navigate_to_edit_overrides(self) -> OperationResult:
        """Navigate to SOC Edit Overrides page. Returns (success, error_message, severity)"""
        try:
            url = self.SOC_base_link + self.SOC_id
            self.driver.get(url)
            
            self.wait_page_fully_loaded()
            self.SOC_locked_check()
            self.access_denied_check()          
            
            txt = "waiting for OverrideTypeId to be displayed"
            logging.info(f"⌛ start {txt}")
            # Wait for multiple conditions to ensure page is fully loaded
            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                lambda driver: (
                    driver.find_element(By.ID, "OverrideTypeId")
                )
            )
            logging.info("🏁 finish {txt}")
            
            return True, None, ErrorLevel.RECOVERABLE
            
        except TimeoutException as e:
            error_msg = "Page load timeout"
            logging.error(error_msg)
            return False, error_msg, ErrorLevel.FATAL
        except (WebDriverException, NoSuchWindowException) as e:
            error_msg = "Browser closed during navigation"
            logging.warning(error_msg)
            return False, error_msg, ErrorLevel.TERMINAL
        except Exception as e:
            error_msg = f"Navigation to edit overrides failed: {e}"
            logging.error(error_msg)
            return False, error_msg, ErrorLevel.FATAL

    def wait_for_user_confirmation(self) -> OperationResult:
        """Wait for user confirmation. Returns (success, error_message, severity)"""
        try:
            msg = '⚠️ Скрипт ожидает нажатия кнопки "Подтвердить".'
            xpath = "//div[@id='bottomWindowButtons']/div"
            self.inject_info_message(msg, (By.XPATH, xpath), {'color': 'lawngreen'})
            
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(
                EC.title_is(self.EXPECTED_HOME_PAGE_TITLE)
            )
            logging.info("🏁 Confirm pressed, home page loaded")
            return True, None, ErrorLevel.RECOVERABLE
        except NoSuchWindowException:
            error_msg = "Browser closed by user during confirmation"
            logging.warning(error_msg)
            return False, error_msg, ErrorLevel.TERMINAL
        except Exception as e:
            error_msg = f"Failed waiting for confirm: {e}"
            logging.error(error_msg)
            return False, error_msg, ErrorLevel.FATAL

    # =========================================================================
    # ERROR HANDLING & MAIN EXECUTION
    # =========================================================================

    def _handle_result(self, success: bool, error_msg: str | None, severity: ErrorLevel) -> bool:
        """Handle result and return whether to continue execution"""
        if not success:
            if severity == ErrorLevel.TERMINAL:
                logging.info(f"🏁 Terminal: {error_msg}")
                self.safe_exit()
                return False
            elif severity == ErrorLevel.FATAL:
                logging.error(f"💥 Fatal: {error_msg}")
                self.inject_error_message(error_msg)
                return False
            else:  # RECOVERABLE
                logging.warning(f"⚠️ Recoverable: {error_msg}")
                # Continue execution for recoverable errors
                return True
        return True

    def run(self, standalone=False):
        """Main execution workflow."""
        if not self._initialized:
            logging.error("❌ Importer not properly initialized")
            return
            
        if standalone:
            self.navigate_to_base()
            self.enter_credentials_and_prepare_soc_input()
            success = self.wait_for_soc_input_and_submit()  # Now returns bool
            if not success:
                logging.error("❌ SOC input and submission failed")
                return

        # Main workflow with proper severity handling
        success, error_msg, severity = self.load_override_records()
        if not self._handle_result(success, error_msg, severity):
            return
            
        success, error_msg, severity = self.navigate_to_edit_overrides()
        if not self._handle_result(success, error_msg, severity):
            return

        success, error_msg, severity = self.execute_import_workflow()
        if not self._handle_result(success, error_msg, severity):
            return
            
        success, error_msg, severity = self.wait_for_user_confirmation()
        if not self._handle_result(success, error_msg, severity):
            return
            
        self.safe_exit()


if __name__ == "__main__":
    try:
        bot = SOC_Importer()
        bot.run(standalone=True)
    except Exception as e:
        print(f"❌ Failed to start importer: {e}")
        logging.error(f"❌ Importer startup failed: {e}")