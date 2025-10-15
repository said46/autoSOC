# soc_base_mixin.py
import re
import base64
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import (NoSuchElementException, NoSuchWindowException,
                                      WebDriverException, InvalidSelectorException, TimeoutException)
import configparser

from soc_DB import SQLQueryDirect
from error_types import ErrorLevel, OperationResult
from base_web_bot import BaseWebBot

class WaitForSOCInput:
    """
    Custom wait condition for monitoring SOC ID input field.
    Handles user browser closure gracefully.
    """

    def __init__(self, locator, soc_mixin):
        self.locator = locator
        self.soc_mixin = soc_mixin
        self.last_value = ""

    def __call__(self, driver):
        try:
            # Respect user's ability to close browser at any time
            if not self.soc_mixin.is_browser_alive():
                return True  # Break wait if browser closed

            injected_input = driver.find_element(*self.locator)
            current_value = injected_input.get_attribute("value")

            if current_value != self.last_value:
                is_valid, message = self.soc_mixin._validate_soc_input(current_value)
                self.soc_mixin._update_input_ui(is_valid, message)
                self.last_value = current_value

            enter_pressed = injected_input.get_attribute('data-enter-pressed') == 'true'
            if enter_pressed:
                is_valid, message = self.soc_mixin._validate_soc_input(current_value)
                self.soc_mixin._update_input_ui(is_valid, message)

                if is_valid:
                    driver.execute_script("""
                        var input = document.getElementById('InjectedInput');
                        input.removeAttribute('data-enter-pressed');
                        input.disabled = true;
                    """)
                    return True
                else:
                    self.soc_mixin._update_input_ui(False, "❌ Invalid - " + message.split('⚠️ ')[-1])
                    driver.execute_script("""
                        var input = document.getElementById('InjectedInput');
                        input.removeAttribute('data-enter-pressed');
                    """)

            return False
        except (NoSuchWindowException, WebDriverException):
            return True  # Browser closed - break wait

class WidgetReady:
    """
    Custom wait condition for checking Kendo widget readiness.
    """

    def __init__(self, widget_id):
        self.widget_id = widget_id

    def __call__(self, driver):
        try:
            # Check browser state first
            debug_info = driver.execute_script(f"""
                try {{
                    var element = document.getElementById('{self.widget_id}');
                    var exists = !!element;
                    var kendoWidget = exists ? $(element).data('kendoDropDownList') : null;
                    var widgetType = kendoWidget ? kendoWidget.toString() : 'none';
                    var hasDataSource = kendoWidget && kendoWidget.dataSource;
                    var isLoading = hasDataSource ? kendoWidget.dataSource._loading : false;
                                       
                    return exists && kendoWidget && !isLoading;
                }} catch (e) {{
                    return false;
                }}
            """)
            
            logging.info(f"🔍 Widget {self.widget_id} ready: {debug_info}")
            return bool(debug_info)
            
        except Exception as e:
            logging.error(f"❌ Widget check exception for {self.widget_id}: {e}")
            return False

class SOC_BaseMixin(BaseWebBot):
    """
    Enhanced mixin class with user-centric SOC automation.
    
    Maintains core principles:
    - Browser always under user control
    - User can close browser at any time
    - All communication via HTML injection
    - Graceful handling of browser closure
    """

    EXPECTED_HOME_PAGE_TITLE = "СНД - Домашняя страница"

    def __init__(self):
        super().__init__()  # Ensure BaseWebBot is properly initialized
        self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
        self.SOC_ID_PATTERN = r"^\d{7,8}$"
        self.ERROR_MESSAGE_ENDING = ", the script cannot proceed, close this window."
        self.config_file = 'SOC.ini'
        self.SOC_id = ''

    # ===== ENHANCED KENDO WIDGET METHODS =====

    def _wait_for_kendo_widget_ready(self, widget_id: str, timeout: int = 10) -> bool:
        """
        Wait for Kendo widget to be fully initialized and ready.
        Returns False if browser closed by user during wait.
        """
        if not self.safe_browser_operation("Kendo widget wait"):
            return False
            
        try:
            return WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script(f"""
                    var widget = $('#{widget_id}').data('kendoDropDownList');
                    if (!widget) return false;
                    
                    var dataSource = widget.dataSource;
                    if (!dataSource) return false;
                    
                    var hasData = dataSource.data().length > 0;
                    var isEnabled = !widget.wrapper.hasClass('k-state-disabled');
                    var isVisible = widget.wrapper.is(':visible');
                    
                    return hasData && isEnabled && isVisible;
                """)
            )
        except TimeoutException:
            # Check if browser closed during wait
            if not self.is_browser_alive():
                logging.info(f"🏁 Browser closed by user while waiting for widget: {widget_id}")
                return False
            logging.warning(f"⏰ Timeout waiting for Kendo widget: {widget_id}")
            return False

    def _set_kendo_dropdown_value(self, dropdown_id: str, value: str) -> bool:
        """
        Set Kendo dropdown value with proper event triggering.
        Returns False if browser closed by user.
        """
        if not self.safe_browser_operation("Kendo dropdown set"):
            return False
            
        try:
            success = self.driver.execute_script(f"""
                var dropdown = $('#{dropdown_id}').data('kendoDropDownList');
                if (!dropdown) {{
                    console.log('Kendo dropdown not found: {dropdown_id}');
                    return false;
                }}
                
                var oldValue = dropdown.value();
                dropdown.value('{value}');
                
                if (oldValue !== '{value}') {{
                    dropdown.trigger('change', {{
                        sender: dropdown,
                        value: '{value}',
                        oldValue: oldValue
                    }});
                    
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
                self._wait_for_kendo_widget_ready(dropdown_id, 5)
            
            return success
            
        except Exception as e:
            # Check if browser closed during operation
            if not self.is_browser_alive():
                logging.info(f"🏁 Browser closed by user during dropdown set: {dropdown_id}")
                return False
            logging.error(f"❌ Failed to set Kendo dropdown {dropdown_id}: {e}")
            return False

    def _get_dropdown_data(self, dropdown_id: str) -> dict:
        """
        Get complete dropdown data including items and selection.
        Returns error dict if browser closed.
        """
        if not self.safe_browser_operation("get dropdown data"):
            return {'error': 'browser_closed'}
            
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
            if not self.is_browser_alive():
                return {'error': 'browser_closed'}
            logging.error(f"❌ Failed to get dropdown data for {dropdown_id}: {e}")
            return {'error': str(e)}

    def _find_dropdown_item_by_text(self, dropdown_id: str, search_text: str) -> dict:
        """
        Find dropdown item by partial text match.
        Returns None if browser closed or item not found.
        """
        if not self.safe_browser_operation("find dropdown item"):
            return None
            
        data = self._get_dropdown_data(dropdown_id)
        if data.get('error') or not data.get('items'):
            return None
            
        search_lower = search_text.lower()
        for item in data['items']:
            if search_lower in item['text'].lower():
                return item
        return None

    # ===== CONSISTENT ERROR HANDLING =====
    
    def _handle_result(self, success: bool, error_msg: str | None, severity: ErrorLevel) -> bool:
        """
        Consistent error handling across all SOC classes.
        Returns True if execution should continue, False if should stop.
        """
        if not self.is_browser_alive():
            logging.info("🏁 Browser closed by user during operation")
            return False
            
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
                return True
        return True

    def _safe_browser_operation(self, operation_name: str) -> bool:
        """
        Unified browser state check for operations.
        Returns True if browser is alive and operation can proceed.
        """
        if not self.is_browser_alive():
            logging.info(f"🏁 Browser closed by user during: {operation_name}")
            return False
        return True

    # ===== CONFIGURATION METHODS =====
    
    def load_common_configuration(self, config: configparser.ConfigParser) -> OperationResult:
        """Load configuration common to all SOC bots with enhanced error handling"""
        try:           
            self.user_name = config.get('Settings', 'user_name', fallback='xxxxxx')
            raw_password = config.get('Settings', 'password', fallback='******')
            self.password = self.process_password(raw_password)

            if '\n' in self.password:
                self.password = 'INCORRECT PASSWORD'

            self._base_link = config.get('Settings', 'base_link', fallback='http://eptw.sakhalinenergy.ru/')
            self.MAX_WAIT_USER_INPUT_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_USER_INPUT_DELAY_SECONDS', fallback=300)
            self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_PAGE_LOAD_DELAY_SECONDS', fallback=30)
            self.USE_HARD_TIMEOUT_FOR_WIDGET_READY = config.getboolean('Settings', 'USE_HARD_TIMEOUT_FOR_WIDGET_READY', fallback=False)
            self.HARD_TIMEOUT_FOR_WIDGET_READY = config.getfloat('Settings', 'HARD_TIMEOUT_FOR_WIDGET_READY', fallback=1)
            
            self.SOC_id = config.get('Settings', 'SOC_id', fallback='')
            logging.info(f"🔧 Loaded SOC_id from config: '{self.SOC_id}'") 
            
            return True, None, None
        except Exception as e:
            return False, f"Loading common configuration failed: {e}", ErrorLevel.FATAL

    # ===== PASSWORD PROCESSING =====

    def process_password(self, password: str) -> str:
        """Decode base64 encoded password or return plain text as fallback."""
        encoded_password = password
        try:
            decoded_password = base64.b64decode(password.encode()).decode()
            logging.info(f"🔐 Password decoded successfully")
            return decoded_password
        except Exception as e:
            logging.error(f"🔐 Failed to decode password: {str(e)}, using plain text password")
            return encoded_password

    # ===== LOGIN AND CREDENTIAL MANAGEMENT =====

    def enter_credentials_and_prepare_soc_input(self) -> OperationResult:
        """
        Enhanced credential entry with proper error handling.
        Returns OperationResult instead of None.
        """
        if not self._safe_browser_operation("credential entry"):
            return False, "Browser closed by user", ErrorLevel.TERMINAL
            
        try:
            self.driver.find_element(By.ID, "UserName").send_keys(self.user_name)
            if self.password != "INCORRECT PASSWORD":
                self.driver.find_element(By.ID, "Password").send_keys(self.password)
            else:
                error_msg = "❌ Password contains line break"
                logging.error(error_msg)
                return False, error_msg, ErrorLevel.FATAL
                
            # Show warning message if any
            if hasattr(self, 'warning_message') and self.warning_message:
                self.inject_info_message(self.warning_message, style_addons={'color': 'darkorange'})

            # Inject SOC ID input field
            self.inject_SOC_id_input()
            
            return True, None, None
            
        except Exception as e:
            if not self.is_browser_alive():
                return False, "Browser closed by user during credential entry", ErrorLevel.TERMINAL
            error_msg = f"Failed to enter credentials: {str(e)}"
            logging.error(error_msg)
            return False, error_msg, ErrorLevel.FATAL

    # ===== SECURITY AND ACCESS CHECKS =====

    def SOC_locked_check(self) -> tuple[bool, str | None]:
        """Check if SOC is locked and handle accordingly by showing error message."""
        if not self._safe_browser_operation("SOC locked check"):
            return False, "Browser closed by user"
            
        try:
            locked_xpath = "//div[@class='text-danger validation-summary-valid']//li[contains(., 'заблокирован')]"
            li_locked = self.driver.find_element(By.XPATH, locked_xpath)
            error_msg = f"❌ SOC is locked: {li_locked.text}"
            return False, error_msg
        except NoSuchElementException:
            logging.info("✅ Success: SOC is not locked")
            return True, None
        except Exception as e:
            if not self.is_browser_alive():
                return False, "Browser closed by user during SOC lock check"
            logging.error(f"❌ Error during SOC lock check: {str(e)}")
            return False, f"Error checking SOC lock: {str(e)}"

    def access_denied_check(self) -> tuple[bool, str | None]:
        """Check for Access Denied error and handle accordingly."""
        if not self._safe_browser_operation("access denied check"):
            return False, "Browser closed by user"
            
        try:
            access_denied_xpath = "//div[contains(@class, 'panel-line-danger')]//li[contains(text(), 'I DON'T KNOW WHAT TO FIND YET')]"
            self.driver.find_element(By.XPATH, access_denied_xpath)
            error_msg = f"❌ Access denied, SOC {self.SOC_id} may be archived or in improper state"
            logging.error(error_msg)
            return False, error_msg
        except NoSuchElementException:
            logging.info("✅ Success: no access denied issue")
            return True, None
        except InvalidSelectorException:
            logging.warning("⚠️ InvalidSelectorException in access_denied_check() - temporary disabled")
            return True, None
        except Exception as e:
            if not self.is_browser_alive():
                return False, "Browser closed by user during access check"
            logging.error(f"❌ Error during access denied check: {str(e)}")
            return False, f"Error checking access: {str(e)}"

    def login_failed_check(self) -> tuple[bool, str | None]:
        """Check for login failure and handle accordingly."""
        if not self._safe_browser_operation("login failed check"):
            return False, "Browser closed by user"
            
        try:
            login_failed_xpath = "//div[contains(@class, 'validation-summary-errors')]"
            self.driver.find_element(By.XPATH, login_failed_xpath)
            error_msg = "❌ Login issue, check the password in ini-file."
            return False, error_msg
        except NoSuchElementException:
            logging.info("✅ Success: no login issue")
            return True, None
        except Exception as e:
            if not self.is_browser_alive():
                return False, "Browser closed by user during login check"
            logging.error(f"❌ Error during login check: {str(e)}")
            return False, f"Error checking login: {str(e)}"

    def error_404_not_present_check(self) -> tuple[bool, str | None]:
        """Check if no 404 error is present on the page."""
        if not self._safe_browser_operation("404 check"):
            return False, "Browser closed by user"
            
        try:
            self.driver.find_element(By.XPATH, "//h1[contains(@class, 'text-danger') and contains(text(), '404')]")
            error_msg = f"❌ Error 404, probably SOC {self.SOC_id} does not exist"
            logging.error(error_msg)
            return False, error_msg
        except NoSuchElementException:
            logging.info("✅ Success: no error 404")
            return True, None
        except Exception as e:
            if not self.is_browser_alive():
                return False, "Browser closed by user during 404 check"
            logging.error(f"❌ Error during 404 check: {str(e)}")
            return False, f"Error checking 404: {str(e)}"

    def url_contains_SOC_Details_check(self) -> tuple[bool, str | None]:
        """Verify that the current URL contains the SOC Details path."""
        if not self._safe_browser_operation("URL check"):
            return False, "Browser closed by user"
            
        current_url = self.driver.current_url
        if "/Soc/Details/" not in current_url:
            error_message = f"❌ Wrong page loaded: {current_url}. Expected SOC Details page."
            logging.error(error_message)
            return False, error_message
        return True, None

    # ===== SOC INPUT FIELD MANAGEMENT =====

    def inject_SOC_id_input(self) -> bool:
        """
        Inject SOC ID input field into the login form with default value.
        Returns True if successful, False if browser closed.
        """
        if not self._safe_browser_operation("SOC input injection"):
            return False
            
        try:
            default_soc_id = getattr(self, 'SOC_id', '')
            
            js_code = f"""
                var container = document.createElement('div');
                container.style.cssText = 'margin-top: 10px;';

                var input = document.createElement('input');
                input.type = 'text';
                input.id = 'InjectedInput';
                input.className = "form-control control-lg";
                input.style.marginBottom = "5px";
                input.style.width = "100%";
                input.value = "{default_soc_id}";

                // Hide the original submit button AND prevent form submission
                var submitButton = document.querySelector('button[type="submit"]');
                if (submitButton) submitButton.style.display = 'none';

                // Prevent form submission on Enter in any field
                var form = document.querySelector('form');
                if (form) {{
                    form.addEventListener('keypress', function(e) {{
                        if (e.key === 'Enter') {{
                            e.preventDefault();
                            e.stopPropagation();
                        }}
                    }});
                }}

                container.appendChild(input);
                const referenceElement = document.getElementById('Password');
                referenceElement.insertAdjacentElement('afterend', container);
                input.focus();
                
                // Trigger initial validation if there's a default value
                if ("{default_soc_id}") {{
                    var event = new Event('input', {{ bubbles: true }});
                    input.dispatchEvent(event);
                }}
            """
            self.driver.execute_script(js_code)

            self._setup_input_monitoring()

            if default_soc_id:
                logging.info(f"✅ Injected SOC input field with default: {default_soc_id}")
            else:
                logging.info("✅ Injected SOC input field (no default)")
                
            return True

        except NoSuchWindowException:
            logging.info("🏁 Browser closed by user during SOC input injection")
            return False
        except Exception as e:
            if not self.is_browser_alive():
                logging.info("🏁 Browser closed by user during SOC input injection")
                return False
            logging.error(f"❌ Failed to inject SOC_id input field: {str(e)}")
            self.inject_error_message(f"❌ Failed to inject SOC_id input field.")
            return False

    def _setup_input_monitoring(self) -> bool:
        """
        Set up Python-based input monitoring and validation.
        Returns True if successful, False if browser closed.
        """
        if not self._safe_browser_operation("input monitoring setup"):
            return False
            
        try:
            # Add guide text using Python
            guide_js = """
                var guideText = document.createElement('div');
                guideText.id = 'InjectedGuideText';
                guideText.style.cssText = 'font-size: 12px; color: #666; margin-top: 5px; text-align: center;';
                guideText.textContent = '☝ Enter SOC number and press Enter';

                var input = document.getElementById('InjectedInput');
                input.parentNode.appendChild(guideText);
            """
            self.driver.execute_script(guide_js)

            # Set up Enter key listener with prevention of default behavior
            enter_listener_js = """
                document.getElementById('InjectedInput').addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') {
                        e.preventDefault(); // ⚠️ CRITICAL: Prevent form submission
                        e.stopPropagation(); // ⚠️ Prevent event bubbling
                        this.setAttribute('data-enter-pressed', 'true');
                    }
                });
            """
            self.driver.execute_script(enter_listener_js)
            return True

        except Exception as e:
            if not self.is_browser_alive():
                return False
            logging.error(f"❌ Failed to set up input monitoring: {str(e)}")
            return False

    def _update_input_ui(self, is_valid: bool, message: str) -> bool:
        """
        Update the input field UI based on validation result.
        Returns True if successful, False if browser closed.
        """
        if not self._safe_browser_operation("UI update"):
            return False
            
        try:
            color = 'green' if is_valid else 'orange'
            border_color = 'green' if is_valid else 'orange'

            js_code = f"""
                var input = document.getElementById('InjectedInput');
                var guideText = document.getElementById('InjectedGuideText');

                if (input) {{
                    input.style.borderColor = '{border_color}';
                    input.style.borderWidth = '{'2px' if border_color else ''}';
                }}

                if (guideText) {{
                    guideText.textContent = '{message}';
                    guideText.style.color = '{color}';
                }}
            """
            self.driver.execute_script(js_code)
            return True

        except Exception as e:
            if not self.is_browser_alive():
                return False
            logging.error(f"❌ Failed to update input UI: {str(e)}")
            return False

    # ===== SOC INPUT VALIDATION =====

    def _validate_soc_input(self, value: str) -> tuple[bool, str]:
        """
        Validate SOC input and return validation result and message.
        """
        if ' ' in value:
            return False, "⚠️ Spaces are not allowed in SOC ID"        
        
        value = value.strip()      
        
        if not value:
            return False, "⚠️ Empty value is not allowed"

        # Check against the full pattern
        pattern = re.compile(self.SOC_ID_PATTERN)
        min_digits = 4 if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID else 7
        if not pattern.match(value):
            return False, f"⚠️ SOC id must to be at least {min_digits} digits"

        return True, "✅ Valid - Press Enter to continue"

    # ===== SOC INPUT PROCESSING AND FORM SUBMISSION =====

    def wait_for_soc_input_and_submit(self) -> tuple[bool, str | None]:
        """
        Wait for SOC ID input and submit the form.
        Handles browser closure gracefully.
        """
        if not self._safe_browser_operation("SOC input wait"):
            return False, "Browser closed by user"
            
        try:
            # Wait for valid SOC ID input with timeout
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(
                WaitForSOCInput((By.ID, "InjectedInput"), self)
            )

            # Check if browser closed during wait
            if not self.is_browser_alive():
                return False, "Browser closed by user during SOC input wait"

            # Get the SOC_id from the injected input field
            raw_soc_id = self.driver.find_element(By.ID, "InjectedInput").get_attribute("value")
            logging.info(f"🔧 Raw SOC id is {raw_soc_id}, continue processing it")

            # Strip leading zero if SOC ID is 8 digits and starts with 0
            if len(raw_soc_id) == 8 and raw_soc_id.startswith('0'):
                self.SOC_id = raw_soc_id[1:]  # Remove the first character
                logging.info(f"🔧 Stripped leading zero: '{raw_soc_id}' -> '{self.SOC_id}'")
            else:
                self.SOC_id = raw_soc_id

            # Database logic for partial SOC IDs
            if hasattr(self, 'CONNECT_TO_DB_FOR_PARTIAL_SOC_ID') and self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
                if len(self.SOC_id) < 7:
                    try:
                        full_SOC_id = self.request_DB_for_SOC_id(self.SOC_id)
                        self.SOC_id = full_SOC_id
                        if self.SOC_id is None:
                            raise ValueError("SOC_id cannot be None")
                    except Exception as e:
                        logging.error(f"❌ Failed to request DB: {str(e)}")
                        self.inject_error_message(f"❌ Failed to request DB ({str(e)}).")
                        return False, str(e)

            logging.info(f"✅ Processed SOC id is {self.SOC_id}, continue submitting the form")
            
            # Submit the form
            success = self.submit_form_with_soc_id()
            if not success:
                return False, "Form submission failed"

            success, error_msg = self.login_failed_check()
            if not success:
                return False, error_msg

            return True, None

        except TimeoutException:
            # Check if browser closed during timeout
            if not self.is_browser_alive():
                return False, "Browser closed by user during SOC input timeout"
            error_msg = f"⏰ Timeout waiting for SOC ID input after {self.MAX_WAIT_USER_INPUT_DELAY_SECONDS} seconds."
            logging.error(error_msg)
            self.inject_error_message(error_msg)
            return False, error_msg
        except Exception as e:
            if not self.is_browser_alive():
                return False, "Browser closed by user during SOC input processing"
            error_msg = "❌ Failed to wait for SOC_id to be entered"
            logging.error(f"{error_msg}: {str(e)}")
            self.inject_error_message(error_msg)
            return False, error_msg

    def submit_form_with_soc_id(self) -> bool:
        """
        Submit the form with the self.SOC_id.
        Returns True if successful, False if browser closed or failed.
        """
        if not self._safe_browser_operation("form submission"):
            return False
            
        try:
            self.driver.execute_script("""
                var form = document.querySelector('form');
                form?.submit()
            """)
            logging.info(f"✅ Form submitted successfully with {self.SOC_id}")
            return True
        except Exception as e:
            if not self.is_browser_alive():
                return False
            logging.error(f"❌ Failed to submit the form: {str(e)}")
            self.inject_error_message(f"❌ Failed to submit the form.")
            return False

    # ===== DATABASE OPERATIONS =====

    def request_DB_for_SOC_id(self, SOC_id: str) -> str:
        """
        Query database for full SOC ID when partial ID is provided.
        """
        SQL = self.SQL_template.format(soc_id=SOC_id)

        with SQLQueryDirect(
            server=self.db_server,
            database=self.db_database,
            username=self.db_username,
            password=self.db_password
        ) as sql:
            results = sql.execute(SQL)
            if len(results) == 1:
                row = results[0]
                if 'Id' not in row:
                     raise ValueError("Database query result missing 'Id' key.")
                SOC_id_from_db = row['Id']
                try:
                    SOC_id_converted = str(SOC_id_from_db)
                except (TypeError, ValueError) as conv_error:
                    logging.error(f"❌ Failed to convert DB result '{SOC_id_from_db}' to string: {conv_error}")
                    raise ValueError(f"Database result '{SOC_id_from_db}' could not be converted to a valid string SOC ID: {conv_error}")
                
                SOC_id = SOC_id_converted
            else:
                raise ValueError(f"Expected 1 row, got {len(results)}")

        if not isinstance(SOC_id, str) or len(SOC_id) < 7:
            raise ValueError(f"{SOC_id} has to be string with len 7 or 8")

        return SOC_id

    # ===== PAGE READINESS METHODS =====
    
    def wait_for_page_fully_ready(self, 
                                check_dom: bool = True,
                                check_jquery: bool = True, 
                                check_kendo: bool = True,
                                specific_widgets: list = None,
                                timeout: int = None) -> bool:
        """
        Unified method to wait for page complete readiness including Kendo widgets.
        Returns False if browser closed by user during wait.
        """
        if not self._safe_browser_operation("page readiness check"):
            return False
                
        if timeout is None:
            timeout = self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS
          
        try:                
            wait = WebDriverWait(self.driver, timeout)
            
            # Step 1: DOM Ready (if requested)
            if check_dom:
                logging.info("⏳ Waiting for DOM ready state...")
                wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            
            # Step 2: jQuery (if requested)
            if check_jquery:
                logging.info("⏳ Waiting for jQuery...")
                wait.until(lambda d: d.execute_script("return typeof jQuery !== 'undefined'"))
            
            # Step 3: Kendo Framework (if requested)
            if check_kendo:
                logging.info("⏳ Waiting for Kendo framework...")
                wait.until(lambda d: d.execute_script("return typeof kendo !== 'undefined'"))
            
            # Step 4: Specific Widgets (if provided)
            if specific_widgets:
                logging.info(f"⏳ Waiting for {len(specific_widgets)} widgets: {specific_widgets}")
                
                if not self.USE_HARD_TIMEOUT_FOR_WIDGET_READY:
                    for widget_id in specific_widgets:
                        # Check browser state before each widget
                        if not self._safe_browser_operation(f"waiting for widget {widget_id}"):
                            return False
                        try:
                            logging.info(f"⏳ Checking widget: {widget_id}...")
                            widget_wait = WebDriverWait(self.driver, timeout // 5)
                            widget_wait.until(WidgetReady(widget_id))
                            logging.info(f"✅ Widget ready: {widget_id}")
                        except TimeoutException:
                            if not self.is_browser_alive():
                                return False
                            logging.warning(f"⚠️ Widget not ready within timeout: {widget_id}")
                            continue
                else:
                    time.sleep(self.HARD_TIMEOUT_FOR_WIDGET_READY)
            
            # Step 5: If Kendo is enabled but no specific widgets, just do a brief wait
            elif check_kendo:
                logging.info("⏳ Kendo enabled but no specific widgets - brief wait...")
                time.sleep(1)
            
            logging.info("✅ Page fully ready with all widgets loaded")
            return True
            
        except TimeoutException as e:
            if not self.is_browser_alive():
                return False
            logging.error(f"⏰ Timeout waiting for page readiness: {str(e)}")
            return False
        except Exception as e:
            if not self.is_browser_alive():
                return False
            logging.error(f"❌ Error waiting for page readiness: {str(e)}")
            return False
