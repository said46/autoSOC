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
from base_web_bot import BaseWebBot # Import BaseWebBot to make the dependency clear

class WaitForSOCInput:
    """
    Custom wait condition for monitoring SOC ID input field.

    This class implements the __call__ method to be used with WebDriverWait.
    It monitors the input field for changes and Enter key presses, validating
    the input in real-time and updating the UI accordingly.
    """

    def __init__(self, locator, soc_mixin):
        """
        Initialize the wait condition.

        Args:
            locator: Tuple (By strategy, value) to locate the input field
            soc_mixin: Reference to the SOC_BaseMixin instance for validation
        """
        self.locator = locator
        self.soc_mixin = soc_mixin
        self.last_value = ""  # Track previous value to detect changes

    def __call__(self, driver):
        """
        Called repeatedly by WebDriverWait until condition is met or timeout.

        Returns:
            True if valid SOC ID entered and Enter pressed, False to continue waiting
        """
        try:
            # Browser closure check - stop waiting if browser closed
            if self.soc_mixin._is_browser_closed():
                return True

            injected_input = driver.find_element(*self.locator)
            current_value = injected_input.get_attribute("value")

            # Validate and update UI on value change
            if current_value != self.last_value:
                is_valid, message = self.soc_mixin._validate_soc_input(current_value)
                self.soc_mixin._update_input_ui(is_valid, message)
                self.last_value = current_value

            # Check if Enter key was pressed
            enter_pressed = injected_input.get_attribute('data-enter-pressed') == 'true'
            # Simplified condition: only check for Enter press and validity
            if enter_pressed:
                is_valid, message = self.soc_mixin._validate_soc_input(current_value)
                self.soc_mixin._update_input_ui(is_valid, message)

                if is_valid:
                    # Valid input - disable field and proceed
                    driver.execute_script("""
                        var input = document.getElementById('InjectedInput');
                        input.removeAttribute('data-enter-pressed');
                        input.disabled = true;
                    """)
                    return True
                else:
                    # Invalid input - show error and reset Enter flag
                    self.soc_mixin._update_input_ui(False, "❌ Invalid - " + message.split('⚠️ ')[-1])
                    driver.execute_script("""
                        var input = document.getElementById('InjectedInput');
                        input.removeAttribute('data-enter-pressed');
                    """)

            return False
        except (NoSuchWindowException, WebDriverException):
            # Browser closed - return True to break the wait
            return True

class WidgetReady:
    """
    Custom wait condition for checking Kendo widget readiness.
    """

    def __init__(self, widget_id):
        self.widget_id = widget_id

    def __call__(self, driver):
        """
        Check if widget is ready.
        """
        try:
            # Debug: Check what's actually on the page
            debug_info = driver.execute_script(f"""
                try {{
                    var element = document.getElementById('{self.widget_id}');
                    var exists = !!element;
                    var kendoWidget = exists ? $(element).data('kendoWidget') : null;
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

class SOC_BaseMixin(BaseWebBot): # Now inherits from BaseWebBot
    """
    Mixin class that provides SOC ID input functionality, password processing, and login logic.

    This mixin is designed to be combined with BaseWebBot to add SOC-specific functionality:
    - SOC ID input field injection and validation
    - Password decoding and credential entry
    - Login form submission with SOC ID
    - Database lookup for partial SOC IDs
    - Various security and access checks

    Expected to be used with web applications that require SOC number authentication.
    """

    EXPECTED_HOME_PAGE_TITLE = "СНД - Домашняя страница"

    def __init__(self):
        """
        Initialize SOC mixin with default configuration.

        Note: Child classes should override these attributes as needed.
        """
        # Ensure BaseWebBot's __init__ is called first to set up driver, etc.
        # This happens implicitly when SOC_BaseMixin is inherited by the final class
        # and that class calls super().__init__(), which eventually calls BaseWebBot.__init__().
        # If SOC_BaseMixin needs to directly call BaseWebBot's __init__ if it were standalone,
        # it would use: BaseWebBot.__init__(self)
        # But since it's a mixin, the inheriting class (e.g., SOC_Exporter) handles the chain.

        # These should be set by the child class
        self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
        self.SOC_ID_PATTERN = r"^\d{7,8}$"  # Regex pattern for SOC ID validation
        self.ERROR_MESSAGE_ENDING = ", the script cannot proceed, close this window."
        self.config_file = 'SOC.ini'  # Default configuration file
        self.SOC_id = ''  # Initialized for safety

    # ===== ERROR HANDLING =====
    
    def _handle_result(self, success: bool, error_msg: str | None, severity: ErrorLevel) -> bool:
        """Handle result and return whether to continue execution"""
        # Check browser state in error handling - exit immediately if already closed
        if not self.is_browser_alive():
            logging.info("🏁 Browser already closed - immediate exit")
            self.safe_exit()
            return False
            
        if not success:
            if severity == ErrorLevel.TERMINAL:
                logging.info(f"🏁 Terminal: {error_msg}")
                # For TERMINAL errors, exit immediately without message injection
                self.safe_exit()
                return False
            elif severity == ErrorLevel.FATAL:
                logging.error(f"💥 Fatal: {error_msg}")
                self.inject_error_message(error_msg)  # This will wait for user to close
                return False
            else:  # RECOVERABLE
                logging.warning(f"⚠️ Recoverable: {error_msg}")
                # Continue execution for recoverable errors
                return True
        return True

    # ===== CONFIGURATION METHODS =====
    
    def load_common_configuration(self, config: configparser.ConfigParser) -> OperationResult:
        """Load configuration common to all SOC bots"""
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
            
            # ✅ SOC_id assigned once
            self.SOC_id = config.get('Settings', 'SOC_id', fallback='')
            logging.info(f"🔧 Loaded SOC_id from config: '{self.SOC_id}'") 
            
            return True, None, None
        except Exception as e:
            return False, f"Loading common configuration failed: {e}", ErrorLevel.FATAL

    # ===== PASSWORD PROCESSING =====

    def process_password(self, password: str) -> str:
        """
        Decode base64 encoded password or return plain text as fallback.
        This provides a basic level of password obfuscation in configuration files.
        If base64 decoding fails, the method falls back to using the password as plain text.
        """
        encoded_password = password
        try:
            decoded_password = base64.b64decode(password.encode()).decode()
            logging.info(f"🔐 Password decoded successfully")
            return decoded_password
        except Exception as e:
            logging.error(f"🔐 Failed to decode password: {str(e)}, using plain text password")
            return encoded_password  # Fallback to plain text

    # ===== LOGIN AND CREDENTIAL MANAGEMENT =====

    def enter_credentials_and_prepare_soc_input(self) -> None:
        """
        This method handles the complete login preparation:
        1. Enters username and password into their respective fields
        2. Checks for password issues (like line breaks)
        3. Displays any warning messages from configuration
        4. Injects the SOC ID input field for user entry
        """
        try:
            # Browser check at start of operation
            self.check_browser_alive_or_exit("credential entry") # Corrected call, removed if not and return

            # Enter username and password
            self.driver.find_element(By.ID, "UserName").send_keys(self.user_name)
            if self.password != "INCORRECT PASSWORD":
                self.driver.find_element(By.ID, "Password").send_keys(self.password)
            else:
                logging.error("❌ Password contains line break")
                self.inject_error_message(f"❌ Password contains line break.")
        except NoSuchElementException as e:
            logging.error(f"❌ Failed to find 'Username' or 'Password' input fields: {str(e)}")
            self.inject_error_message(f"❌ Failed to find 'Username' or 'Password' input fields .")

        # Show warning message if any (from configuration issues)
        if hasattr(self, 'warning_message') and self.warning_message:
            self.inject_info_message(self.warning_message, style_addons={'color': 'darkorange'})

        # Use mixin method to inject SOC ID input field
        self.inject_SOC_id_input()

    # ===== SECURITY AND ACCESS CHECKS =====

    def SOC_locked_check(self) -> tuple[bool, str | None]:
        """Check if SOC is locked and handle accordingly by showing error message."""
        try:
            # Browser check before WebDriver operation
            self.check_browser_alive_or_exit("SOC locked check") # Corrected call

            locked_xpath = "//div[@class='text-danger validation-summary-valid']//li[contains(., 'заблокирован')]"
            li_locked = self.driver.find_element(By.XPATH, locked_xpath)
            error_msg = f"❌ SOC is locked: {li_locked.text}"
            return False, error_msg
        except NoSuchElementException:
            logging.info("✅ Success: SOC is not locked")
            return True, None

    def access_denied_check(self) -> tuple[bool, str | None]:
        """Check for Access Denied error and handle accordingly."""
        """REWORK WHEN HAPPENS!!!! see in correct XPATH below"""
        try:
            # Browser check before WebDriver operation
            self.check_browser_alive_or_exit("access denied check") # Corrected call

            access_denied_xpath = "//div[contains(@class, 'panel-line-danger')//li[contains(text(), 'I DON'T KNOW WHAT TO FIND YET')]"
            self.driver.find_element(By.XPATH, access_denied_xpath)
            error_msg = f"❌ Access denied, SOC {self.SOC_id} may be archived or in improper state"
            logging.error(error_msg)
            return False, error_msg
        except NoSuchElementException:
            logging.info("✅ Success: no access denied issue")
            return True, None
        except InvalidSelectorException:
            logging.warning(f"InvalidSelectorException is TEMPORARY DISABLED IN access_denied_check()")
            return True, None

    def login_failed_check(self) -> tuple[bool, str | None]:
        """Check for login failure and handle accordingly."""
        try:
            # Browser check before WebDriver operation
            self.check_browser_alive_or_exit("login failed check") # Corrected call

            login_failed_xpath = "//div[contains(@class, 'validation-summary-errors')]"
            self.driver.find_element(By.XPATH, login_failed_xpath)
            error_msg = "❌ Login issue, check the password in ini-file."
            return False, error_msg
        except NoSuchElementException:
            logging.info("✅ Success: no login issue")
            return True, None

    def error_404_not_present_check(self) -> tuple[bool, str | None]:
        """Check if no 404 error is present on the page."""
        try:
            # Browser check before WebDriver operation
            self.check_browser_alive_or_exit("404 check") # Corrected call

            self.driver.find_element(By.XPATH, "//h1[contains(@class, 'text-danger') and contains(text(), '404')]")
            error_msg = f"❌ Error 404, probably SOC {self.SOC_id} does not exist"
            logging.error(error_msg)
            return False, error_msg
        except NoSuchElementException:
            logging.info("✅ Success: no error 404")
            return True, None

    def url_contains_SOC_Details_check(self) -> tuple[bool, str | None]:
        """Verify that the current URL contains the SOC Details path."""
        # Browser check before WebDriver operation
        self.check_browser_alive_or_exit("URL check") # Corrected call

        current_url = self.driver.current_url
        if "/Soc/Details/" not in current_url:
            error_message = f"❌ Wrong page loaded: {current_url}. Expected SOC Details page."
            logging.error(error_message)
            return False, error_message
        return True, None

    # ===== SOC INPUT FIELD MANAGEMENT =====

    def inject_SOC_id_input(self) -> None:
        """
        Inject SOC ID input field into the login form with default value.
        """
        try:
            # Browser check before WebDriver operation
            self.check_browser_alive_or_exit("SOC input injection") # Corrected call

            # Get the default SOC_id (might be empty string)
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
                // ✅ PRE-POPULATE with default SOC ID
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

            # Now use Python to add the guide text and set up monitoring
            self._setup_input_monitoring()

            if default_soc_id:
                logging.info(f"✅ Injected SOC input field with default: {default_soc_id}")
            else:
                logging.info("✅ Injected SOC input field (no default)")

        except NoSuchWindowException:
            logging.warning(f"🏁 Browser windows was closed, end of script")
            self.safe_exit()
        except Exception as e:
            logging.error(f"❌ Failed to inject SOC_id input field: {str(e)}")
            self.inject_error_message(f"❌ Failed to inject SOC_id input field.")

    def _setup_input_monitoring(self) -> None:
        """
        Set up Python-based input monitoring and validation.

        Adds guide text and Enter key listener to the injected input field.
        The Enter key listener prevents default form submission behavior.
        """
        try:
            # Browser check before WebDriver operation
            self.check_browser_alive_or_exit("input monitoring setup") # Corrected call

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

        except Exception as e:
            logging.error(f"❌ Failed to set up input monitoring: {str(e)}")

    def _update_input_ui(self, is_valid: bool, message: str) -> None:
        """
        Update the input field UI based on validation result.

        Args:
            is_valid: Boolean indicating if the current input is valid
            message: Validation message to display to the user
        """
        try:
            # Browser check before WebDriver operation
            self.check_browser_alive_or_exit("UI update") # Corrected call

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

        except Exception as e:
            logging.error(f"❌ Failed to update input UI: {str(e)}")

    # ===== SOC INPUT VALIDATION =====

    def _validate_soc_input(self, value: str) -> tuple[bool, str]:
        """
        Validate SOC input and return validation result and message.

        Args:
            value: The SOC ID value to validate

        Returns:
            Tuple of (is_valid, message) where:
            - is_valid: Boolean indicating if input is valid
            - message: Descriptive message for the user
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
        """
        try:
            # Browser check before starting wait
            self.check_browser_alive_or_exit("SOC input wait") # Corrected call

            # Wait for valid SOC ID input with timeout
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(
                WaitForSOCInput((By.ID, "InjectedInput"), self)  # Pass self as mixin instance
            )

            # If browser closed, exit
            self.check_browser_alive_or_exit("SOC input processing") # Corrected call

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

        except (NoSuchWindowException, WebDriverException):
            logging.warning(f"🏁 Browser window was closed, end of script")
            self.safe_exit()
        except TimeoutException: # Added specific handling for TimeoutException
            error_msg = f"⏰ Timeout waiting for SOC ID input after {self.MAX_WAIT_USER_INPUT_DELAY_SECONDS} seconds."
            logging.error(error_msg)
            self.inject_error_message(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = "❌ Failed to wait for SOC_id to be entered"
            logging.error(f"{error_msg}: {str(e)}")
            self.inject_error_message(error_msg)
            return False, error_msg

    def submit_form_with_soc_id(self) -> bool:
        """
        Submit the form with the self.SOC_id.
        
        Returns:
            bool: True if successful, False if failed
        """
        try:
            # Browser check before WebDriver operation
            self.check_browser_alive_or_exit("form submission") # Corrected call

            # Submit the form directly via JavaScript
            # "form?.submit();" is same as "if (form) form.submit();"
            self.driver.execute_script("""
                var form = document.querySelector('form');
                form?.submit()
            """)
            logging.info(f"✅ Form submitted successfully with {self.SOC_id}")
            return True
        except Exception as e:
            logging.error(f"❌ Failed to submit the form: {str(e)}")
            self.inject_error_message(f"❌ Failed to submit the form.")
            return False

    # ===== DATABASE OPERATIONS =====

    def request_DB_for_SOC_id(self, SOC_id: str) -> str:
        """
        Query database for full SOC ID when partial ID is provided.

        Args:
            SOC_id: Partial SOC ID to look up in database

        Returns:
            Full SOC ID from database

        Raises:
            ValueError: If no results or multiple results found, or if result is invalid
        """
        SQL = self.SQL_template.format(soc_id=SOC_id)

        with SQLQueryDirect(
            server=self.db_server,
            database=self.db_database,
            username=self.db_username,
            password=self.db_password
        ) as sql:
            results = sql.execute(SQL)  # Now returns list of dicts, not DataFrame
            if len(results) == 1:
                row = results[0]
                if 'Id' not in row:
                     raise ValueError("Database query result missing 'Id' key.")
                SOC_id_from_db = row['Id']
                # Robust conversion to string with error handling
                try:
                    SOC_id_converted = str(SOC_id_from_db)
                except (TypeError, ValueError) as conv_error:
                    logging.error(f"❌ Failed to convert DB result '{SOC_id_from_db}' (type {type(SOC_id_from_db).__name__}) to string: {conv_error}")
                    raise ValueError(f"Database result '{SOC_id_from_db}' could not be converted to a valid string SOC ID: {conv_error}")
                
                SOC_id = SOC_id_converted
            else:
                raise ValueError(f"Expected 1 row, got {len(results)}")

        if not isinstance(SOC_id, str) or len(SOC_id) < 7:
            raise ValueError(f"{SOC_id} has to be string with len 7 or 8")

        return SOC_id

    # ===== DOM/jQuery/Kendo elements readiness =====
    
    def wait_for_page_fully_ready(self, 
                                check_dom: bool = True,
                                check_jquery: bool = True, 
                                check_kendo: bool = True,
                                specific_widgets: list = None,
                                timeout: int = None) -> bool:
        """
        Unified method to wait for page complete readiness including Kendo widgets.
        
        Args:
            check_dom: Wait for DOM ready state
            check_jquery: Wait for jQuery
            check_kendo: Wait for Kendo framework
            specific_widgets: List of specific widget IDs to wait for
            timeout: Override default timeout
        
        Returns:
            bool: True if all checks pass
        """

        # logging.info(f"⚡ wait_for_page_fully_ready() called - DOM: {check_dom}, jQuery: {check_jquery}, Kendo: {check_kendo}, Widgets: {specific_widgets}, Timeout: {timeout}")
        
        if timeout is None:
            timeout = self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS
          
        try:
            # Initial browser check
            self.check_browser_alive_or_exit("page readiness check") # Corrected call
                
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
                    # Wait for each widget individually with shorter timeout
                    for widget_id in specific_widgets:
                        # Browser check before each widget
                        self.check_browser_alive_or_exit(f"waiting for widget {widget_id}") # Corrected call
                        try:
                            logging.info(f"⏳ Checking widget: {widget_id}...")
                            # Use shorter timeout per widget
                            widget_wait = WebDriverWait(self.driver, timeout // 5)
                            widget_wait.until(WidgetReady(widget_id))
                            logging.info(f"✅ Widget ready: {widget_id}")
                        except TimeoutException:
                            logging.warning(f"⚠️ Widget not ready within timeout: {widget_id}")
                            # Continue with other widgets instead of failing completely
                            continue
                else:
                    time.sleep(self.HARD_TIMEOUT_FOR_WIDGET_READY)
            
            # Step 5: If Kendo is enabled but no specific widgets, just do a brief wait
            elif check_kendo:
                logging.info("⏳ Kendo enabled but no specific widgets - brief wait...")
                time.sleep(1)  # Short wait for any Kendo initialization
            
            logging.info("✅ Page fully ready with all widgets loaded")
            return True
            
        except TimeoutException as e:
            logging.error(f"⏰ Timeout waiting for page readiness: {str(e)}")
            return False
        except Exception as e:
            logging.error(f"❌ Error waiting for page readiness: {str(e)}")
            return False