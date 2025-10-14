# soc_launcher.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import (NoSuchElementException, NoSuchWindowException)
import logging
import base64
import os

from base_web_bot import BaseWebBot
from soc_base_mixin import SOC_BaseMixin
from error_types import ErrorLevel, OperationResult

from soc_controller import SOC_Controller
from soc_exporter import SOC_Exporter
from soc_importer import SOC_Importer


class SOC_Launcher(BaseWebBot, SOC_BaseMixin):
    """
    Launcher for SOC bots with common login/SOC input functionality
    and radio button selection between control, export, and import.
    """

    def __init__(self):
        BaseWebBot.__init__(self)
        SOC_BaseMixin.__init__(self)
        self._initialized = False
        self.selected_bot = "control"  # Default selection
        
        # Load and convert image to base64
        self.base64_logo = self.image_to_base64("LOGO.png")
        
        # Load configuration with proper error handling
        success, error_msg, severity = self.load_configuration()
        if not self._handle_result(success, error_msg, severity):
            return
            
        self._initialized = True

    def image_to_base64(self, image_path: str) -> str:
        """
        Convert image file to base64 string.
        Returns base64 string or empty string if file not found.
        """
        try:
            if not os.path.exists(image_path):
                logging.warning(f"⚠️ Image file {image_path} not found, using placeholder")
                return ""
                
            with open(image_path, "rb") as image_file:
                base64_data = base64.b64encode(image_file.read()).decode('utf-8')
                logging.info(f"✅ Image {image_path} converted to base64 ({len(base64_data)} chars)")
                return base64_data
                
        except Exception as e:
            logging.error(f"❌ Failed to convert image to base64: {str(e)}")
            return ""

    def load_configuration(self) -> OperationResult:
        """Returns (success, error_message, severity)"""
        try:
            import configparser
            config = configparser.ConfigParser(interpolation=None)
            config.read(self.config_file, encoding="utf8")

            success, error_msg, severity = self.load_common_configuration(config)
            if not success:
                return False, error_msg, severity            

            logging.info(f"✅ Launcher configuration loaded from {self.config_file}")
            return True, None, None

        except Exception as e:
            return False, f"Configuration failed: {str(e)}", ErrorLevel.FATAL

    @property
    def base_link(self) -> str:
        return self._base_link

    def _handle_result(self, success: bool, error_msg: str | None, severity: ErrorLevel) -> bool:
        """Handle result and return whether to continue execution"""
        if not success:
            if severity == ErrorLevel.TERMINAL:
                logging.info(f"🏁 Terminal: {error_msg}")
                self.safe_exit()
                return False
            elif severity == ErrorLevel.FATAL:
                logging.error(f"💥 Fatal: {error_msg}")
                # Can't use inject_error_message here - browser not ready yet
                print(f"❌ FATAL: {error_msg}")
                return False
            else:  # RECOVERABLE
                logging.warning(f"⚠️ Recoverable: {error_msg}")
                # Continue execution for recoverable errors
                return True
        return True

    def inject_bot_selection(self) -> None:
        """
        Inject radio buttons for bot selection into the login form.
        """
        try:
            js_code = """
                // Create container for radio buttons
                var radioContainer = document.createElement('div');
                radioContainer.id = 'BotSelectionContainer';
                radioContainer.style.cssText = 'margin: 15px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px; background: #f9f9f9;';
                
                // Add title
                var title = document.createElement('div');
                title.textContent = 'Select SOC Operation:';
                title.style.cssText = 'font-weight: bold; margin-bottom: 10px; color: #333;';
                radioContainer.appendChild(title);
                
                // Create radio buttons
                var options = [
                    {id: 'control', label: '🚀 Control - Apply/remove overrides'},
                    {id: 'export', label: '⏩ Export - Export overrides to Excel'},
                    {id: 'import', label: '⏪ Import - Import overrides from Excel'}
                ];
                
                options.forEach(function(option) {
                    var radioDiv = document.createElement('div');
                    radioDiv.style.cssText = 'margin: 5px 0;';
                    
                    var radio = document.createElement('input');
                    radio.type = 'radio';
                    radio.id = 'bot_' + option.id;
                    radio.name = 'bot_selection';
                    radio.value = option.id;
                    radio.style.marginRight = '8px';
                    
                    // Set control as default
                    if (option.id === 'control') {
                        radio.checked = true;
                    }
                    
                    var label = document.createElement('label');
                    label.htmlFor = 'bot_' + option.id;
                    label.textContent = option.label;
                    label.style.cursor = 'pointer';
                    
                    radioDiv.appendChild(radio);
                    radioDiv.appendChild(label);
                    radioContainer.appendChild(radioDiv);
                });
                
                // Add event listener to store selection
                radioContainer.addEventListener('change', function(e) {
                    if (e.target.name === 'bot_selection') {
                        window.selectedBot = e.target.value;
                    }
                });
                
                // Initialize selection
                window.selectedBot = 'control';
                
                // Insert after password field
                var passwordField = document.getElementById('Password');
                if (passwordField) {
                    passwordField.parentNode.insertBefore(radioContainer, passwordField.nextSibling);
                }
            """
            self.driver.execute_script(js_code)
            logging.info("✅ Bot selection radio buttons injected")

        except Exception as e:
            logging.error(f"❌ Failed to inject bot selection: {str(e)}")

    def get_selected_bot(self) -> str:
        """
        Get the currently selected bot from radio buttons.
        Returns: 'control', 'export', or 'import'
        """
        try:
            selected_bot = self.driver.execute_script("return window.selectedBot || 'control';")
            logging.info(f"✅ Selected bot: {selected_bot}")
            return selected_bot
        except Exception as e:
            logging.warning(f"⚠️ Could not get selected bot, using default: {str(e)}")
            return "control"

    def enter_credentials_and_prepare_launcher(self) -> None:
        """
        Enhanced version that includes scarlet text, larger image, and bot selection radio buttons.
        """
        try:
            # Inject scarlet text and larger image
            header_js = """
                // Create main container
                var mainContainer = document.createElement('div');
                mainContainer.id = 'InjectedMainContainer';
                mainContainer.style.cssText = 'text-align: center; margin: 20px 0;';
                
                // Create image container with larger size
                var imgContainer = document.createElement('div');
                imgContainer.id = 'InjectedImageContainer';
                imgContainer.style.cssText = 'margin: 15px 0;';
                
                var img = document.createElement('img');
                img.id = 'InjectedLogo';
                img.alt = 'SOC Logo';
                img.style.cssText = 'max-width: 300px; max-height: 150px; border-radius: 5px;';
                
                imgContainer.appendChild(img);
                
                // Create scarlet text (no background, just scarlet colored text)
                var textElement = document.createElement('div');
                textElement.id = 'InjectedScarletText';
                textElement.textContent = 'АСУ СБЗ "SOCовыжималка"';
                textElement.style.cssText = 'color: #FF2400; font-size: 32px; font-weight: bold; font-family: Calibri, sans-serif; margin: 10px 0;';
                
                mainContainer.appendChild(imgContainer);
                mainContainer.appendChild(textElement);
                
                // Insert at the top of the form
                var loginForm = document.querySelector('form');
                if (loginForm) {
                    loginForm.insertBefore(mainContainer, loginForm.firstChild);
                } else {
                    // Fallback: insert at top of body
                    document.body.insertBefore(mainContainer, document.body.firstChild);
                }
            """
            self.driver.execute_script(header_js)
            
            # Set the image source with base64 data
            if self.base64_logo:
                set_image_js = f"document.getElementById('InjectedLogo').src = 'data:image/png;base64,{self.base64_logo}';"
                self.driver.execute_script(set_image_js)
                logging.info("✅ Logo image injected successfully")
            else:
                # Fallback to larger text placeholder if image not available
                fallback_js = """
                    var imgContainer = document.getElementById('InjectedImageContainer');
                    if (imgContainer) {
                        var placeholder = document.createElement('div');
                        placeholder.textContent = '🚀 SOCовыжималка';
                        placeholder.style.cssText = 'color: #FF2400; font-size: 24px; font-weight: bold; padding: 20px; border: 2px dashed #FF2400; display: inline-block; background: #FFF0F0; border-radius: 5px;';
                        imgContainer.innerHTML = '';
                        imgContainer.appendChild(placeholder);
                    }
                """
                self.driver.execute_script(fallback_js)
                logging.info("✅ Text placeholder injected (image not available)")
            
            logging.info("✅ Scarlet text and larger logo container injected")

            # Enter username and password
            self.driver.find_element(By.ID, "UserName").send_keys(self.user_name)
            if self.password != "INCORRECT PASSWORD":
                self.driver.find_element(By.ID, "Password").send_keys(self.password)
            else:
                logging.error("❌ Password contains line break")
                self.inject_error_message(f"❌ Password contains line break.")

            # Show warning message if any
            if hasattr(self, 'warning_message') and self.warning_message:
                self.inject_info_message(self.warning_message, style_addons={'color': 'darkorange'})

            # Inject bot selection radio buttons
            self.inject_bot_selection()

            # Use mixin method to inject SOC ID input field
            self.inject_SOC_id_input()

        except NoSuchElementException as e:
            logging.error(f"❌ Failed to find login fields: {str(e)}")
            self.inject_error_message(f"❌ Failed to find login fields.")

    def wait_for_launcher_input_and_submit(self) -> OperationResult:
        """
        Wait for both SOC ID input and form submission, then return selected bot.
        Returns (success, error_message, severity)
        """
        try:
            # Wait for valid SOC ID input with timeout
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(
                self.WaitForSOCInput((By.ID, "InjectedInput"), self)
            )

            # If browser closed, exit
            if self._is_browser_closed():
                error_msg = "🏁 Browser closed by user during input"
                logging.info(error_msg)
                return False, error_msg, ErrorLevel.TERMINAL

            # Get the selected bot type
            self.selected_bot = self.get_selected_bot()

            # Get the SOC_id from the injected input field
            raw_soc_id = self.driver.find_element(By.ID, "InjectedInput").get_attribute("value")
            logging.info(f"🔧 Raw SOC id is {raw_soc_id}, selected bot: {self.selected_bot}")

            # Strip leading zero if SOC ID is 8 digits and starts with 0
            if len(raw_soc_id) == 8 and raw_soc_id.startswith('0'):
                self.SOC_id = raw_soc_id[1:]
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
                        return False, f"Database error: {str(e)}", ErrorLevel.FATAL

            logging.info(f"✅ Processed SOC id is {self.SOC_id}, bot: {self.selected_bot}")

            # Submit the form
            success = self.submit_form_with_soc_id()
            if not success:
                return False, "Form submission failed", ErrorLevel.FATAL

            # Check for login failures
            success, error_msg = self.login_failed_check()
            if not success:
                return False, error_msg, ErrorLevel.FATAL

            return True, None, None

        except (NoSuchWindowException, NoSuchWindowException):
            error_msg = "Browser window was closed during input"
            logging.warning(error_msg)
            return False, error_msg, ErrorLevel.TERMINAL
        except Exception as e:
            error_msg = f"Failed to wait for launcher input: {str(e)}"
            logging.error(error_msg)
            self.inject_error_message(f"❌ {error_msg}")
            return False, error_msg, ErrorLevel.FATAL

    def launch_selected_bot(self) -> OperationResult:
        """
        Launch the selected bot with the obtained SOC ID and existing browser session.
        Returns (success, error_message, severity)
        """
        try:
            logging.info(f"🚀 Launching {self.selected_bot} bot for SOC {self.SOC_id}")

            # a small pause to let driver stabilize
            import time
            time.sleep(0.3)

            if self.selected_bot == "control":
                bot = SOC_Controller(soc_id=self.SOC_id)
            elif self.selected_bot == "export":
                bot = SOC_Exporter(soc_id=self.SOC_id)
            elif self.selected_bot == "import":
                bot = SOC_Importer(soc_id=self.SOC_id)
            else:
                error_msg = f"Unknown bot type: {self.selected_bot}"
                logging.error(error_msg)
                return False, error_msg, ErrorLevel.FATAL

            # Run the bot without standalone mode (we already handled login)
            bot.run(standalone=False)
            
            return True, None, None

        except Exception as e:
            error_msg = f"Failed to launch {self.selected_bot} bot: {str(e)}"
            logging.error(error_msg)
            self.inject_error_message(f"❌ {error_msg}")
            return False, error_msg, ErrorLevel.FATAL

    def run(self):
        """
        Main launcher workflow.
        """
        if not self._initialized:
            logging.error("❌ Launcher not properly initialized")
            return

        try:
            # Navigate to base and handle login/SOC input
            self.navigate_to_base()
            self.enter_credentials_and_prepare_launcher()

            # Wait for user input and get selected bot
            success, error_msg, severity = self.wait_for_launcher_input_and_submit()
            if not self._handle_result(success, error_msg, severity):
                return

            # Launch the selected bot
            success, error_msg, severity = self.launch_selected_bot()
            if not self._handle_result(success, error_msg, severity):
                return

        except Exception as e:
            logging.error(f"❌ Launcher execution failed: {str(e)}")
            self.inject_error_message(f"❌ Launcher execution failed: {str(e)}")
            self.safe_exit()


if __name__ == "__main__":
    try:
        launcher = SOC_Launcher()
        launcher.run()
    except Exception as e:
        print(f"❌ Failed to start launcher: {str(e)}")
        logging.error(f"❌ Launcher startup failed: {str(e)}")