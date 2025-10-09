# soc_input_mixin.py
import re
import base64
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import (NoSuchElementException, NoSuchWindowException, 
                                      WebDriverException)

class SOCInputMixin:
    """Mixin class that provides SOC ID input functionality, password processing, and login logic"""
    
    def __init__(self):
        # These should be set by the child class
        self.SOC_ID_PATTERN = r"^\d{7,8}$"
        self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
        self.MAX_WAIT_USER_INPUT_DELAY_SECONDS = 300
        self.ERROR_MESSAGE_ENDING = ", the script cannot proceed, close this window."
    
    def process_password(self, password: str) -> str:
        """
        Decode base64 encoded password or return plain text as fallback
        
        Args:
            password: The password string (either base64 encoded or plain text)
            
        Returns:
            Decoded password if base64 was valid, otherwise original password
            
        💡 TIP: Use base64 encoding for passwords in config files to avoid plain text storage
        💡 TIP: If decoding fails, the method falls back to using the password as plain text
        """
        encoded_password = password
        try:
            decoded_password = base64.b64decode(password.encode()).decode()
            logging.info(f"🔐 Password decoded successfully")
            return decoded_password
        except Exception as e:
            logging.error(f"🔐 Failed to decode password: {str(e)}, using plain text password")
            return encoded_password  # Fallback to plain text
    
    def perform_login(self) -> None:
        """
        Perform login with username and password, then inject SOC ID input field
        
        💡 TIP: This method handles the entire login process including error checking
        💡 TIP: If password contains line breaks, it will show an error and exit
        """
        # login
        try:
            self.driver.find_element(By.ID, "UserName").send_keys(self.user_name)
            if self.password != "INCORRECT PASSWORD":
                self.driver.find_element(By.ID, "Password").send_keys(self.password)
            else:
                logging.error("❌ Password contains line break, cannot continue")
                self.inject_error_message(f"❌ Password contains line break{self.ERROR_MESSAGE_ENDING}.")
        except NoSuchElementException as e:
            logging.error(f"❌ Failed to find 'Username' or 'Password' input fields: {str(e)}")
            self.inject_error_message(f"❌ Failed to find 'Username' or 'Password' input fields {self.ERROR_MESSAGE_ENDING}.")
        
        # Show warning message if any (from configuration issues)
        if hasattr(self, 'warning_message') and self.warning_message:
            self.inject_info_message(self.warning_message, style_addons={'color': 'darkorange'})

        # Use mixin method to inject SOC ID input field
        self.inject_SOC_id_input()
    
    def wait_for_soc_input_and_process(self) -> str:
        """
        Wait for SOC ID input, process it, and return the validated SOC ID
        
        Returns:
            Validated SOC ID string
            
        💡 TIP: This method combines waiting for input with SOCBot-specific database logic
        💡 TIP: Child classes can override this to add their own processing logic
        """
        # Use mixin method to get SOC ID
        soc_id = self.wait_for_soc_input_and_submit()
        
        # SOCBot-specific database logic for partial SOC IDs
        if hasattr(self, 'CONNECT_TO_DB_FOR_PARTIAL_SOC_ID') and self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
            if len(soc_id) < 7:
                try:
                    full_SOC_id = self.request_DB_for_SOC_id(soc_id)
                    soc_id = full_SOC_id
                    if soc_id is None:
                        raise ValueError("SOC_id cannot be None")
                except Exception as e:
                    logging.error(f"❌ Failed to request DB: {str(e)}")
                    self.inject_error_message(f"❌ Failed to request DB ({str(e)}){self.ERROR_MESSAGE_ENDING}.")                

        return soc_id

    def SOC_locked_check(self) -> None:
        """Check if SOC is locked and handle accordingly"""
        try:
            li_locked = self.driver.find_element(By.XPATH, "//li[contains(text(), 'Locked')]")
            logging.error(f"❌ SOC is locked, the script will be terminated: {li_locked.text}")
            self.inject_error_message(f"❌ SOC is locked, the script cannot proceed, close this window: {li_locked.text}")
        except NoSuchElementException:
            logging.info("✅ Success: SOC is not locked")
    
    def access_denied_check(self) -> None:
        """Check for Access Denied error and handle accordingly"""
        # check for Access Denied
        try:
            access_denied = self.driver.find_element(By.XPATH, "//h1[contains(text(), 'Access Denied')]")
            logging.error(f"❌ {access_denied.text} - Access denied, probably SOC {self.SOC_id} is archived or in improper state")
            self.inject_error_message(f"❌ Access denied, probably SOC {self.SOC_id} is archived or in improper state{self.ERROR_MESSAGE_ENDING}.")
        except NoSuchElementException:
            logging.info("✅ Success: no access denied issue")

    def login_failed_check(self) -> None:
        """Check for login failure and handle accordingly"""
        # check for login issue
        try:
            # check if li tag with parent div[contains(@class, 'text-danger')] contains any text
            self.driver.find_element(By.XPATH, "//div[contains(@class, 'text-danger')]//li[text()]")
            logging.error("❌ Login issue, check the password in ini-file.")
            self.inject_error_message("❌ Login issue, check the password in ini-file, the script cannot proceed, close this window")
        except NoSuchElementException:
            logging.info("✅ Success: no login issue")
    
    # callable class
    class WaitForSOCInput:
        """SOCInputMixin-specific wait condition for SOC input"""
        def __init__(self, locator, soc_mixin):
            self.locator = locator
            self.soc_mixin = soc_mixin
            self.last_value = ""

        def __call__(self, driver):
            try:
                # Browser closure check
                if self.soc_mixin._is_browser_closed():
                    return True  # Return True to stop waiting and continue
                    
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
                # Browser closed - return True to break the wait
                return True

    def inject_SOC_id_input(self) -> None:
        """Inject SOC ID input field into the login form"""
        try:
            # JavaScript to create the SOC id input field
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
            self.inject_error_message(f"❌ Failed to inject SOC_id input field")

    def _update_input_ui(self, is_valid: bool, message: str) -> None:
        """Update the input field UI based on validation result"""
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

    def _setup_input_monitoring(self) -> None:
        """Set up Python-based input monitoring and validation"""
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

    def _validate_soc_input(self, value: str) -> tuple[bool, str]:
        """Validate SOC input and return (is_valid, message)"""
        value = value.strip()
        
        if not value:
            return False, "⚠️ Empty value is not allowed"
                            
        # Check against the full pattern
        pattern = re.compile(self.SOC_ID_PATTERN)
        min_digits = 4 if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID else 7
        if not pattern.match(value):
            return False, f"⚠️ SOC id must to be at least {min_digits} digits"
        
        return True, "✅ Valid - Press Enter to continue"
          
    def wait_for_soc_input_and_submit(self) -> str:
        """Wait for SOC ID input and return the validated SOC ID"""
        try:
            # the script will wait for MAX_WAIT_USER_INPUT_DELAY_SECONDS until valid input is provided
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(
                self.WaitForSOCInput((By.ID, "InjectedInput"), self)  # Pass self as mixin instance
            )
            
            # If browser closed, exit
            if self._is_browser_closed():
                logging.info("🏁 Browser closed by user during input")
                self.safe_exit()
            
            # get the SOC_id from the injected input field
            raw_soc_id = self.driver.find_element(By.ID, "InjectedInput").get_attribute("value")
            
            # Strip leading zero if SOC ID is 8 digits and starts with 0
            if len(raw_soc_id) == 8 and raw_soc_id.startswith('0'):
                soc_id = raw_soc_id[1:]  # Remove the first character
                logging.info(f"🔧 Stripped leading zero: '{raw_soc_id}' -> '{soc_id}'")
            else:
                soc_id = raw_soc_id

            logging.info(f"✅ Valid SOC id {soc_id} entered - returning for further processing")
            
            # ✅ CRITICAL FIX: Submit the form with the SOC ID
            self.submit_form_with_soc_id(soc_id)            
            return soc_id
            
        except NoSuchWindowException:
            logging.warning(f"🏁  Browser windows was closed, end of script")
            self.safe_exit()
            return ""
        except Exception as e:
            logging.error(f"❌ Failed to wait for SOC_id to be entered: {str(e)}")
            self.inject_error_message(f"❌ Failed to wait for SOC_id to be entered{self.ERROR_MESSAGE_ENDING}.")
            return ""

    def submit_form_with_soc_id(self, soc_id: str) -> None:
        """Submit the form with the provided SOC ID"""
        try:
            # Store the SOC ID in the instance if needed by child class
            if hasattr(self, 'SOC_id'):
                self.SOC_id = soc_id
            
            # press the login button - submit the form directly via JavaScript
            # "form?.submit();"" is same as "if (form) form.submit();""
            self.driver.execute_script("""
                var form = document.querySelector('form');
                form?.submit()
            """)
            logging.info("✅ Form submitted successfully with SOC ID")
        except Exception as e:
            logging.error(f"❌ Failed to submit the form: {str(e)}")
            self.inject_error_message(f"❌ Failed to submit the form{self.ERROR_MESSAGE_ENDING}.")