# soc_controller.py
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (NoSuchElementException, NoSuchWindowException)
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

import configparser
import logging

from base_web_bot import BaseWebBot
from soc_base_mixin import SOC_BaseMixin
from error_types import ErrorLevel, OperationResult


class SOC_Controller(BaseWebBot, SOC_BaseMixin):
    """
    Specialized bot for SOC overrides automation.
    """

    FINAL_STATE_DROPDOWN_INDEX = 1

    # =========================================================================
    # INITIALIZATION AND CONFIGURATION
    # =========================================================================

    def __init__(self, soc_id=None):
        BaseWebBot.__init__(self)
        SOC_BaseMixin.__init__(self)
        self.warning_message = None
        self._initialized = False
        
        # Load configuration - critical for operation
        success, error_msg, severity = self.load_configuration()
        if not success:
            logging.error(f"❌ Controller initialization failed: {error_msg}")
            # Can't use inject_error_message here - browser not ready yet
            print(f"❌ FATAL: {error_msg}")
            raise RuntimeError(f"Controller initialization failed: {error_msg}")
            
        if soc_id:
            self.SOC_id = soc_id
            
        self._initialized = True

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
            self.MAX_WAIT_USER_INPUT_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_USER_INPUT_DELAY_SECONDS', fallback=300)
            self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_PAGE_LOAD_DELAY_SECONDS', fallback=30)
            self.SOC_id = config.get('Settings', 'SOC_id', fallback='')

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
            self._load_database_configuration(config)

            if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
                self.SOC_ID_PATTERN = r"^\d{4,8}$"
            else:
                self.SOC_ID_PATTERN = r"^\d{7,8}$"

            return True, None, None

        except Exception as e:
            return False, f"Configuration failed: {e}", ErrorLevel.FATAL

    def _load_database_configuration(self, config: configparser.ConfigParser) -> None:
        if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
            try:
                self.db_server = config.get('Database', 'server')
                raw_db_password = config.get('Database', 'password')
                self.db_password = self.process_password(raw_db_password)
                self.db_database = config.get('Database', 'database')
                self.db_username = config.get('Database', 'username')

                if not all([self.db_server, self.db_database, self.db_username]):
                    raise configparser.NoOptionError('Database', 'Some database credentials are empty')

                self.SQL_template = config.get('SQL', 'SOC_query', fallback="").strip(' \n\r\t')
                if self.SQL_template and not self.SQL_template.strip().lower().startswith('select'):
                    raise ValueError("SQL query must start with SELECT")

            except (configparser.NoSectionError, configparser.NoOptionError) as e:
                self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
                self.warning_message = f"⚠️ Database config incomplete: {e}. Disabling database features."
                logging.warning(self.warning_message)
            except ValueError as e:
                self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
                self.warning_message = "⚠️ SQL query doesn't start with SELECT. Disabling database features."
                logging.warning(self.warning_message)

    # =========================================================================
    # PROPERTIES AND SETTERS
    # =========================================================================

    @property
    def base_link(self) -> str:
        return self._base_link

    def set_soc_id(self, soc_id: str) -> None:
        self.SOC_id = soc_id

    # =========================================================================
    # STATUS AND ROLE MANAGEMENT
    # =========================================================================

    def get_SOC_status(self) -> OperationResult:
        """Returns (success, error_message, severity)"""
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
            status = self.driver.execute_script(script)
            if status == '':
                return False, "SOC status cannot be empty", ErrorLevel.FATAL
            logging.info(f"👆 SOC {self.SOC_id} status: '{status}'")
            self.SOC_status = status.lower()
            return True, None, None
        except Exception as e:
            return False, f"Failed to get SOC status: {e}", ErrorLevel.FATAL

    def get_current_role(self) -> tuple[bool, str | None, ErrorLevel]:
        """Returns (success, role_or_error, severity)"""
        try:
            role_span = self.driver.find_element(By.XPATH, "//span[@class='k-state-active' and contains(text(), 'Роль:')]")
            role_text = role_span.text.strip()

            if "Роль:" in role_text:
                role_name = role_text.split("Роль:")[1].strip()
                logging.info(f"👤 Current role: '{role_name}'")
                return True, role_name, ErrorLevel.RECOVERABLE
            else:
                return False, f"Unexpected role format: '{role_name}'", ErrorLevel.RECOVERABLE

        except NoSuchElementException:
            return False, "Role span not found", ErrorLevel.RECOVERABLE
        except Exception as e:
            return False, f"Could not determine role: {str(e)}", ErrorLevel.RECOVERABLE

    def switch_role(self, role: str) -> OperationResult:
        """Returns (success, error_message, severity)"""
        try:
            # Check current role
            success, current_role_or_error, severity = self.get_current_role()
            if not success:
                return False, current_role_or_error, severity

            if current_role_or_error == role:
                logging.info(f"✅ Already in {role} role")
                return True, None, None

            # Switch role
            self.driver.get(self._base_link + r"User/ChangeRole")
            self.wait_for_page_fully_ready() # probably add CurrentRoleName widget

            set_role_script = f"""
                var dropdown = $('#CurrentRoleName').data('kendoDropDownList');
                dropdown.value('{role}');
                dropdown.trigger('change');
                return true;
            """
            self.driver.execute_script(set_role_script)

            WebDriverWait(self.driver, 10).until(
                lambda _: self.driver.execute_script(
                    f"return $('#CurrentRoleName').data('kendoDropDownList').value() === '{role}';"
                )
            )

            self.click_button((By.ID, 'ConfirmHeader'))
            logging.info(f"✅ Switched to {role} role")
            return True, None, None

        except NoSuchWindowException:
            return False, "Browser closed during role switch", ErrorLevel.TERMINAL
        except Exception as e:
            return False, f"Failed to switch role to {role}: {e}", ErrorLevel.FATAL

    # =========================================================================
    # SOC WORKFLOW OPERATIONS
    # =========================================================================

    def accept_SOC_to_apply(self) -> OperationResult:
        """Returns (success, error_message, severity)"""
        try:
            # Get current status
            success, error_msg, severity = self.get_SOC_status()
            if not success:
                return False, error_msg, severity
            
            old_status = self.SOC_status
            logging.info(f"⏳ Current status: '{old_status}' - accepting for apply")

            # Wait for and set action
            self.wait_for_page_fully_ready() # probably add widget "ActionsList"

            action_value = f'/Soc/TriggerChangeWorkflowState/{self.SOC_id}?trigger=AcceptForApply'
            logging.info(f"🔧 Setting action: {action_value}")

            set_action_script = """
                var dropdown = $('#ActionsList').data('kendoDropDownList');
                dropdown.value(arguments[0]);
                dropdown.trigger('change');
            """
            self.driver.execute_script(set_action_script, action_value)
            logging.info("✅ Action set")

            WebDriverWait(self.driver, 10).until(
                lambda _: self.driver.execute_script(
                    "return $('#ActionsList').data('kendoDropDownList').value() === arguments[0];",
                    action_value
                )
            )

            # Apply action
            self.click_button((By.ID, 'ApplyActionButton'))

            # Wait for status change
            logging.info(f"⏳ Waiting for status change from '{old_status}'...")
            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                lambda _: self.get_SOC_status()[0] and self.SOC_status != old_status
            )

            # Verify new status
            success, error_msg, severity = self.get_SOC_status()
            if not success:
                return False, error_msg, severity
                
            logging.info(f"✅ SOC accepted - new status: '{self.SOC_status}'")
            return True, None, None

        except NoSuchWindowException:
            return False, "Browser closed during SOC acceptance", ErrorLevel.TERMINAL
        except Exception as e:
            return False, f"Failed to accept SOC {self.SOC_id}: {e}", ErrorLevel.FATAL

    def update_points(self) -> OperationResult:
        """Returns (success, error_message, severity)"""
        try:
            item_xpath = f"//select[@id='CurrentStateSelect' and not(@disabled)]"
            sel_items = self.driver.find_elements(By.XPATH, item_xpath)
            logging.info(f"Updating {len(sel_items)} points")

            for point_index, sel_item in enumerate(sel_items, start=1):
                drop = Select(sel_item)
                if len(drop.options) > 1:
                    drop.select_by_index(self.FINAL_STATE_DROPDOWN_INDEX)
                    selected_text = drop.first_selected_option.text
                    logging.info(f"✅ Point {point_index} updated to {selected_text}")
            
            return True, None, None
        except Exception as e:
            return False, f"Failed to update points: {e}", ErrorLevel.RECOVERABLE

    # =========================================================================
    # NAVIGATION AND WORKFLOW MANAGEMENT
    # =========================================================================

    def navigate_to_soc_and_check_status(self) -> OperationResult:
        """Returns (success, error_message, severity)"""
        try:
            SOC_view_base_link = self._base_link + r"Soc/Details/"
            self.driver.get(SOC_view_base_link + self.SOC_id)
            
            success, error_msg = self.error_404_not_present_check()
            if not success:
                return False, error_msg, ErrorLevel.FATAL
            
            is_correct_page, error_msg = self.url_contains_SOC_Details_check()
            if not is_correct_page:
                return False, error_msg, ErrorLevel.FATAL

            # Get and check status
            success, error_msg, severity = self.get_SOC_status()
            if not success:
                return False, error_msg, severity
            
            logging.info(f"🔍 Initial SOC status: '{self.SOC_status}'")

            # Handle SOC acceptance if needed
            if self.SOC_status == self.SOC_status_approved_for_apply:
                logging.info("🔄 SOC needs accept - switching to OAC role")
                
                success, error_msg, severity = self.switch_role('OAC')
                if not success:
                    return False, error_msg, severity
                    
                self.driver.get(SOC_view_base_link + self.SOC_id)
                
                success, error_msg, severity = self.accept_SOC_to_apply()
                if not success:
                    return False, error_msg, severity
                    
                success, error_msg, severity = self.get_SOC_status()
                if not success:
                    return False, error_msg, severity
                    
                logging.info(f"🔍 Status after accept: '{self.SOC_status}'")

            # Final status check
            if self.SOC_status not in self.good_statuses:
                error_msg = f'SOC {self.SOC_id} status "{self.SOC_status}" - cannot proceed'
                logging.error(error_msg)
                locator = (By.XPATH, "//div[@id='issowFormContainer']//div[contains(@class, 'user-form')]")
                self.inject_error_message(f'❌ SOC {self.SOC_id} status "{self.SOC_status}"',
                                        locator, style_addons={'width': '100%', 'align': 'center'})
                return False, error_msg, ErrorLevel.FATAL

            return True, None, None

        except NoSuchWindowException:
            return False, "Browser closed during navigation", ErrorLevel.TERMINAL
        except Exception as e:
            return False, f"Navigation to SOC failed: {e}", ErrorLevel.FATAL

    def process_soc_roles(self) -> OperationResult:
        """Returns (success, error_message, severity)"""
        try:
            for SOC_role in self.SOC_roles:
                # Switch role
                success, error_msg, severity = self.switch_role(SOC_role)
                if not success:
                    return False, error_msg, severity

                # Navigate to update page
                SOC_update_base_link = self._base_link + r"Soc/UpdateOverride/"
                self.driver.get(SOC_update_base_link + self.SOC_id)

                success, error_msg = self.SOC_locked_check()
                if not success:
                    return False, error_msg, ErrorLevel.FATAL
                
                success, error_msg = self.access_denied_check()
                if not success:
                    return False, error_msg, ErrorLevel.FATAL

                # Wait for points and update them
                WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                    lambda _: len(self.driver.find_elements(By.XPATH, "//select[@id='CurrentStateSelect' and not(@disabled)]")) >= 1
                )

                success, error_msg, severity = self.update_points()
                if not success:
                    return False, error_msg, severity
                    
                self.wait_for_user_confirmation()

            return True, None, None

        except NoSuchWindowException:
            return False, "Browser closed during role processing", ErrorLevel.TERMINAL
        except Exception as e:
            return False, f"Failed to process SOC roles: {e}", ErrorLevel.FATAL

    # =========================================================================
    # USER INTERACTION METHODS
    # =========================================================================

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
            logging.error("⚠️ User closed browser")
            self.safe_exit()
        except Exception as e:
            return False, f"Failed waiting for confirm: {e}", ErrorLevel.FATAL

    # =========================================================================
    # ERROR HANDLING AND EXECUTION CONTROL
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

    # =========================================================================
    # MAIN EXECUTION WORKFLOW
    # =========================================================================

    def run(self, standalone=False):
        if not self._initialized:
            logging.error("❌ Controller not properly initialized")
            return
            
        if standalone:
            self.navigate_to_base()
            self.enter_credentials_and_prepare_soc_input()
                        
            success, error_msg = self.wait_for_soc_input_and_submit()
            if not success:
                # this is the way to use with function calls from the mixin
                # we convert it to our error handling approach
                if not self._handle_result(False, error_msg, ErrorLevel.FATAL):
                    return
                    
        # Main workflow with proper severity handling
        success, error_msg, severity = self.navigate_to_soc_and_check_status()
        if not self._handle_result(success, error_msg, severity):
            return
        
        success, error_msg, severity = self.process_soc_roles()
        if not self._handle_result(success, error_msg, severity):
            return
            
        self.safe_exit()


if __name__ == "__main__":
    try:
        bot = SOC_Controller()
        bot.run(standalone=True)
    except Exception as e:
        print(f"❌ Failed to start controller: {e}")
        logging.error(f"❌ Controller startup failed: {e}")