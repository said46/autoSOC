# soc_controller.py
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (NoSuchElementException, NoSuchWindowException)
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

import configparser
from dataclasses import dataclass
from typing import Any
from enum import Enum

import logging
import traceback
import inspect

from base_web_bot import BaseWebBot
from soc_base_mixin import SOC_BaseMixin


class ErrorSeverity(Enum):
    RECOVERABLE = 1      # Continue execution
    FATAL = 2           # Stop current operation
    TERMINAL = 3        # Immediate safe_exit

@dataclass
class AutomationResult:
    success: bool
    severity: ErrorSeverity = ErrorSeverity.RECOVERABLE
    message: str = ""
    data: Any = None
    exception: Exception | None = None
    
    @classmethod
    def success(cls, data: Any = None, message: str = "") -> 'AutomationResult':
        return cls(True, ErrorSeverity.RECOVERABLE, message, data)
    
    @classmethod
    def recoverable(cls, message: str, exception: Exception = None) -> 'AutomationResult':
        # Add caller context to message
        caller_frame = inspect.currentframe().f_back
        caller_info = f"{caller_frame.f_code.co_name}()" if caller_frame else "unknown"
        enhanced_message = f"[{caller_info}] {message}"
        return cls(False, ErrorSeverity.RECOVERABLE, enhanced_message, None, exception)

    @classmethod
    def fatal(cls, message: str, exception: Exception = None) -> 'AutomationResult':
        caller_frame = inspect.currentframe().f_back
        caller_info = f"{caller_frame.f_code.co_name}()" if caller_frame else "unknown"
        enhanced_message = f"[{caller_info}] {message}"
        return cls(False, ErrorSeverity.FATAL, enhanced_message, None, exception)
    
    @classmethod
    def terminal(cls, message: str, exception: Exception = None) -> 'AutomationResult':
        return cls(False, ErrorSeverity.TERMINAL, message, None, exception)


class SOC_Controller(BaseWebBot, SOC_BaseMixin):
    """
    Specialized bot for SOC overrides automation.
    """

    FINAL_STATE_DROPDOWN_INDEX = 1

    def __init__(self, soc_id=None):
        BaseWebBot.__init__(self)
        SOC_BaseMixin.__init__(self)
        self.warning_message = None
        self.load_configuration()
        
        if soc_id:
            self.SOC_id = soc_id

    def set_soc_id(self, soc_id: str) -> AutomationResult:
        """Set SOC ID with validation"""
        try:
            if not soc_id or not isinstance(soc_id, str):
                return AutomationResult.fatal("SOC ID must be a non-empty string")
            
            self.SOC_id = soc_id
            logging.info(f"✅ SOC ID set to: {soc_id}")
            return AutomationResult.success()
        except Exception as e:
            return AutomationResult.fatal(f"Failed to set SOC ID: {e}")

    @property
    def base_link(self) -> str:
        return self._base_link

    def load_configuration(self) -> AutomationResult:
        """Load configuration from file with comprehensive error handling"""
        try:
            config = configparser.ConfigParser(interpolation=None)
            
            # Read config file
            files_read = config.read(self.config_file, encoding="utf8")
            if not files_read:
                return AutomationResult.fatal(f"Configuration file not found: {self.config_file}")

            # Load basic settings
            try:
                self.user_name = config.get('Settings', 'user_name', fallback='xxxxxx')
                raw_password = config.get('Settings', 'password', fallback='******')
                self.password = self.process_password(raw_password)

                if '\n' in self.password:
                    self.password = 'INCORRECT PASSWORD'
                    logging.warning("⚠️ Password contains newline characters, using placeholder")

                self._base_link = config.get('Settings', 'base_link', fallback='http://eptw.sakhalinenergy.ru/')
                self.MAX_WAIT_USER_INPUT_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_USER_INPUT_DELAY_SECONDS', fallback=300)
                self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_PAGE_LOAD_DELAY_SECONDS', fallback=30)
                self.SOC_id = config.get('Settings', 'SOC_id', fallback='')

                # Load roles and statuses
                self.SOC_roles = config.get('Roles', 'SOC_roles', fallback='OAC,OAV').split(',')
                self.good_statuses = config.get(
                    'Statuses',
                    'good_statuses',
                    fallback='принято для установки-запрошено для удаления-установлено, не подтверждено-удалено, не подтверждено').split('-')
                self.SOC_status_approved_for_apply = config.get('Statuses', 'SOC_status_approved_for_apply', fallback='одобрено для установки')

                self.roles = {
                    config.get('Roles', 'OAC', fallback='Исполняющий форсирование'): 'OAC',
                    config.get('Roles', 'OAV', fallback='Проверяющий форсирование'): 'OAV'
                }

                self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = config.getboolean('Database', 'CONNECT_TO_DB_FOR_PARTIAL_SOC_ID', fallback=False)
                
                # Load database configuration
                db_result = self._load_database_configuration(config)
                if not db_result.success and db_result.severity == ErrorSeverity.FATAL:
                    return db_result

                # Set SOC ID pattern
                if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
                    self.SOC_ID_PATTERN = r"^\d{4,8}$"
                else:
                    self.SOC_ID_PATTERN = r"^\d{7,8}$"

                logging.info("✅ Configuration loaded successfully")
                return AutomationResult.success()

            except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
                return AutomationResult.fatal(f"Invalid configuration: {e}")

        except Exception as e:
            return AutomationResult.terminal(f"Failed to load configuration: {e}")

    def _load_database_configuration(self, config: configparser.ConfigParser) -> AutomationResult:
        """Load database configuration with error handling"""
        if not self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
            return AutomationResult.success()

        try:
            self.db_server = config.get('Database', 'server')
            raw_db_password = config.get('Database', 'password')
            self.db_password = self.process_password(raw_db_password)
            self.db_database = config.get('Database', 'database')
            self.db_username = config.get('Database', 'username')

            # Validate required database fields
            if not all([self.db_server, self.db_database, self.db_username]):
                error_msg = "Database credentials are incomplete"
                logging.warning(f"⚠️ {error_msg}")
                self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
                return AutomationResult.recoverable(error_msg)

            self.SQL_template = config.get('SQL', 'SOC_query', fallback="").strip(' \n\r\t')
            
            # Validate SQL query
            if self.SQL_template and not self.SQL_template.strip().lower().startswith('select'):
                error_msg = "SQL query must start with SELECT"
                logging.warning(f"⚠️ {error_msg}")
                self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
                return AutomationResult.recoverable(error_msg)

            logging.info("✅ Database configuration loaded successfully")
            return AutomationResult.success()

        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            error_msg = f"Database config incomplete: {e}. Disabling database features."
            logging.warning(f"⚠️ {error_msg}")
            self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
            return AutomationResult.recoverable(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error loading database config: {e}. Disabling database features."
            logging.warning(f"⚠️ {error_msg}")
            self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
            return AutomationResult.recoverable(error_msg)

    def get_SOC_status(self) -> AutomationResult:
        """Get SOC status with enhanced error handling"""
        script = """
            return document.evaluate(
                "//label[normalize-space()='Состояние']/following-sibling::text()[1]",
                document,
                null,
                XPathResult.STRING_TYPE,
                null
            ).stringValue.trim();
        """
        try:
            # Validate driver state
            if not self.driver or not self.driver.current_url:
                return AutomationResult.fatal("Web driver not initialized or no active page")

            status = self.driver.execute_script(script)
            if not status or status == '':
                return AutomationResult.recoverable("SOC status is empty or not found")

            logging.info(f"👆 SOC {self.SOC_id} status: '{status}'")
            return AutomationResult.success(data=status.lower())

        except NoSuchWindowException:
            return AutomationResult.terminal("Browser closed while getting SOC status")
        except Exception as e:
            return AutomationResult.fatal(f"Failed to get SOC status: {e}")

    def get_current_role(self) -> AutomationResult:
        """Get current role with enhanced error handling"""
        try:
            # Validate driver state
            if not self.driver:
                return AutomationResult.fatal("Web driver not initialized")

            role_span = self.driver.find_element(By.XPATH, "//span[@class='k-state-active' and contains(text(), 'Роль:')]")
            role_text = role_span.text.strip()

            if "Роль:" in role_text:
                role_name = role_text.split("Роль:")[1].strip()
                logging.info(f"👤 Current role: '{role_name}'")
                
                # Validate role exists in configuration
                if role_name not in self.roles:
                    return AutomationResult.fatal(f"Unknown role: '{role_name}'")
                    
                return AutomationResult.success(data=self.roles[role_name])
            else:
                return AutomationResult.fatal(f"Unexpected role format: '{role_text}'")

        except NoSuchElementException:
            return AutomationResult.fatal("Role span element not found on page")
        except NoSuchWindowException:
            return AutomationResult.terminal("Browser closed while getting current role")
        except Exception as e:
            return AutomationResult.recoverable(f"Could not determine role: {e}")

    def switch_role(self, role: str) -> AutomationResult:
        """Switch role with enhanced error handling"""
        try:
            # Validate input
            if not role or role not in self.SOC_roles:
                return AutomationResult.fatal(f"Invalid role specified: {role}")

            current_role_result = self.get_current_role()
            if not current_role_result.success:
                return current_role_result

            if current_role_result.data == role:
                logging.info(f"✅ Already in {role} role")
                return AutomationResult.success()

            # Navigate to role change page
            self.driver.get(self._base_link + r"User/ChangeRole")
            
            # Wait for dropdown to be ready
            dropdown_result = self.wait_for_kendo_dropdown("CurrentRoleName")
            if not dropdown_result:
                return AutomationResult.fatal("Role dropdown not available")

            # Set role using JavaScript
            set_role_script = f"""
                var dropdown = $('#CurrentRoleName').data('kendoDropDownList');
                if (dropdown) {{
                    dropdown.value('{role}');
                    dropdown.trigger('change');
                    return true;
                }}
                return false;
            """
            script_success = self.driver.execute_script(set_role_script)
            if not script_success:
                return AutomationResult.recoverable("Failed to set role via JavaScript")

            # Verify role was set
            WebDriverWait(self.driver, 10).until(
                lambda _: self.driver.execute_script(
                    f"return $('#CurrentRoleName').data('kendoDropDownList').value() === '{role}';"
                )
            )

            # Confirm role change with detailed error handling
            logging.info("🖱️ Attempting to click ConfirmHeader button...")
            click_result = self.click_button((By.ID, 'ConfirmHeader'))
            if not click_result:
                # Add more context about what might have failed
                logging.error("❌ click_button() returned False - button might not be clickable")
                # Check if button exists and is visible
                try:
                    button = self.driver.find_element(By.ID, 'ConfirmHeader')
                    is_displayed = button.is_displayed()
                    is_enabled = button.is_enabled()
                    logging.error(f"🔍 Button state - displayed: {is_displayed}, enabled: {is_enabled}")
                except NoSuchElementException:
                    logging.error("🔍 ConfirmHeader button not found on page")
                except Exception as e:
                    logging.error(f"🔍 Error inspecting button: {e}")
                    
                return AutomationResult.recoverable("Failed to confirm role change - button click failed")

            logging.info(f"✅ Switched to {role} role")
            return AutomationResult.success()

        except NoSuchWindowException:
            return AutomationResult.terminal("Browser closed during role switch")
        except Exception as e:
            logging.error(f"❌ Unexpected error in switch_role: {e}")
            return AutomationResult.fatal(f"Failed to switch role to {role}: {e}")

    def accept_SOC_to_apply(self) -> AutomationResult:
        """Accept SOC for application with enhanced error handling"""
        try:
            status_result = self.get_SOC_status()
            if not status_result.success:
                return status_result
            
            old_status = status_result.data
            logging.info(f"⏳ Current status: '{old_status}' - accepting for apply")

            logging.info("⏳ Waiting for ActionsList dropdown...")
            dropdown_ready = self.wait_for_kendo_dropdown("ActionsList")
            if not dropdown_ready:
                return AutomationResult.fatal("ActionsList dropdown not available")
            logging.info("✅ ActionsList ready")

            action_value = f'/Soc/TriggerChangeWorkflowState/{self.SOC_id}?trigger=AcceptForApply'
            logging.info(f"🔧 Setting action: {action_value}")

            set_action_script = """
                var dropdown = $('#ActionsList').data('kendoDropDownList');
                if (dropdown) {
                    dropdown.value(arguments[0]);
                    dropdown.trigger('change');
                    return true;
                }
                return false;
            """
            script_success = self.driver.execute_script(set_action_script, action_value)
            if not script_success:
                return AutomationResult.recoverable("Failed to set action via JavaScript")
                
            logging.info("✅ Action set")

            # Verify action was set
            WebDriverWait(self.driver, 10).until(
                lambda _: self.driver.execute_script(
                    "return $('#ActionsList').data('kendoDropDownList').value() === arguments[0];",
                    action_value
                )
            )

            # Apply action
            click_result = self.click_button((By.ID, 'ApplyActionButton'))
            if not click_result:
                return AutomationResult.recoverable("Failed to click Apply Action button")

            logging.info(f"⏳ Waiting for status change from '{old_status}'...")
            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                lambda _: self.get_SOC_status().data != old_status
            )

            new_status_result = self.get_SOC_status()
            if not new_status_result.success:
                return new_status_result
                
            new_status = new_status_result.data
            logging.info(f"✅ SOC accepted - new status: '{new_status}'")
            return AutomationResult.success(data=new_status)

        except NoSuchWindowException:
            return AutomationResult.terminal("Browser closed during SOC acceptance")
        except Exception as e:
            return AutomationResult.fatal(f"Failed to accept SOC {self.SOC_id}: {e}")

    def update_points(self) -> AutomationResult:
        """Update points with enhanced error handling"""
        try:
            item_xpath = f"//select[@id='CurrentStateSelect' and not(@disabled)]"
            sel_items = self.driver.find_elements(By.XPATH, item_xpath)
            
            if not sel_items:
                return AutomationResult.recoverable("No editable points found on page")

            logging.info(f"Updating {len(sel_items)} points")
            updated_count = 0

            for point_index, sel_item in enumerate(sel_items, start=1):
                try:
                    drop = Select(sel_item)
                    if len(drop.options) > 1:
                        drop.select_by_index(self.FINAL_STATE_DROPDOWN_INDEX)
                        selected_text = drop.first_selected_option.text
                        logging.info(f"✅ Point {point_index} updated to {selected_text}")
                        updated_count += 1
                except Exception as e:
                    logging.warning(f"⚠️ Failed to update point {point_index}: {e}")
                    continue

            if updated_count == 0:
                return AutomationResult.recoverable("No points were successfully updated")
                
            logging.info(f"✅ Successfully updated {updated_count}/{len(sel_items)} points")
            return AutomationResult.success(data=updated_count)

        except NoSuchElementException as e:
            return AutomationResult.recoverable("Failed to find points to update", e)
        except NoSuchWindowException:
            return AutomationResult.terminal("Browser closed during points update")
        except Exception as e:
            return AutomationResult.fatal("Failed to update points", e)

    def navigate_to_soc_and_check_status(self) -> AutomationResult:
        """Navigate to SOC and check status with enhanced error handling"""
        try:
            # Validate SOC ID
            if not self.SOC_id:
                return AutomationResult.fatal("SOC ID not set")

            SOC_view_base_link = self._base_link + r"Soc/Details/"
            self.driver.get(SOC_view_base_link + self.SOC_id)

            # Perform page checks
            checks_result = self._perform_page_checks()
            if not checks_result.success:
                return checks_result

            status_result = self.get_SOC_status()
            if not status_result.success:
                return status_result
            
            SOC_status = status_result.data
            logging.info(f"🔍 Initial SOC status: '{SOC_status}'")

            # Handle SOC that needs acceptance
            if SOC_status == self.SOC_status_approved_for_apply:
                logging.info("🔄 SOC needs accept - switching to OAC role")
                switch_result = self.switch_role('OAC')
                if not switch_result.success:
                    return switch_result
                    
                # Refresh SOC page
                self.driver.get(SOC_view_base_link + self.SOC_id)
                accept_result = self.accept_SOC_to_apply()
                if not accept_result.success:
                    return accept_result
                    
                status_result = self.get_SOC_status()
                if not status_result.success:
                    return status_result
                    
                SOC_status = status_result.data
                logging.info(f"🔍 Status after accept: '{SOC_status}'")

            # Validate final status
            if SOC_status not in self.good_statuses:
                error_msg = f'SOC {self.SOC_id} status "{SOC_status}" - cannot proceed'
                logging.error(error_msg)
                locator = (By.XPATH, "//div[@id='issowFormContainer']//div[contains(@class, 'user-form')]")
                self.inject_error_message(f'❌ SOC {self.SOC_id} status "{SOC_status}"',
                                        locator, style_addons={'width': '100%', 'align': 'center'})
                return AutomationResult.fatal(error_msg)

            return AutomationResult.success()

        except NoSuchWindowException:
            return AutomationResult.terminal("Browser closed during navigation")
        except Exception as e:
            return AutomationResult.fatal("Navigation to SOC failed", e)

    def _perform_page_checks(self) -> AutomationResult:
        """Perform necessary page validation checks"""
        try:
            self.error_404_not_present_check()
            self.url_contains_SOC_Details_check()
            return AutomationResult.success()
        except Exception as e:
            return AutomationResult.fatal(f"Page validation failed: {e}")

    def process_soc_roles(self) -> AutomationResult:
        """Process SOC roles with enhanced error handling"""
        try:
            if not self.SOC_roles:
                return AutomationResult.fatal("No SOC roles configured")

            for SOC_role in self.SOC_roles:
                logging.info(f"🔄 Processing role: {SOC_role}")
                
                switch_result = self.switch_role(SOC_role)
                if not switch_result.success:
                    return switch_result

                SOC_update_base_link = self._base_link + r"Soc/UpdateOverride/"
                self.driver.get(SOC_update_base_link + self.SOC_id)

                # Perform security checks
                security_result = self._perform_security_checks()
                if not security_result.success:
                    return security_result

                # Wait for points to be available
                try:
                    WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                        lambda _: len(self.driver.find_elements(By.XPATH, "//select[@id='CurrentStateSelect' and not(@disabled)]")) >= 1
                    )
                except Exception as e:
                    return AutomationResult.recoverable(f"Timeout waiting for points to load in role {SOC_role}: {e}")

                update_result = self.update_points()
                if not update_result.success:
                    return update_result
                    
                self.wait_for_user_confirmation()

            return AutomationResult.success()

        except NoSuchWindowException:
            return AutomationResult.terminal("Browser closed during role processing")
        except Exception as e:
            return AutomationResult.fatal("Failed to process SOC roles", e)

    def _perform_security_checks(self) -> AutomationResult:
        """Perform security-related checks"""
        try:
            self.SOC_locked_check()
            self.access_denied_check()
            return AutomationResult.success()
        except Exception as e:
            return AutomationResult.fatal(f"Security check failed: {e}")

    def wait_for_user_confirmation(self) -> AutomationResult:
        """Wait for user confirmation with enhanced error handling"""
        msg = '⚠️  Скрипт ожидает нажатия кнопки "Подтвердить".'
        xpath = "//div[@id='bottomWindowButtons']/div"
        
        try:
            self.inject_info_message(msg, (By.XPATH, xpath), {'color': 'lawngreen'})
            
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(
                EC.title_is(self.EXPECTED_HOME_PAGE_TITLE)
            )
            logging.info("🏁 Confirm pressed, home page loaded")
            return AutomationResult.success()
            
        except NoSuchWindowException:
            logging.error("⚠️ User closed browser")
            return AutomationResult.terminal("Browser closed by user during confirmation")
        except Exception as e:
            error_msg = "❌ Failed waiting for user confirmation"
            logging.error(f"{error_msg}: {e}")
            self.process_exception(error_msg, e)
            return AutomationResult.recoverable(error_msg, e)

    def _handle_automation_result(self, result: AutomationResult) -> bool:
        """Handle AutomationResult and return whether to continue execution"""
        # Get caller information for better context
        caller_frame = inspect.currentframe().f_back
        caller_info = f"{caller_frame.f_code.co_name}()" if caller_frame else "unknown"
        
        if result.severity == ErrorSeverity.TERMINAL:
            logging.error(f"🏁 TERMINAL in {caller_info}: {result.message}")
            if result.exception:
                logging.error(f"Terminal exception: {result.exception}")
                logging.error(f"Stack trace:\n{''.join(traceback.format_exception(type(result.exception), result.exception, result.exception.__traceback__))}")
            self.safe_exit()
            return False
        elif result.severity == ErrorSeverity.FATAL:
            logging.error(f"💥 FATAL in {caller_info}: {result.message}")
            if result.exception:
                logging.error(f"Fatal exception: {result.exception}")
                logging.error(f"Stack trace:\n{''.join(traceback.format_exception(type(result.exception), result.exception, result.exception.__traceback__))}")
            self.inject_error_message(f"Fatal error in {caller_info}: {result.message}")
            return False
        elif result.severity == ErrorSeverity.RECOVERABLE and not result.success:
            logging.warning(f"⚠️ RECOVERABLE in {caller_info}: {result.message}")
            if result.exception:
                logging.warning(f"Recoverable exception: {result.exception}")
                # Only log full stack trace for more serious recoverable errors
                if "timeout" in str(result.exception).lower() or "element" in str(result.exception).lower():
                    logging.debug(f"Stack trace:\n{''.join(traceback.format_exception(type(result.exception), result.exception, result.exception.__traceback__))}")
            # Continue execution for recoverable errors
            return True
        return True

    def run(self, standalone=False) -> AutomationResult:
        """Main execution method with comprehensive error handling"""
        try:
            if standalone:
                self.navigate_to_base()
                self.enter_credentials_and_prepare_soc_input()
            success = self.wait_for_soc_input_and_submit() 
            if not success:
                logging.error("❌ SOC input and submission failed")
                return
            
            # Main workflow with result handling
            nav_result = self.navigate_to_soc_and_check_status()
            if not self._handle_automation_result(nav_result):
                return nav_result
            
            roles_result = self.process_soc_roles()
            if not self._handle_automation_result(roles_result):
                return roles_result
                
            self.safe_exit()
            return AutomationResult.success("SOC processing completed successfully")
            
        except Exception as e:
            error_result = AutomationResult.terminal(f"Unexpected error in main execution: {e}", e)
            self._handle_automation_result(error_result)
            return error_result

if __name__ == "__main__":
    bot = SOC_Controller()
    result = bot.run(standalone=True)
    if not result.success:
        logging.error(f"Script execution failed: {result.message}")