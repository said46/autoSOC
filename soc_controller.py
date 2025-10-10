# soc_controller.py
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (NoSuchElementException, NoSuchWindowException)
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

import configparser

import logging

from base_web_bot import BaseWebBot, message_box
from soc_base_mixin import SOC_BaseMixin


class SOC_Controller(BaseWebBot, SOC_BaseMixin):    
    """
    Specialized bot for SOC (Safety Override Certificate) overrides automation.
    
    This controller combines BaseWebBot's web automation capabilities with 
    SOC_BaseMixin's SOC-specific functionality to automate SOC point management.
    
    Key features:
    - SOC ID input and validation
    - Role-based access control
    - SOC status monitoring and transitions
    - Overrides state manipulation
    - Multi-role processing workflow
    """
    
    # Index for selecting final state in dropdowns
    # In all cases override manipulation is the change of 2-options dropdown list from 1st option to 2nd one
    FINAL_STATE_DROPDOWN_INDEX = 1 
    
    def __init__(self, soc_id=None):
        """Initialize the SOC controller with combined base and mixin functionality."""
        BaseWebBot.__init__(self)
        SOC_BaseMixin.__init__(self)
        self.warning_message: str | None = None  # Stores configuration warnings
        self.load_configuration()

        # Use provided SOC ID or maintain existing logic
        if soc_id:
            self.SOC_id = soc_id

    def set_soc_id(self, soc_id: str) -> None:
        """Set SOC ID externally for unified workflow."""
        self.SOC_id = soc_id

    # ===== PROPERTY DEFINITIONS =====
    
    @property    
    def base_link(self) -> str:
        """Abstract property implementation - returns the base URL for navigation."""
        return self._base_link        
   
    # ===== CONFIGURATION MANAGEMENT =====
    
    def load_configuration(self) -> None:        
        """
        Load all configuration settings from the ini file.
        
        This method reads and parses the SOC.ini configuration file, setting up:
        - User credentials and authentication
        - Application URLs and timeouts
        - SOC-specific settings (roles, statuses, patterns)
        - Database connectivity (if enabled)
        
        Configuration is loaded from multiple sections: Settings, Roles, Statuses, Database, SQL
        """
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.config_file, encoding="utf8")

        # Load ALL configuration including base settings
        self.user_name = config.get('Settings', 'user_name', fallback='xxxxxx')
        
        # Use mixin's process_password method for secure password handling
        raw_password = config.get('Settings', 'password', fallback='******')
        self.password = self.process_password(raw_password)
        
        # Check for password formatting issues
        if '\n' in self.password:
            self.password = 'INCORRECT PASSWORD'
            
        self._base_link = config.get('Settings', 'base_link', fallback='http://eptw.sakhalinenergy.ru/')
        self.MAX_WAIT_USER_INPUT_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_USER_INPUT_DELAY_SECONDS', fallback=300)
        self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_PAGE_LOAD_DELAY_SECONDS', fallback=30)        
        self.SOC_id = config.get('Settings', 'SOC_id', fallback='')
        
        # Load role and status configurations
        self.SOC_roles = config.get('Roles', 'SOC_roles', fallback='OAC,OAV').split(',')
        self.good_statuses = config.get(
            'Statuses',
            'good_statuses', 
            fallback='принято для установки-запрошено для удаления-установлено, не подтверждено-удалено, не подтверждено').split('-')
        self.SOC_status_approved_for_apply = config.get('Statuses', 'SOC_status_approved_for_apply', fallback='одобрено для установки')
        
        # Map role display names to role codes
        self.roles = {
            config.get('Roles', 'OAC', fallback='Исполняющий форсирование'): 'OAC', 
            config.get('Roles', 'OAV', fallback='Проверяющий форсирование'): 'OAV'
        }
                      
        self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = config.getboolean('Database', 'CONNECT_TO_DB_FOR_PARTIAL_SOC_ID', fallback=False)
                           
        # Load database configuration using separate method
        self._load_database_configuration(config)

        # Configure the mixin with SOC pattern based on database connectivity
        if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
            self.SOC_ID_PATTERN = r"^\d{4,8}$"  # Allow shorter IDs when DB lookup is enabled
        else:
            self.SOC_ID_PATTERN = r"^\d{7,8}$"  # Require full SOC IDs otherwise
    
    def _load_database_configuration(self, config: configparser.ConfigParser) -> None:
        """
        Load database configuration from config parser.
        
        Args:
            config: The configparser instance with loaded configuration
            
        💡 TIP: Separating database config makes the main load_configuration method cleaner
        💡 TIP: This method handles all database-related configuration in one place
        """
        # Database configuration is only loaded if database features are enabled
        if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
            try:
                self.db_server = config.get('Database', 'server')
                
                # Use mixin's process_password method for database password
                raw_db_password = config.get('Database', 'password')
                self.db_password = self.process_password(raw_db_password)
                
                self.db_database = config.get('Database', 'database') 
                self.db_username = config.get('Database', 'username')
                                
                # Validate none are empty
                if not all([self.db_server, self.db_database, self.db_username]):
                    raise configparser.NoOptionError('Database', 'Some database credentials are empty')
                                
                self.SQL_template = config.get('SQL', 'SOC_query', fallback="").strip(' \n\r\t')
                if self.SQL_template and not self.SQL_template.strip().lower().startswith('select'):
                    raise ValueError("SQL query must start with SELECT")                        
            
            except (configparser.NoSectionError, configparser.NoOptionError) as e:            
                self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
                self.warning_message = f"⚠️  Database configuration incomplete: {str(e)}. Disabling database features."
                logging.warning(self.warning_message)
            except ValueError as e:
                self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
                self.warning_message = "⚠️  SQL query in ini-file doesn't start with SELECT or is empty. Disabling database features."
                logging.warning(self.warning_message)                
  
    # ===== SOC STATUS AND ROLE MANAGEMENT =====
    
    def get_SOC_status(self) -> str:    
        """
        Get the current status of the SOC from the details page.
        
        Uses JavaScript execution with XPath to extract the status value from the page.
        
        Returns:
            Current SOC status in lowercase, or empty string if retrieval fails            
        """
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
                raise ValueError("SOC status cannot be empty")
            logging.info(f"👆 SOC {self.SOC_id} status: '{status}'")
            return status.lower()
        except Exception as e:
            logging.error(f"❌ Failed to get SOC status: {str(e)}")        
            self.inject_error_message(f"❌ Failed to get SOC status: {str(e)} ")
            return ''
                           
    def get_current_role(self) -> str:
        """
        Get the current role from the page using the role span element.
        
        Returns:
            Role code ('OAC', 'OAV', or 'unknown') based on the current role display
        """
        try:
            # Look for the role span with class "k-state-active"
            role_span = self.driver.find_element(By.XPATH, "//span[@class='k-state-active' and contains(text(), 'Роль:')]")
            role_text = role_span.text.strip()
            
            # Extract just the role name (remove "Роль: " prefix)
            if "Роль:" in role_text:
                role_name = role_text.split("Роль:")[1].strip()
                logging.info(f"👤 Current role detected: '{role_name}'")
                return self.roles[role_name]
            else:
                logging.warning(f"⚠️  Unexpected role text format: '{role_text}'")
                return "unknown"
                
        except NoSuchElementException:
            logging.warning("⚠️  Role span element not found, cannot determine current role")
            return "unknown"
        except Exception as e:
            logging.warning(f"⚠️  Could not determine current role: {str(e)}")
            return "unknown"    
    
    def switch_role(self, role: str) -> None:
        """
        Switch to the specified role using Kendo dropdown.
        
        Args:
            role: The role code to switch to ('OAC', 'OAV', etc.)
            
        If the current role already matches the target role, no action is taken.
        """
        try:
            if self.get_current_role() == role:
                logging.info(f"✅ The role is already {role}, no need to switch")
                return
                
            self.driver.get(self._base_link + r"User/ChangeRole")
            
            # Wait for Kendo components to initialize
            self.wait_for_kendo_dropdown("CurrentRoleName")
            
            # Set value using Kendo API
            set_role_script = f"""
                var dropdown = $('#CurrentRoleName').data('kendoDropDownList');
                dropdown.value('{role}');
                dropdown.trigger('change');
                return true;
            """
            self.driver.execute_script(set_role_script)
            
            # Wait for the value to actually change in the Kendo component
            WebDriverWait(self.driver, 10).until(
                lambda _: self.driver.execute_script(
                    f"return $('#CurrentRoleName').data('kendoDropDownList').value() === '{role}';"
                )
            )
            
            self.click_button((By.ID, 'ConfirmHeader'))            
            
            logging.info(f"✅ The role switched to {role} successfully")
        except NoSuchWindowException:
            logging.warning(f"🏁  Browser windows was closed, end of script")
            self.safe_exit()           
        except Exception as e:
            logging.error(f"❌ Failed to switch the role: {str(e)}")
            self.inject_error_message(f"❌ Failed to switch the role")
    
    # ===== SOC PROCESSING METHODS =====
    
    def accept_SOC_to_apply(self) -> None:
        """
        Accept SOC for apply and wait for status change.
        
        This method handles the workflow state transition when a SOC needs to be
        accepted for application, typically requiring OAC role privileges.
        """
        try:
            old_status = self.get_SOC_status()
            logging.info(f"⏳ Current SOC status: '{old_status}' - proceeding with accept for apply")
            
            # Wait for Kendo components to initialize
            logging.info("⏳ Waiting for ActionsList dropdown...")
            self.wait_for_kendo_dropdown("ActionsList")
            logging.info("✅ ActionsList dropdown ready")
            
            # Build the action value
            action_value = f'/Soc/TriggerChangeWorkflowState/{self.SOC_id}?trigger=AcceptForApply'
            logging.info(f"🔧 Setting action value: {action_value}")
            
            # Set dropdown value
            set_action_script = """
                var dropdown = $('#ActionsList').data('kendoDropDownList');
                dropdown.value(arguments[0]);
                dropdown.trigger('change');
            """
            self.driver.execute_script(set_action_script, action_value)
            logging.info("✅ Action value set in dropdown")
            
            # Wait for value to be set
            logging.info("⏳ Verifying dropdown value was set...")
            WebDriverWait(self.driver, 10).until(
                lambda _: self.driver.execute_script(
                    "return $('#ActionsList').data('kendoDropDownList').value() === arguments[0];",
                    action_value
                )
            )
            logging.info("✅ Dropdown value verified")
            
            # Click apply button
            self.click_button((By.ID, 'ApplyActionButton'))
            
            # Wait for status to actually change
            logging.info(f"⏳ Waiting for status to change from '{old_status}'...")
            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                lambda _: self.get_SOC_status() != old_status
            )
            
            new_status = self.get_SOC_status()
            logging.info(f"✅ SOC {self.SOC_id} successfully accepted - status changed to '{new_status}'")
            
        except NoSuchWindowException:
            logging.warning(f"🏁  Browser window was closed, end of script")
            self.safe_exit()
        except Exception as e:
            logging.error(f"❌ Failed to accept SOC {self.SOC_id} for apply: {str(e)}")
            self.inject_error_message(f"❌ Failed to accept SOC {self.SOC_id} for apply")

    def update_points(self):
        """
        Update all points in the SOC to their final state.
        
        Iterates through all enabled point dropdowns and updates them to the
        configured final state (typically index 1 in the dropdown).
        
        Kendo API approach failed (becomes too complicated), because the Kendo dropdowns are created dynamically 
        by the updateOverrideFunctions.onGridDataBound() function, but they're not initialized yet when the script runs.
        This method uses traditional Selenium Select approach which turned out to be more reliable.
        """
        try:
            # Find all enabled CurrentStateSelect dropdown elements
            item_xpath = f"//select[@id='CurrentStateSelect' and not(@disabled)]"
            sel_items = self.driver.find_elements(By.XPATH, item_xpath)
            logging.info(f"Number of points to update is {len(sel_items)}")
            
            # Process each point dropdown
            for point_index, sel_item in enumerate(sel_items, start=1):
                drop = Select(sel_item)
                try:
                    # Only update dropdowns with multiple options
                    if len(drop.options) > 1:
                        drop.select_by_index(self.FINAL_STATE_DROPDOWN_INDEX)
                        selected_text = drop.first_selected_option.text
                        logging.info(f"✅ Point {point_index} has been updated to {selected_text}")
                except Exception as e:
                    logging.warning(f"⚠️  Точка не обновлена: {str(e)}")
                    message_box("⚠️  Точка не обновлена", f"{str(e)}", 0)
        except NoSuchElementException as e:
            logging.error(f"❌ Failed to update points: {str(e)}")
            self.inject_error_message(f"❌ Failed to update some points")
    
    # ===== WORKFLOW COORDINATION METHODS =====
    
    def navigate_to_soc_and_check_status(self):
        """
        Navigate to SOC details page and check/update status if needed.
        
        This method:
        1. Navigates to the SOC details page
        2. Performs various security and access checks
        3. Checks if SOC needs to be accepted for apply
        4. Handles role switching and status transitions if needed
        """
        # Open SOC details web page
        SOC_view_base_link = self._base_link + r"Soc/Details/"
        self.driver.get(SOC_view_base_link + self.SOC_id)
        
        # Perform security and access checks
        self.error_404_not_present_check()
        self.url_contains_SOC_Details_check()

        SOC_status = self.get_SOC_status()
        logging.info(f"🔍 Initial SOC status: '{SOC_status}'")

        # If SOC needs to be accepted for apply, switch to OAC role and process
        if SOC_status == self.SOC_status_approved_for_apply:
            logging.info("🔄 SOC needs to be accepted for apply - switching role to OAC")
            
            # Switch the role to OAC
            self.switch_role('OAC')
                       
            # Reopen SOC details page after role change
            self.driver.get(SOC_view_base_link + self.SOC_id)
                       
            self.accept_SOC_to_apply()
            # Waiting is inside of accept_SOC_to_apply function!!! 
            SOC_status = self.get_SOC_status()
            logging.info(f"🔍 SOC status after accept attempt: '{SOC_status}'")

        # Validate final SOC status is acceptable for processing
        if SOC_status not in self.good_statuses:
            logging.error(f'❌ SOC {self.SOC_id} status is "{SOC_status}", the script cannot proceed.')
            locator = (By.XPATH, "//div[@id='issowFormContainer']//div[contains(@class, 'user-form')]")
            self.inject_error_message(f'❌ SOC {self.SOC_id} status is "{SOC_status}"', 
                                        locator, style_addons={'width': '100%', 'align': 'center'})

    def process_soc_roles(self):
        """
        Process SOC for each required role in sequence.
        
        Iterates through configured SOC roles (typically OAC, OAV) and:
        1. Switches to the target role
        2. Navigates to the update page
        3. Performs security checks
        4. Updates all points
        5. Waits for user confirmation
        """
        # Process each role (usually OAC, OAV, depends on the values in the ini-file)
        for SOC_role in self.SOC_roles:
            # Change the role
            self.switch_role(SOC_role)

            # Navigate to Edit Overrides page
            SOC_update_base_link = self._base_link + r"Soc/UpdateOverride/"
            self.driver.get(SOC_update_base_link + self.SOC_id)  # Example: http://eptw.sakhalinenergy.ru/Soc/UpdateOverride/1458894

            # Check if the SOC is locked or access is denied using mixin methods
            self.SOC_locked_check()
            self.access_denied_check()

            # Wait for points to be loaded and ready
            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                lambda _: len(self.driver.find_elements(By.XPATH, "//select[@id='CurrentStateSelect' and not(@disabled)]")) >= 1
            )            
            
            # Update all points
            self.update_points()
            
            # Wait for user to press confirm button
            self.wait_for_user_confirmation()

    def wait_for_user_confirmation(self):
        """
        Wait for user to press confirm button after point updates.
        
        Injects a guidance message and waits for the page to transition to the
        home page, indicating the user has pressed the confirm button.
        """
        msg = '⚠️  Скрипт ожидает нажатия кнопки "Подтвердить".'
        xpath = "//div[@id='bottomWindowButtons']/div"
        self.inject_info_message(msg, (By.XPATH, xpath), {'color': 'lawngreen'})
        try:
            # Wait for page title change to confirm user pressed the confirm button
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(
                EC.title_is(self.EXPECTED_HOME_PAGE_TITLE)
            )
            logging.info("🏁  Confirm pressed, home page loaded")
        except NoSuchWindowException as e:
            logging.error(f"⚠️  User closed the browser window.")
            self.safe_exit()
        except Exception as e:
            logging.error(f"❌ Failed to wait for user input ('Confirm' button): {str(e)}")
            self.inject_error_message(f"❌ Failed to wait for user input ('Confirm' button)")

    # ===== MAIN AUTOMATION WORKFLOW =====
    
    def run(self, standalone=False):
        """
        Main automation workflow coordinating all SOC processing steps.
        
        Execution sequence:
        1. Initialize and login
        2. Wait for SOC ID input and submit
        3. Navigate to SOC and check status
        4. Process SOC through all required roles
        5. Clean up resources
        """
        if standalone:
            self.navigate_to_base()
            self.enter_credentials_and_prepare_soc_input()
            self.wait_for_soc_input_and_submit()
        self.navigate_to_soc_and_check_status()
        self.process_soc_roles()
        self.safe_exit()

if __name__ == "__main__":
    # Entry point for script execution
    bot = SOC_Controller()
    bot.run(standalone=True)