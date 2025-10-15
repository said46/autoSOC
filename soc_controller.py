# soc_controller.py
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (NoSuchElementException, TimeoutException)
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

import configparser
import logging

from base_web_bot import BaseWebBot
from soc_base_mixin import SOC_BaseMixin
from error_types import ErrorLevel, OperationResult


class SOC_Controller(SOC_BaseMixin):
    """
    Specialized bot for SOC overrides automation with enhanced Kendo UI interaction.
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
                      
        self._initialized = True

    def load_configuration(self) -> OperationResult:
        """Returns (success, error_message, severity)"""
        try:
            import configparser
            config = configparser.ConfigParser(interpolation=None)
            config.read(self.config_file, encoding="utf8")

            # ✅ Common configuration (includes SOC_id)
            success, error_msg, severity = self.load_common_configuration(config)
            if not success:
                return False, error_msg, severity

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
            return False, f"Configuration failed: {str(e)}", ErrorLevel.FATAL

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
                self.warning_message = f"⚠️ Database config incomplete: {str(e)}. Disabling database features."
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
    # KENDO WIDGET INTERACTION METHODS
    # =========================================================================

    def _wait_for_kendo_widget_ready(self, widget_id: str, timeout: int = 10) -> bool:
        """
        Wait for Kendo widget to be fully initialized and ready.
        Based on typical Kendo UI patterns from app.min.js.
        """
        if not self.is_browser_alive():
            return False
            
        try:
            return WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script(f"""
                    var widget = $('#{widget_id}').data('kendoDropDownList');
                    if (!widget) return false;
                    
                    // Check if widget has data source and data is loaded
                    var dataSource = widget.dataSource;
                    if (!dataSource) return false;
                    
                    var hasData = dataSource.data().length > 0;
                    var isEnabled = !widget.wrapper.hasClass('k-state-disabled');
                    var isVisible = widget.wrapper.is(':visible');
                    
                    return hasData && isEnabled && isVisible;
                """)
            )
        except TimeoutException:
            logging.warning(f"⏰ Timeout waiting for Kendo widget: {widget_id}")
            return False

    def _set_kendo_dropdown_value(self, dropdown_id: str, value: str) -> bool:
        """
        Set Kendo dropdown value with proper event triggering.
        Mimics JavaScript behavior from app.min.js.
        """
        if not self.is_browser_alive():
            return False
            
        try:
            success = self.driver.execute_script(f"""
                var dropdown = $('#{dropdown_id}').data('kendoDropDownList');
                if (!dropdown) {{
                    console.log('Kendo dropdown not found: {dropdown_id}');
                    return false;
                }}
                
                var oldValue = dropdown.value();
                
                // Set the value
                dropdown.value('{value}');
                
                // Trigger change event if value actually changed
                if (oldValue !== '{value}') {{
                    // Trigger Kendo change event
                    dropdown.trigger('change', {{
                        sender: dropdown,
                        value: '{value}',
                        oldValue: oldValue
                    }});
                    
                    // Also trigger DOM change event
                    var element = $('#{dropdown_id}')[0];
                    if (element) {{
                        var domEvent = new Event('change', {{ bubbles: true }});
                        element.dispatchEvent(domEvent);
                    }}
                }}
                
                return true;
            """)
            
            if success:
                logging.info(f"✅ Kendo dropdown set: {dropdown_id} = {value}")
                # Wait for widget to update
                self._wait_for_kendo_widget_ready(dropdown_id, 5)
            
            return success
            
        except Exception as e:
            logging.error(f"❌ Failed to set Kendo dropdown {dropdown_id}: {e}")
            return False

    # =========================================================================
    # STATUS AND ROLE MANAGEMENT - ENHANCED
    # =========================================================================

    def get_SOC_status(self) -> OperationResult:
        """
        Get SOC status with multiple fallback methods.
        Uses both XPath and CSS selectors for robustness.
        """
        if not self.is_browser_alive():
            return False, "Browser closed", ErrorLevel.TERMINAL
            
        try:
            # Method 1: Try multiple XPath patterns
            status_scripts = [
                # Common pattern for status labels
                """
                return document.evaluate(
                    "//label[contains(text(), 'Состояние')]/following-sibling::text()[1]",
                    document,
                    null,
                    XPathResult.STRING_TYPE,
                    null
                ).stringValue.trim();
                """,
                # Alternative pattern for different UI layouts
                """
                return document.evaluate(
                    "//span[contains(text(), 'Состояние')]/following-sibling::span",
                    document,
                    null,
                    XPathResult.STRING_TYPE,
                    null
                ).stringValue.trim();
                """,
                # CSS selector fallback
                """
                var statusEl = document.querySelector('[class*="status"], [id*="Status"]');
                return statusEl ? statusEl.textContent.trim() : '';
                """
            ]
            
            status = ''
            for script in status_scripts:
                status = self.driver.execute_script(script)
                if status and status.strip():
                    break
            
            if not status:
                return False, "SOC status not found using any detection method", ErrorLevel.FATAL
                
            logging.info(f"👆 SOC {self.SOC_id} status: '{status}'")
            self.SOC_status = status.lower()
            return True, None, None
            
        except Exception as e:
            return False, f"Failed to get SOC status: {str(e)}", ErrorLevel.FATAL

    def get_current_role(self) -> tuple[bool, str | None, ErrorLevel]:
        """Get current role with enhanced detection."""
        if not self.is_browser_alive():
            return False, "Browser closed", ErrorLevel.TERMINAL
            
        try:
            # Try multiple selectors for role detection
            role_selectors = [
                "//span[@class='k-state-active' and contains(text(), 'Роль:')]",
                "//span[contains(text(), 'Роль:')]",
                "//div[contains(text(), 'Роль:')]",
                ".role-selector, [class*='role']"
            ]
            
            role_element = None
            for selector in role_selectors:
                try:
                    if selector.startswith('//') or selector.startswith('.') or selector.startswith('['):
                        role_element = self.driver.find_element(By.XPATH, selector) if selector.startswith('//') else self.driver.find_element(By.CSS_SELECTOR, selector)
                    if role_element:
                        break
                except NoSuchElementException:
                    continue
            
            if not role_element:
                return False, "Role element not found with any selector", ErrorLevel.RECOVERABLE
            
            role_text = role_element.text.strip()
            if "Роль:" in role_text:
                role_name = role_text.split("Роль:")[1].strip()
                logging.info(f"👤 Current role: '{role_name}'")
                return True, role_name, ErrorLevel.RECOVERABLE
            else:
                return False, f"Unexpected role format: '{role_text}'", ErrorLevel.RECOVERABLE

        except Exception as e:
            return False, f"Could not determine role: {str(e)}", ErrorLevel.RECOVERABLE

    def switch_role(self, role: str) -> OperationResult:
        """Switch role with proper Kendo widget interaction."""
        if not self.is_browser_alive():
            return False, "Browser closed", ErrorLevel.TERMINAL
            
        try:
            # Check current role first
            success, current_role_or_error, severity = self.get_current_role()
            if not success:
                return False, current_role_or_error, severity

            if current_role_or_error == role:
                logging.info(f"✅ Already in {role} role")
                return True, None, None

            # Navigate to role change page
            self.driver.get(self._base_link + r"User/ChangeRole")
            
            # Wait for page and Kendo widgets to be ready
            if not self.wait_for_page_fully_ready(check_kendo=True):
                return False, "Role change page failed to load properly", ErrorLevel.FATAL

            # Wait specifically for the role dropdown
            if not self._wait_for_kendo_widget_ready('CurrentRoleName', 10):
                return False, "Role dropdown not ready", ErrorLevel.FATAL

            # Set role using Kendo API
            if not self._set_kendo_dropdown_value('CurrentRoleName', role):
                return False, f"Failed to set role to {role}", ErrorLevel.FATAL

            # Wait for role to be applied
            WebDriverWait(self.driver, 10).until(
                lambda _: self.driver.execute_script(
                    f"return $('#CurrentRoleName').data('kendoDropDownList').value() === '{role}';"
                )
            )

            # Click confirm button
            if not self.click_button((By.ID, 'ConfirmHeader')):
                return False, "Confirm button not found or not clickable", ErrorLevel.FATAL

            # Wait for role change to take effect
            self.wait_for_page_fully_ready()
            
            # Verify role change was successful
            success, new_role_or_error, severity = self.get_current_role()
            if not success or new_role_or_error != role:
                return False, f"Role switch verification failed: expected {role}, got {new_role_or_error}", ErrorLevel.FATAL

            logging.info(f"✅ Successfully switched to {role} role")
            return True, None, None

        except Exception as e:
            return False, f"Failed to switch role to {role}: {str(e)}", ErrorLevel.FATAL

    # =========================================================================
    # SOC WORKFLOW OPERATIONS - ENHANCED
    # =========================================================================

    def accept_SOC_to_apply(self) -> OperationResult:
        """Accept SOC for application with proper Kendo interaction."""
        if not self.is_browser_alive():
            return False, "Browser closed", ErrorLevel.TERMINAL
            
        try:
            # Get current status
            success, error_msg, severity = self.get_SOC_status()
            if not success:
                return False, error_msg, severity
            
            old_status = self.SOC_status
            logging.info(f"⏳ Current status: '{old_status}' - accepting for apply")

            # Wait for page and action dropdown
            if not self.wait_for_page_fully_ready(check_kendo=True):
                return False, "SOC page not ready for action selection", ErrorLevel.FATAL

            # Wait for actions dropdown specifically
            if not self._wait_for_kendo_widget_ready('ActionsList', 10):
                return False, "Actions dropdown not ready", ErrorLevel.FATAL

            # Set action value
            action_value = f'/Soc/TriggerChangeWorkflowState/{self.SOC_id}?trigger=AcceptForApply'
            logging.info(f"🔧 Setting action: {action_value}")

            if not self._set_kendo_dropdown_value('ActionsList', action_value):
                return False, "Failed to set action in dropdown", ErrorLevel.FATAL

            # Wait for action to be set
            WebDriverWait(self.driver, 10).until(
                lambda _: self.driver.execute_script(
                    "return $('#ActionsList').data('kendoDropDownList').value() === arguments[0];",
                    action_value
                )
            )

            # Apply action
            if not self.click_button((By.ID, 'ApplyActionButton')):
                return False, "Apply action button not found or not clickable", ErrorLevel.FATAL

            # Wait for status change with timeout
            logging.info(f"⏳ Waiting for status change from '{old_status}'...")
            try:
                WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                    lambda _: self.get_SOC_status()[0] and self.SOC_status != old_status
                )
            except TimeoutException:
                return False, f"Timeout waiting for status change from '{old_status}'", ErrorLevel.FATAL

            # Verify new status
            success, error_msg, severity = self.get_SOC_status()
            if not success:
                return False, error_msg, severity
                
            logging.info(f"✅ SOC accepted - new status: '{self.SOC_status}'")
            return True, None, None

        except Exception as e:
            return False, f"Failed to accept SOC {self.SOC_id}: {str(e)}", ErrorLevel.FATAL

    def update_points(self) -> OperationResult:
        """Update points with enhanced error handling."""
        if not self.is_browser_alive():
            return False, "Browser closed", ErrorLevel.TERMINAL
            
        try:
            item_xpath = f"//select[@id='CurrentStateSelect' and not(@disabled)]"
            sel_items = self.driver.find_elements(By.XPATH, item_xpath)
            logging.info(f"Updating {len(sel_items)} points")

            for point_index, sel_item in enumerate(sel_items, start=1):
                if not self.is_browser_alive():
                    return False, "Browser closed during points update", ErrorLevel.TERMINAL
                    
                drop = Select(sel_item)
                if len(drop.options) > 1:
                    try:
                        drop.select_by_index(self.FINAL_STATE_DROPDOWN_INDEX)
                        selected_text = drop.first_selected_option.text
                        logging.info(f"✅ Point {point_index} updated to {selected_text}")
                    except Exception as e:
                        logging.warning(f"⚠️ Failed to update point {point_index}: {e}")
                        continue
            
            return True, None, None
        except Exception as e:
            return False, f"Failed to update points: {str(e)}", ErrorLevel.RECOVERABLE

    # =========================================================================
    # NAVIGATION AND WORKFLOW MANAGEMENT - ENHANCED
    # =========================================================================

    def navigate_to_soc_and_check_status(self) -> OperationResult:
        """Navigate to SOC with comprehensive status checking."""
        if not self.is_browser_alive():
            return False, "Browser closed", ErrorLevel.TERMINAL
            
        try:
            SOC_view_base_link = self._base_link + r"Soc/Details/"
            self.driver.get(SOC_view_base_link + self.SOC_id)
            
            # Wait for page to load completely
            if not self.wait_for_page_fully_ready():
                return False, "SOC details page failed to load", ErrorLevel.FATAL
            
            # Security and access checks
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
                    
                # Navigate back to SOC details
                self.driver.get(SOC_view_base_link + self.SOC_id)
                if not self.wait_for_page_fully_ready():
                    return False, "SOC details page failed to load after role switch", ErrorLevel.FATAL
                
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

        except Exception as e:
            return False, f"Navigation to SOC failed: {str(e)}", ErrorLevel.FATAL

    def process_soc_roles(self) -> OperationResult:
        """Process SOC roles with enhanced navigation and error handling."""
        if not self.is_browser_alive():
            return False, "Browser closed", ErrorLevel.TERMINAL
            
        try:
            for SOC_role in self.SOC_roles:
                if not self.is_browser_alive():
                    return False, "Browser closed during role processing", ErrorLevel.TERMINAL
                    
                # Switch role
                success, error_msg, severity = self.switch_role(SOC_role)
                if not success:
                    return False, error_msg, severity

                # Navigate to update page
                SOC_update_base_link = self._base_link + r"Soc/UpdateOverride/"
                self.driver.get(SOC_update_base_link + self.SOC_id)

                # Wait for page load
                if not self.wait_for_page_fully_ready():
                    return False, f"SOC update page failed to load for role {SOC_role}", ErrorLevel.FATAL

                # Security checks
                success, error_msg = self.SOC_locked_check()
                if not success:
                    return False, error_msg, ErrorLevel.FATAL
                
                success, error_msg = self.access_denied_check()
                if not success:
                    return False, error_msg, ErrorLevel.FATAL

                # Wait for points to be available
                try:
                    WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                        lambda _: len(self.driver.find_elements(By.XPATH, "//select[@id='CurrentStateSelect' and not(@disabled)]")) >= 1
                    )
                except TimeoutException:
                    return False, f"No points found to update for role {SOC_role}", ErrorLevel.FATAL

                # Update points
                success, error_msg, severity = self.update_points()
                if not success:
                    return False, error_msg, severity
                    
                # Wait for user confirmation
                success, error_msg, severity = self.wait_for_user_confirmation()
                if not success:
                    return False, error_msg, severity

            return True, None, None

        except Exception as e:
            return False, f"Failed to process SOC roles: {str(e)}", ErrorLevel.FATAL

    # =========================================================================
    # USER INTERACTION METHODS
    # =========================================================================

    def wait_for_user_confirmation(self) -> OperationResult:
        """Wait for user confirmation with enhanced error handling."""
        if not self.is_browser_alive():
            return True, "Browser already closed by user", ErrorLevel.RECOVERABLE
            
        try:
            msg = '⚠️  Скрипт ожидает нажатия кнопки "Подтвердить".'
            xpath = "//div[@id='bottomWindowButtons']/div"
            
            success = self._inject_message(msg, (By.XPATH, xpath), {'color': 'lawngreen'})
            if not success:
                logging.warning("⚠️ Failed to inject confirmation message, but continuing...")
            
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(
                EC.title_is(self.EXPECTED_HOME_PAGE_TITLE)
            )
            logging.info("🏁 Confirm pressed, home page loaded")
            return True, None, None
            
        except TimeoutException:
            if not self.is_browser_alive():
                return True, "Browser closed by user during confirmation wait", ErrorLevel.RECOVERABLE
            return True, "User confirmation timeout - continuing anyway", ErrorLevel.RECOVERABLE
            
        except Exception as e:
            if not self.is_browser_alive():
                return True, "Browser closed by user during confirmation wait", ErrorLevel.RECOVERABLE
            error_msg = f"Failed waiting for confirm: {e}"
            logging.error(error_msg)
            return False, error_msg, ErrorLevel.FATAL

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
                if not self._handle_result(False, error_msg, ErrorLevel.FATAL):
                    return
                    
        # Main workflow with proper severity handling
        success, error_msg, severity = self.navigate_to_soc_and_check_status()
        if not self._handle_result(success, error_msg, severity):
            return
        
        success, error_msg, severity = self.process_soc_roles()
        if not self._handle_result(success, error_msg, severity):
            return
            
if __name__ == "__main__":
    try:
        bot = SOC_Controller()
        bot.run(standalone=True)
    except Exception as e:
        print(f"❌ Failed to start controller: {str(e)}")
        logging.error(f"❌ Controller startup failed: {str(e)}")
