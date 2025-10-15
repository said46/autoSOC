# soc_launcher.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import (NoSuchElementException, NoSuchWindowException)
import logging
import base64
import os

from base_web_bot import BaseWebBot
from soc_base_mixin import SOC_BaseMixin, WaitForSOCInput
from error_types import ErrorLevel, OperationResult

from soc_controller import SOC_Controller
from soc_exporter import SOC_Exporter
from soc_importer import SOC_Importer

class SOC_Launcher(SOC_BaseMixin):
    """
    Enhanced launcher for SOC bots with improved UI and robust bot selection.
    
    Features:
    - Professional header with logo and branding
    - Radio button selection between control, export, and import operations
    - Enhanced error handling and user feedback
    - Session management for bot transitions
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
        if not success:
            logging.error(f"❌ Launcher initialization failed: {error_msg}")
            print(f"❌ FATAL: {error_msg}")
            raise RuntimeError(f"Launcher initialization failed: {error_msg}")
            
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

    def inject_enhanced_header(self) -> None:
        """
        Inject professional header with logo, branding, and visual enhancements.
        """
        try:
            js_code = """
                // Create main header container
                var headerContainer = document.createElement('div');
                headerContainer.id = 'SOCLauncherHeader';
                headerContainer.style.cssText = `
                    text-align: center;
                    margin: 20px 0 30px 0;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    border-radius: 10px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                    color: white;
                    position: relative;
                    overflow: hidden;
                `;

                // Add decorative elements
                var decoration = document.createElement('div');
                decoration.style.cssText = `
                    position: absolute;
                    top: -50px;
                    right: -50px;
                    width: 100px;
                    height: 100px;
                    background: rgba(255,255,255,0.1);
                    border-radius: 50%;
                `;
                headerContainer.appendChild(decoration);

                // Create content wrapper
                var contentWrapper = document.createElement('div');
                contentWrapper.style.cssText = 'position: relative; z-index: 2;';

                // Create logo container
                var logoContainer = document.createElement('div');
                logoContainer.id = 'SOCLauncherLogo';
                logoContainer.style.cssText = 'margin: 15px 0; display: inline-block;';

                var logoImg = document.createElement('img');
                logoImg.id = 'SOCLauncherLogoImg';
                logoImg.alt = 'SOC Automation Suite';
                logoImg.style.cssText = `
                    max-width: 200px;
                    max-height: 80px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                    background: white;
                    padding: 5px;
                `;
                logoContainer.appendChild(logoImg);

                // Create title with enhanced styling
                var titleElement = document.createElement('div');
                titleElement.id = 'SOCLauncherTitle';
                titleElement.textContent = 'АСУ СБЗ "SOCовыжималка"';
                titleElement.style.cssText = `
                    color: #FFD700;
                    font-size: 28px;
                    font-weight: bold;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 10px 0;
                    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                    letter-spacing: 0.5px;
                `;

                // Create subtitle
                var subtitleElement = document.createElement('div');
                subtitleElement.textContent = 'Automation Suite for SOC Overrides Management';
                subtitleElement.style.cssText = `
                    color: rgba(255,255,255,0.9);
                    font-size: 14px;
                    font-style: italic;
                    margin-bottom: 10px;
                `;

                // Assemble content
                contentWrapper.appendChild(logoContainer);
                contentWrapper.appendChild(titleElement);
                contentWrapper.appendChild(subtitleElement);
                headerContainer.appendChild(contentWrapper);

                // Insert at the top of the form
                var loginForm = document.querySelector('form');
                if (loginForm) {
                    loginForm.insertBefore(headerContainer, loginForm.firstChild);
                } else {
                    // Fallback: insert at top of body
                    document.body.insertBefore(headerContainer, document.body.firstChild);
                }

                // Set logo image if base64 data is available
                if (typeof window.socLauncherLogoData !== 'undefined' && window.socLauncherLogoData) {
                    document.getElementById('SOCLauncherLogoImg').src = 'data:image/png;base64,' + window.socLauncherLogoData;
                }
            """
            self.driver.execute_script(js_code)
            
            # Set the logo image if available
            if self.base64_logo:
                self.driver.execute_script(f"window.socLauncherLogoData = '{self.base64_logo}';")
                logging.info("✅ Enhanced header with logo injected successfully")
            else:
                # Create a stylish placeholder
                placeholder_js = """
                    var logoContainer = document.getElementById('SOCLauncherLogo');
                    if (logoContainer) {
                        var placeholder = document.createElement('div');
                        placeholder.innerHTML = '🚀<br>SOC';
                        placeholder.style.cssText = `
                            color: #FFD700;
                            font-size: 24px;
                            font-weight: bold;
                            padding: 15px;
                            border: 2px solid #FFD700;
                            border-radius: 8px;
                            display: inline-block;
                            background: rgba(255,255,255,0.1);
                        `;
                        logoContainer.innerHTML = '';
                        logoContainer.appendChild(placeholder);
                    }
                """
                self.driver.execute_script(placeholder_js)
                logging.info("✅ Enhanced header with placeholder injected")

        except Exception as e:
            logging.error(f"❌ Failed to inject enhanced header: {str(e)}")

    def inject_bot_selection_panel(self) -> None:
        """
        Inject enhanced bot selection panel with improved UX.
        """
        try:
            js_code = """
                // Create selection panel container
                var selectionPanel = document.createElement('div');
                selectionPanel.id = 'BotSelectionPanel';
                selectionPanel.style.cssText = `
                    margin: 25px 0;
                    padding: 20px;
                    border: 2px solid #e0e0e0;
                    border-radius: 12px;
                    background: #f8f9fa;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                `;

                // Panel header
                var panelHeader = document.createElement('div');
                panelHeader.style.cssText = `
                    font-weight: bold;
                    font-size: 18px;
                    margin-bottom: 15px;
                    color: #2c3e50;
                    text-align: center;
                    border-bottom: 1px solid #dee2e6;
                    padding-bottom: 10px;
                `;
                panelHeader.textContent = '🔧 Select SOC Operation Type';
                selectionPanel.appendChild(panelHeader);

                // Create radio options container
                var optionsContainer = document.createElement('div');
                optionsContainer.style.cssText = 'display: flex; flex-direction: column; gap: 12px;';

                // Bot options configuration
                var botOptions = [
                    {
                        id: 'control',
                        icon: '🚀',
                        title: 'Control',
                        description: 'Apply or remove overrides in real-time',
                        color: '#3498db'
                    },
                    {
                        id: 'export', 
                        icon: '📤',
                        title: 'Export',
                        description: 'Export overrides to Excel for analysis',
                        color: '#27ae60'
                    },
                    {
                        id: 'import',
                        icon: '📥', 
                        title: 'Import',
                        description: 'Import overrides from Excel template',
                        color: '#e74c3c'
                    }
                ];

                // Create each option
                botOptions.forEach(function(option, index) {
                    var optionDiv = document.createElement('div');
                    optionDiv.style.cssText = `
                        display: flex;
                        align-items: center;
                        padding: 12px 15px;
                        border: 2px solid #e0e0e0;
                        border-radius: 8px;
                        background: white;
                        cursor: pointer;
                        transition: all 0.3s ease;
                    `;

                    // Radio button
                    var radio = document.createElement('input');
                    radio.type = 'radio';
                    radio.id = 'bot_' + option.id;
                    radio.name = 'bot_selection';
                    radio.value = option.id;
                    radio.style.cssText = `
                        margin-right: 12px;
                        transform: scale(1.2);
                        cursor: pointer;
                    `;

                    // Set default selection
                    if (option.id === 'control') {
                        radio.checked = true;
                        optionDiv.style.borderColor = option.color;
                        optionDiv.style.background = 'rgba(52, 152, 219, 0.05)';
                    }

                    // Icon and content container
                    var contentDiv = document.createElement('div');
                    contentDiv.style.cssText = 'display: flex; align-items: center; flex: 1;';

                    // Icon
                    var iconSpan = document.createElement('span');
                    iconSpan.textContent = option.icon;
                    iconSpan.style.cssText = 'font-size: 20px; margin-right: 10px;';

                    // Text content
                    var textDiv = document.createElement('div');
                    
                    var titleDiv = document.createElement('div');
                    titleDiv.textContent = option.title;
                    titleDiv.style.cssText = 'font-weight: bold; color: ' + option.color + '; font-size: 16px;';
                    
                    var descDiv = document.createElement('div');
                    descDiv.textContent = option.description;
                    descDiv.style.cssText = 'font-size: 12px; color: #666; margin-top: 2px;';

                    textDiv.appendChild(titleDiv);
                    textDiv.appendChild(descDiv);

                    // Assemble content
                    contentDiv.appendChild(iconSpan);
                    contentDiv.appendChild(textDiv);
                    
                    optionDiv.appendChild(radio);
                    optionDiv.appendChild(contentDiv);

                    // Add hover and selection effects
                    optionDiv.addEventListener('mouseenter', function() {
                        if (!radio.checked) {
                            this.style.borderColor = option.color;
                            this.style.background = 'rgba(' + parseInt(option.color.slice(1,3), 16) + ',' + parseInt(option.color.slice(3,5), 16) + ',' + parseInt(option.color.slice(5,7), 16) + ', 0.02)';
                        }
                    });

                    optionDiv.addEventListener('mouseleave', function() {
                        if (!radio.checked) {
                            this.style.borderColor = '#e0e0e0';
                            this.style.background = 'white';
                        }
                    });

                    // Radio selection handler
                    optionDiv.addEventListener('click', function() {
                        // Update all radios
                        botOptions.forEach(function(opt) {
                            var otherRadio = document.getElementById('bot_' + opt.id);
                            var otherDiv = otherRadio.parentNode;
                            otherRadio.checked = false;
                            otherDiv.style.borderColor = '#e0e0e0';
                            otherDiv.style.background = 'white';
                        });

                        // Select this one
                        radio.checked = true;
                        optionDiv.style.borderColor = option.color;
                        optionDiv.style.background = 'rgba(' + parseInt(option.color.slice(1,3), 16) + ',' + parseInt(option.color.slice(3,5), 16) + ',' + parseInt(option.color.slice(5,7), 16) + ', 0.05)';
                        
                        // Store selection
                        window.selectedBot = option.id;
                    });

                    optionsContainer.appendChild(optionDiv);
                });

                selectionPanel.appendChild(optionsContainer);

                // Insert after header and before credentials
                var header = document.getElementById('SOCLauncherHeader');
                if (header) {
                    header.parentNode.insertBefore(selectionPanel, header.nextSibling);
                } else {
                    // Fallback: insert before credentials
                    var credentialsSection = document.querySelector('#UserName, #Password').closest('div');
                    if (credentialsSection) {
                        credentialsSection.parentNode.insertBefore(selectionPanel, credentialsSection);
                    }
                }

                // Initialize selection
                window.selectedBot = 'control';
            """
            self.driver.execute_script(js_code)
            logging.info("✅ Enhanced bot selection panel injected")

        except Exception as e:
            logging.error(f"❌ Failed to inject bot selection panel: {str(e)}")

    def enter_credentials_and_prepare_launcher(self) -> None:
        """
        Enhanced launcher preparation with professional UI elements.
        """
        try:
            # Inject enhanced header
            self.inject_enhanced_header()
            
            # Inject bot selection panel
            self.inject_bot_selection_panel()

            # Enter username and password
            self.driver.find_element(By.ID, "UserName").send_keys(self.user_name)
            if self.password != "INCORRECT PASSWORD":
                self.driver.find_element(By.ID, "Password").send_keys(self.password)
            else:
                logging.error("❌ Password contains line break")
                self.inject_error_message("❌ Password contains line break.")

            # Show warning message if any
            if hasattr(self, 'warning_message') and self.warning_message:
                self.inject_info_message(self.warning_message, style_addons={'color': 'darkorange'})

            # Use mixin method to inject SOC ID input field
            self.inject_SOC_id_input()

            logging.info("✅ Launcher UI fully prepared")

        except NoSuchElementException as e:
            logging.error(f"❌ Failed to find login fields: {str(e)}")
            self.inject_error_message("❌ Failed to find login fields.")
        except Exception as e:
            logging.error(f"❌ Failed to prepare launcher UI: {str(e)}")
            self.inject_error_message(f"❌ UI preparation failed: {str(e)}")

    def wait_for_launcher_input_and_submit(self) -> OperationResult:
        """
        Wait for both SOC ID input and form submission, then return selected bot.
        Returns (success, error_message, severity)
        """
        try:
            # Wait for SOC input with proper validation
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(
                WaitForSOCInput((By.ID, "InjectedInput"), self)
            )

            # Check browser state after wait completes
            if not self.is_browser_alive():
                error_msg = "🏁 Browser closed by user during input"
                logging.info(error_msg)
                return False, error_msg, ErrorLevel.TERMINAL

            # Get the selected bot type
            self.selected_bot = self.get_selected_bot()

            # Get the SOC_id from the injected input field
            raw_soc_id = self.driver.find_element(By.ID, "InjectedInput").get_attribute("value")
            logging.info(f"🔧 Raw SOC id: {raw_soc_id}, Selected bot: {self.selected_bot}")

            # Strip leading zero if SOC ID is 8 digits and starts with 0
            if len(raw_soc_id) == 8 and raw_soc_id.startswith('0'):
                self.SOC_id = raw_soc_id[1:]
                logging.info(f"🔧 Stripped leading zero: '{raw_soc_id}' → '{self.SOC_id}'")
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

            logging.info(f"✅ Processed SOC id: {self.SOC_id}, Bot: {self.selected_bot}")

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

    def launch_selected_bot(self) -> OperationResult:
        """
        Launch the selected bot with the obtained SOC ID and existing browser session.
        Returns (success, error_message, severity)
        """
        try:
            logging.info(f"🚀 Launching {self.selected_bot} bot for SOC {self.SOC_id}")

            # Check browser state before launching bot
            if not self.is_browser_alive():
                return False, "Browser closed before bot launch", ErrorLevel.TERMINAL

            # Brief pause to let driver stabilize
            import time
            time.sleep(0.5)

            # Create appropriate bot instance
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

            # Inject transition message
            bot_messages = {
                "control": "🚀 Launching SOC Controller...",
                "export": "📤 Launching SOC Exporter...", 
                "import": "📥 Launching SOC Importer..."
            }
            self.inject_info_message(
                bot_messages.get(self.selected_bot, "Launching SOC bot..."),
                style_addons={'color': 'green'}
            )

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
        Main launcher workflow with enhanced error handling and user feedback.
        """
        if not self._initialized:
            logging.error("❌ Launcher not properly initialized")
            return

        try:
            logging.info("🚀 Starting SOC Launcher...")

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

            logging.info("🏁 Launcher workflow completed successfully")

        except Exception as e:
            logging.error(f"❌ Launcher execution failed: {str(e)}")
            if self.is_browser_alive():
                self.inject_error_message(f"❌ Launcher execution failed: {str(e)}")

if __name__ == "__main__":
    try:
        launcher = SOC_Launcher()
        launcher.run()
    except Exception as e:
        print(f"❌ Failed to start launcher: {str(e)}")
        logging.error(f"❌ Launcher startup failed: {str(e)}")
