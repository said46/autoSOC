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
    """Specialized bot for SOC points automation"""
    FINAL_STATE_DROPDOWN_INDEX = 1
    EXPECTED_HOME_PAGE_TITLE = "СНД - Домашняя страница"    
    
    def __init__(self):
        BaseWebBot.__init__(self)
        SOC_BaseMixin.__init__(self)
        self.warning_message: str | None = None
        self.load_configuration()

    @property    
    def base_link(self) -> str:
        return self._base_link        
   
    def _load_database_configuration(self, config: configparser.ConfigParser) -> None:
        """
        Load database configuration from config parser
        
        💡 TIP: Separating database config makes the main load_configuration method cleaner
        💡 TIP: This method handles all database-related configuration in one place
        """
        # Database configuration
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
                    raise ValueError                        
            
            except (configparser.NoSectionError, configparser.NoOptionError) as e:            
                self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
                self.warning_message = f"⚠️  Database configuration incomplete: {str(e)}. Disabling database features."
                logging.warning(self.warning_message)
            except ValueError as e:
                self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
                self.warning_message = "⚠️  SQL query in ini-file doesn't start with SELECT or is empty. Disabling database features."
                logging.warning(self.warning_message)        
    
    def load_configuration(self) -> None:        
        """
        Load all configuration settings from the ini file
        
        💡 TIP: Using a separate method for database config keeps this method clean
        💡 TIP: All configuration-related logic is centralized in this method
        """
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.config_file, encoding="utf8")

        # Load ALL configuration including base settings
        self.user_name = config.get('Settings', 'user_name', fallback='xxxxxx')
        
        # Use mixin's process_password method instead of local implementation
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
        self.roles = {config.get('Roles', 'OAC', fallback='Исполняющий форсирование'): 'OAC', 
                      config.get('Roles', 'OAV', fallback='Проверяющий форсирование'): 'OAV'}
                      
        self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = config.getboolean('Database', 'CONNECT_TO_DB_FOR_PARTIAL_SOC_ID', fallback=False)
                           
        # Load database configuration using separate method
        self._load_database_configuration(config)

        # Configure the mixin with SOC pattern
        if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
            self.SOC_ID_PATTERN = r"^\d{4,8}$"
        else:
            self.SOC_ID_PATTERN = r"^\d{7,8}$"
            
  
    def get_SOC_status(self) -> str:    
        """
        Get the current status of the SOC
        
        💡 TIP: Uses JavaScript execution to extract status from the page
        💡 TIP: Returns empty string if status cannot be retrieved
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
        """Get the current role from the page using the role span element"""
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
        """Switch to the specified role using Kendo dropdown"""
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

    def accept_SOC_to_apply(self) -> None:
        """Accept SOC for apply and wait for status change"""
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
            logging.info("⏳ Clicking ApplyActionButton...")
            self.click_button((By.ID, 'ApplyActionButton'))
            logging.info("✅ Apply button clicked")
            
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
        Update all points in the SOC
        
        💡 TIP: Kendo API approach failed (becomes too complicated), because the Kendo dropdowns are created dynamically 
        by the updateOverrideFunctions.onGridDataBound() function, but they're not initialized yet when our script runs.
        💡 TIP: This method uses traditional Selenium Select approach which is more reliable
        """
        try:
            # change the value of Confirm Current State dropdown list for each point, for that
            # find all the elements with id=CurrentStateSelect that are not disabled
            item_xpath = f"//select[@id='CurrentStateSelect' and not(@disabled)]"
            sel_items = self.driver.find_elements(By.XPATH, item_xpath)
            logging.info(f"Number of points to update is {len(sel_items)}")
            # for each dropdown list
            for point_index, sel_item in enumerate(sel_items, start=1):
                # select the dropdown list
                drop = Select(sel_item)
                try:
                    # check if the dropdown list contains more than a single item
                    if len(drop.options) > 1:
                    # and choose the second value
                        drop.select_by_index(self.FINAL_STATE_DROPDOWN_INDEX)
                        selected_text = drop.first_selected_option.text
                        logging.info(f"✅ Point {point_index} has been updated to {selected_text}")
                except Exception as e:
                    logging.warning(f"⚠️  Точка не обновлена: {str(e)}")
                    message_box("⚠️  Точка не обновлена", f"{str(e)}", 0)
        except NoSuchElementException as e:
            logging.error(f"❌ Failed to update points: {str(e)}")
            self.inject_error_message(f"❌ Failed to update some points")
                   
    def initialize_and_login(self):
        """Initialize the bot and perform login using mixin methods"""
        self.navigate_to_base()
        # Use mixin method for login process
        self.perform_login()

    def navigate_to_soc_and_check_status(self):
        """Navigate to SOC details page and check/update status if needed"""
        # open SOC details web page
        SOC_view_base_link = self._base_link + r"Soc/Details/"
        self.driver.get(SOC_view_base_link + self.SOC_id)
        
        self.error_404_not_present_check()
        self.url_contains_SOC_Details_check()

        SOC_status = self.get_SOC_status()
        logging.info(f"🔍 Initial SOC status: '{SOC_status}'")

        # if SOC_status == "approved for apply", there is a need to change the role to OAC and accept the SOC for apply
        if SOC_status == self.SOC_status_approved_for_apply:
            logging.info("🔄 SOC needs to be accepted for apply - switching role to OAC")
            
            # switch the role to OAC
            self.switch_role('OAC')
                       
            # open SOC details web page - not sure it is necessary, as it will be opened automatically after changing the role
            self.driver.get(SOC_view_base_link + self.SOC_id)
                       
            self.accept_SOC_to_apply()
            # Waiting is inside of accept_SOC_to_apply function!!! 
            SOC_status = self.get_SOC_status()
            logging.info(f"🔍 SOC status after accept attempt: '{SOC_status}'")

        if SOC_status not in self.good_statuses:
            logging.error(f'❌ SOC {self.SOC_id} status is "{SOC_status}", the script cannot proceed.')
            locator = (By.XPATH, "//div[@id='issowFormContainer']//div[contains(@class, 'user-form')]")
            self.inject_error_message(f'❌ SOC {self.SOC_id} status is "{SOC_status}"', 
                                        locator, style_addons={'width': '100%', 'align': 'center'})

    def process_soc_roles(self):
        """Process SOC for each required role"""
        # for each role (usually OAC, OAV, depends on the values in the ini-file)
        for SOC_role in self.SOC_roles:
            # change the role
            self.switch_role(SOC_role)

            # navigate to Edit Overrides page
            SOC_update_base_link = self._base_link + r"Soc/UpdateOverride/"
            self.driver.get(SOC_update_base_link + self.SOC_id) #example: http://eptw.sakhalinenergy.ru/Soc/UpdateOverride/1458894

            # check if the SOC is locked or access is denied using mixin methods
            self.SOC_locked_check()
            self.access_denied_check()

            # Wait for several points to be loaded and ready
            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                lambda _: len(self.driver.find_elements(By.XPATH, "//select[@id='CurrentStateSelect' and not(@disabled)]")) >= 1
            )            
            # update all points
            self.update_points()
            
            self.wait_for_user_confirmation()

    def wait_for_user_confirmation(self):
        """Wait for user to press confirm button"""
        msg = '⚠️  Скрипт ожидает нажатия кнопки "Подтвердить".'
        xpath = "//div[@id='bottomWindowButtons']/div"
        self.inject_info_message(msg, (By.XPATH, xpath), {'color': 'lawngreen'})
        try:
            # after injecting the text, the script waits for MAX_WAIT_USER_INPUT_DELAY_SECONDS minutes for the web page title to be changed
            # to "СНД - Домашняя страница", to ensure the user pressed the confirm button
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(EC.title_is(self.EXPECTED_HOME_PAGE_TITLE))
            logging.info("🏁  Confirm pressed, home page loaded")
        except NoSuchWindowException as e:
            logging.error(f"⚠️  User closed the browser window.")
            self.safe_exit()
        except Exception as e:
            logging.error(f"❌ Failed to wait for user input ('Confirm' button): {str(e)}")
            self.inject_error_message(f"❌ Failed to wait for user input ('Confirm' button)")

    def run_automation(self):
        """Main automation workflow"""
        self.initialize_and_login()
        self.wait_for_soc_input_and_submit()
        self.navigate_to_soc_and_check_status()
        self.process_soc_roles()
        self.driver.quit()

if __name__ == "__main__":
    bot = SOC_Controller()
    bot.run_automation()