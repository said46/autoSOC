# soc_base_mixin.py
import re
import base64
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import (NoSuchElementException, NoSuchWindowException, 
                                      WebDriverException)

from soc_DB import SQLQueryDirect


class SOC_BaseMixin:
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
        # These should be set by the child class
        self.SOC_ID_PATTERN = r"^\d{7,8}$"  # Regex pattern for SOC ID validation
        self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False  # Enable DB lookup for short SOC IDs
        self.MAX_WAIT_USER_INPUT_DELAY_SECONDS = 300  # Max wait time for user input
        self.ERROR_MESSAGE_ENDING = ", the script cannot proceed, close this window."
        self.config_file = 'SOC.ini'  # Default configuration file
    
    # ===== CUSTOM WAIT CONDITION CLASS =====
    
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
    
    # ===== PASSWORD PROCESSING =====
    
    def process_password(self, password: str) -> str:
        """
        Decode base64 encoded password or return plain text as fallback.
        
        This provides a basic level of password obfuscation in configuration files.
        If base64 decoding fails, the method falls back to using the password as plain text.
        
        Args:
            password: The password string (either base64 encoded or plain text)
            
        Returns:
            Decoded password if base64 was valid, otherwise original password           
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
        
        💡 TIP: If password contains line breaks, it will show an error and exit
        """
        try:
            # Enter username and password
            self.driver.find_element(By.ID, "UserName").send_keys(self.user_name)
            if self.password != "INCORRECT PASSWORD":
                self.driver.find_element(By.ID, "Password").send_keys(self.password)
            else:
                logging.error("❌ Password contains line break, cannot continue")
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
    
    def SOC_locked_check(self) -> None:
        """Check if SOC is locked and handle accordingly by showing error message."""
        try:
            li_locked = self.driver.find_element(By.XPATH, "//li[contains(text(), 'Locked')]")
            logging.error(f"❌ SOC is locked, the script will be terminated: {li_locked.text}")
            self.inject_error_message(f"❌ SOC is locked: {li_locked.text},.")
        except NoSuchElementException:
            logging.info("✅ Success: SOC is not locked")
    
    def access_denied_check(self) -> None:
        """Check for Access Denied error and handle accordingly."""
        try:
            access_denied = self.driver.find_element(By.XPATH, "//h1[contains(text(), 'Access Denied')]")
            logging.error(f"❌ {access_denied.text} - Access denied, probably SOC {self.SOC_id} is archived or in improper state")
            self.inject_error_message(f"❌ Access denied, probably SOC {self.SOC_id} is archived or in improper state.")
        except NoSuchElementException:
            logging.info("✅ Success: no access denied issue")

    def login_failed_check(self) -> None:
        """Check for login failure and handle accordingly."""
        try:
            # Check if li tag with parent div[contains(@class, 'text-danger')] contains any text
            self.driver.find_element(By.XPATH, "//div[contains(@class, 'text-danger')]//li[text()]")
            logging.error("❌ Login issue, check the password in ini-file.")
            self.inject_error_message(f"❌ Login issue, check the password in ini-file.")
        except NoSuchElementException:
            logging.info("✅ Success: no login issue")

    def error_404_not_present_check(self) -> None:
        """Check if no 404 error is present on the page."""
        try:
            self.driver.find_element(By.XPATH, "//h1[contains(@class, 'text-danger') and contains(text(), '404')]")
            logging.error(f"❌ Error 404, probably SOC {self.SOC_id} does not exist")
            self.inject_error_message(f"❌ Error 404, probably SOC {self.SOC_id} does not exist.")
        except NoSuchElementException:
            logging.info("✅ Success: no error 404")

    def url_contains_SOC_Details_check(self):
        """Verify that the current URL contains the SOC Details path."""
        current_url = self.driver.current_url
        if "/Soc/Details/" not in current_url:
            logging.error(f"❌ Wrong page loaded: {current_url}. Expected SOC Details page.")
            self.inject_error_message(f"❌ Wrong page loaded, navigation failed.")
    
    # ===== SOC INPUT FIELD MANAGEMENT =====
    
    def inject_SOC_id_input(self) -> None:
        """
        Inject SOC ID input field into the login form.
        
        This method:
        - Creates a custom input field for SOC ID entry
        - Hides the original submit button to prevent premature form submission
        - Prevents form submission on Enter key in other fields
        - Sets up input monitoring and validation
        
        The injected field becomes the primary input mechanism for SOC ID entry.
        """
        try:
            js_code = """
                var container = document.createElement('div');
                container.style.cssText = 'margin-top: 10px;';
                
                var input = document.createElement('input');
                input.type = 'text';
                input.id = 'InjectedInput';
                input.className = "form-control control-lg";
                input.style.marginBottom = "5px";
                input.style.width = "100%";
                
                // Hide the original submit button AND prevent form submission
                var submitButton = document.querySelector('button[type="submit"]');
                if (submitButton) submitButton.style.display = 'none';
                
                // Prevent form submission on Enter in any field
                var form = document.querySelector('form');
                if (form) {
                    form.addEventListener('keypress', function(e) {
                        if (e.key === 'Enter') {
                            e.preventDefault();
                            e.stopPropagation();
                        }
                    });
                }
                
                container.appendChild(input);
                const referenceElement = document.getElementById('Password');
                referenceElement.insertAdjacentElement('afterend', container);
                input.focus();
            """
            self.driver.execute_script(js_code)
            
            # Now use Python to add the guide text and set up monitoring
            self._setup_input_monitoring()
            
        except NoSuchWindowException:
            logging.warning(f"🏁  Browser windows was closed, end of script")
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
    
    def wait_for_soc_input_and_submit(self):
        """
        Wait for SOC ID input and submit the form.
        
        This is the main method that coordinates the SOC input process:
        1. Waits for valid SOC ID input with Enter key press
        2. Processes the SOC ID (stripping leading zeros if needed)
        3. Optionally queries database for full SOC ID if partial provided
        4. Submits the form with the processed SOC ID
        """
        try:
            # Wait for valid SOC ID input with timeout
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(
                self.WaitForSOCInput((By.ID, "InjectedInput"), self)  # Pass self as mixin instance
            )
            
            # If browser closed, exit
            if self._is_browser_closed():
                logging.info("🏁 Browser closed by user during input")
                self.safe_exit()
            
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

            logging.info(f"✅ Processed SOC id is {self.SOC_id}, continue submitting the form")
            self.submit_form_with_soc_id(self.SOC_id)            
            
        except NoSuchWindowException:
            logging.warning(f"🏁  Browser windows was closed, end of script")
            self.safe_exit()
            return ""
        except Exception as e:
            logging.error(f"❌ Failed to wait for SOC_id to be entered: {str(e)}")
            self.inject_error_message(f"❌ Failed to wait for SOC_id to be entered.")
            return ""

    def submit_form_with_soc_id(self) -> None:
        """
        Submit the form with the self.SOC_id.
        """
        try:           
            # Submit the form directly via JavaScript
            # "form?.submit();" is same as "if (form) form.submit();"
            self.driver.execute_script("""
                var form = document.querySelector('form');
                form?.submit()
            """)
            logging.info(f"✅ Form submitted successfully with {self.SOC_id}")
        except Exception as e:
            logging.error(f"❌ Failed to submit the form: {str(e)}")
            self.inject_error_message(f"❌ Failed to submit the form.")
    
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
                SOC_id = str(results[0]['Id'])  # Access via dict key
            else:
                raise ValueError(f"Expected 1 row, got {len(results)}")
        
        if not isinstance(SOC_id, str) or len(SOC_id) < 7:
            raise ValueError(f"{SOC_id} has to be string with len 7 or 8")
        
        return SOC_id