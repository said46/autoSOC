# soc_launcher.py
import logging
import configparser
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import TimeoutException

from base_web_bot import BaseWebBot
from soc_base_mixin import SOC_BaseMixin
from soc_controller import SOC_Controller
from soc_exporter import SOC_Exporter
from soc_importer import SOC_Importer


class SOC_Launcher(BaseWebBot, SOC_BaseMixin):
    """
    Unified SOC automation launcher with mode selection.
    
    Provides a common entry point that handles:
    - Authentication and SOC ID input
    - Mode selection via radio buttons
    - Routing to appropriate SOC component
    - Shared initialization logic
    """
    
    def __init__(self):
        """Initialize the SOC launcher with combined base and mixin functionality."""
        BaseWebBot.__init__(self)
        SOC_BaseMixin.__init__(self)
        self.load_configuration()
        self.selected_mode = None  # Will be set during user selection

    @property
    def base_link(self) -> str:
        """Abstract property implementation - returns the base URL for navigation."""
        return self._base_link
    
    def load_configuration(self) -> None:
        """
        Load configuration settings from the INI file.
        """
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.config_file, encoding="utf8")

        # Load authentication and application settings
        self.user_name = config.get('Settings', 'user_name', fallback='xxxxxx')
        
        # Process password with base64 decoding fallback
        raw_password = config.get('Settings', 'password', fallback='******')
        self.password = self.process_password(raw_password)
        
        # Check for password formatting issues
        if '\n' in self.password:
            self.password = 'INCORRECT PASSWORD'
            
        self._base_link = config.get('Settings', 'base_link', fallback='http://eptw.sakhalinenergy.ru/')
        self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_PAGE_LOAD_DELAY_SECONDS', fallback=20)
        self.MAX_WAIT_USER_INPUT_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_USER_INPUT_DELAY_SECONDS', fallback=300)

        logging.info(f"✅ Configuration loaded from {self.config_file}")

    def inject_mode_selection(self) -> None:
        """
        Inject radio button selection for SOC operation mode.
        
        Creates a user interface with three options:
        - Control: SOC point management and role processing
        - Import: Import overrides from Excel file
        - Export: Export overrides to Excel file
        """
        try:
            js_code = """
                // Create mode selection container
                var container = document.createElement('div');
                container.id = 'ModeSelectionContainer';
                container.style.cssText = 'margin: 20px 0; padding: 15px; border: 2px solid #ddd; border-radius: 8px; background: #f9f9f9;';
                
                // Add title
                var title = document.createElement('h3');
                title.textContent = '🔧 Select SOC Operation Mode';
                title.style.cssText = 'margin-bottom: 15px; text-align: center; color: #333;';
                container.appendChild(title);
                
                // Mode options
                var modes = [
                    {id: 'control', label: '🚀 Control - Process SOC Points', description: 'Automate SOC point management and role processing'},
                    {id: 'import', label: '📥 Import - Load from Excel', description: 'Import overrides from Excel file to SOC'},
                    {id: 'export', label: '📤 Export - Save to Excel', description: 'Export SOC overrides to Excel file for backup'}
                ];
                
                // Create radio buttons
                modes.forEach(function(mode, index) {
                    var radioDiv = document.createElement('div');
                    radioDiv.style.cssText = 'margin: 10px 0; padding: 10px; border: 1px solid #ccc; border-radius: 5px; background: white;';
                    
                    var radioInput = document.createElement('input');
                    radioInput.type = 'radio';
                    radioInput.name = 'socMode';
                    radioInput.id = 'mode_' + mode.id;
                    radioInput.value = mode.id;
                    radioInput.style.marginRight = '10px';
                    
                    var radioLabel = document.createElement('label');
                    radioLabel.htmlFor = 'mode_' + mode.id;
                    radioLabel.innerHTML = '<strong>' + mode.label + '</strong><br><small style="color: #666;">' + mode.description + '</small>';
                    
                    radioDiv.appendChild(radioInput);
                    radioDiv.appendChild(radioLabel);
                    container.appendChild(radioDiv);
                    
                    // Add click handler to select on entire div click
                    radioDiv.addEventListener('click', function() {
                        radioInput.checked = true;
                        document.getElementById('InjectedInput').focus();
                    });
                });
                
                // Add confirmation button
                var buttonContainer = document.createElement('div');
                buttonContainer.style.cssText = 'text-align: center; margin-top: 15px;';
                
                var confirmButton = document.createElement('button');
                confirmButton.id = 'ModeConfirmBtn';
                confirmButton.textContent = '✅ Confirm Selection & Continue';
                confirmButton.style.cssText = 'padding: 10px 20px; background: #007cba; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 14px;';
                confirmButton.disabled = true;
                
                confirmButton.addEventListener('click', function() {
                    var selectedMode = document.querySelector('input[name="socMode"]:checked');
                    if (selectedMode) {
                        this.setAttribute('data-mode-selected', selectedMode.value);
                    }
                });
                
                buttonContainer.appendChild(confirmButton);
                container.appendChild(buttonContainer);
                
                // Enable/disable button based on selection
                var radios = document.getElementsByName('socMode');
                radios.forEach(function(radio) {
                    radio.addEventListener('change', function() {
                        confirmButton.disabled = !document.querySelector('input[name="socMode"]:checked');
                        confirmButton.style.background = confirmButton.disabled ? '#ccc' : '#007cba';
                    });
                });
                
                // Insert after SOC input
                var socInput = document.getElementById('InjectedInput');
                if (socInput && socInput.parentNode) {
                    socInput.parentNode.appendChild(container);
                }
            """
            self.driver.execute_script(js_code)
            logging.info("✅ Mode selection interface injected successfully")
            
        except Exception as e:
            logging.error(f"❌ Failed to inject mode selection: {str(e)}")
            raise

    def wait_for_mode_selection(self) -> str:
        """
        Wait for user to select an operation mode and confirm.
        
        Returns:
            Selected mode string ('control', 'import', or 'export')
        """
        try:
            logging.info("⏳ Waiting for mode selection...")
            
            # Wait for mode selection with timeout
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(
                lambda driver: driver.execute_script(
                    "return document.getElementById('ModeConfirmBtn')?.getAttribute('data-mode-selected') !== null;"
                )
            )
            
            # Get the selected mode
            selected_mode = self.driver.execute_script(
                "return document.getElementById('ModeConfirmBtn').getAttribute('data-mode-selected');"
            )
            
            logging.info(f"✅ Mode selected: {selected_mode}")
            return selected_mode
            
        except TimeoutException:
            logging.error("❌ Timeout waiting for mode selection")
            self.inject_error_message("❌ No mode selected within timeout period")
            raise
        except Exception as e:
            logging.error(f"❌ Error during mode selection: {str(e)}")
            raise

    def execute_selected_mode(self, mode: str) -> None:
        """
        Execute the selected SOC operation mode.
        
        Args:
            mode: The selected operation mode ('control', 'import', or 'export')
        """
        try:
            logging.info(f"🚀 Executing selected mode: {mode}")
            
            if mode == 'control':
                controller = SOC_Controller()
                controller.driver = self.driver  # Reuse the same browser session
                controller.SOC_id = self.SOC_id  # Pass the SOC ID
                controller.run()
                
            elif mode == 'import':
                importer = SOC_Importer()
                importer.driver = self.driver  # Reuse the same browser session
                importer.SOC_id = self.SOC_id  # Pass the SOC ID
                importer.run()
                
            elif mode == 'export':
                exporter = SOC_Exporter()
                exporter.driver = self.driver  # Reuse the same browser session
                exporter.SOC_id = self.SOC_id  # Pass the SOC ID
                exporter.run()
                
            else:
                raise ValueError(f"Unknown mode: {mode}")
                
        except Exception as e:
            logging.error(f"❌ Error executing mode '{mode}': {str(e)}")
            self.inject_error_message(f"❌ Error in {mode} execution")
            raise

    def run_common_workflow(self) -> None:
        """
        Execute the common workflow shared by all SOC components.
        
        This handles the shared initialization steps:
        1. Navigate to base URL
        2. Enter credentials
        3. Inject SOC ID input
        4. Wait for SOC ID input and submit
        5. Inject mode selection
        6. Wait for mode selection
        7. Execute selected mode
        """
        try:
            logging.info("🚀 Starting common SOC automation workflow")
            
            # Step 1: Navigate to base URL
            self.navigate_to_base()
            
            # Step 2: Enter credentials and prepare SOC input
            self.enter_credentials_and_prepare_soc_input()
            
            # Step 3: Inject mode selection UI
            self.inject_mode_selection()
            
            # Step 4: Wait for SOC ID input and submit
            self.wait_for_soc_input_and_submit()
            
            # Step 5: Wait for mode selection
            selected_mode = self.wait_for_mode_selection()
            
            # Step 6: Execute the selected mode
            self.execute_selected_mode(selected_mode)
            
            logging.info("🏁 Common SOC workflow completed successfully")
            
        except Exception as e:
            logging.error(f"❌ Common workflow failed: {str(e)}")
            self.inject_error_message(f"❌ Automation failed: {str(e)}")
        finally:
            self.safe_exit()


if __name__ == "__main__":
    # Entry point for unified SOC automation
    launcher = SOC_Launcher()
    launcher.run_common_workflow()