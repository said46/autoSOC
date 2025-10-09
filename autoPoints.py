from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoSuchWindowException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

import configparser
import re
import base64
from typing_extensions import override, Optional

import logging

from autoDB import SQLQueryDirect
from base_web_bot import BaseWebBot, message_box

class SOCBot(BaseWebBot):    
    """Specialized bot for SOC points automation"""
    FINAL_STATE_DROPDOWN_INDEX = 1
    EXPECTED_HOME_PAGE_TITLE = "СНД - Домашняя страница"    
    
    # callable class
    class WaitForSOCInput:
        """SOCBot-specific wait condition for SOC input"""
        def __init__(self, locator, soc_bot):
            self.locator = locator
            self.soc_bot = soc_bot
            self.last_value = ""

        def __call__(self, driver):
            try:
                # Browser closure check
                if self.soc_bot._is_browser_closed():
                    return True  # Return True to stop waiting and continue
                    
                injected_input = driver.find_element(*self.locator)
                current_value = injected_input.get_attribute("value")
                
                if current_value != self.last_value:
                    is_valid, message = self.soc_bot._validate_soc_input(current_value)
                    self.soc_bot._update_input_ui(is_valid, message)
                    self.last_value = current_value
                
                enter_pressed = injected_input.get_attribute('data-enter-pressed') == 'true'
                if enter_pressed:
                    is_valid, message = self.soc_bot._validate_soc_input(current_value)
                    self.soc_bot._update_input_ui(is_valid, message)
                    
                    if is_valid:
                        driver.execute_script("""
                            var input = document.getElementById('InjectedInput');
                            input.removeAttribute('data-enter-pressed');
                            input.disabled = true;
                        """)
                        return True
                    else:
                        self.soc_bot._update_input_ui(False, "❌ Invalid - " + message.split('⚠️ ')[-1])
                        driver.execute_script("""
                            var input = document.getElementById('InjectedInput');
                            input.removeAttribute('data-enter-pressed');
                        """)
                
                return False
            except (NoSuchWindowException, WebDriverException):
                # Browser closed - return True to break the wait
                return True

    def __init__(self):
        super().__init__()
        self.warning_message: str | None = None
    
    def process_password(self, password: str) -> str:
        # Decode password
        encoded_password = password

        try:
            logging.info(f"🔐 Password decoded successfully")
            return base64.b64decode(password.encode()).decode()
        except Exception as e:
            logging.error(f"🔐 Failed to decode password: {str(e)}, using plain text password")
            return encoded_password  # Fallback to plain text
    
    @override
    def load_configuration(self) -> None:
        """SOCBot-specific configuration loading - REQUIRED by base class"""
        self.config_file = 'autoPoints.ini'
        self.warning_message: Optional[str] = None
        self.load_soc_specific_config()

    def load_soc_specific_config(self):
        """Load SOC-specific configuration"""
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.config_file, encoding="utf8")

        # Load ALL configuration including base settings
        self.user_name = config.get('Settings', 'user_name', fallback='xxxxxx')
        self.password = self.process_password(config.get('Settings', 'password', fallback='******'))
        if '\n' in self.password:
            self.password = 'INCORRECT PASSWORD'
        self.base_link = config.get('Settings', 'base_link', fallback='http://eptw.sakhalinenergy.ru/')
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
                           
        # Database configuration
        if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
            try:
                self.db_server = config.get('Database', 'server')
                self.db_password = self.process_password(config.get('Database', 'password'))
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

        if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
            self.SOC_ID_PATTERN = r"^\d{4,8}$"
        else:
            self.SOC_ID_PATTERN = r"^\d{7,8}$"
    
    # SOC-specific methods that now use base class error handling
    def get_SOC_status(self) -> str:    
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
            self.inject_error_message(f"❌ Failed to get SOC status: {str(e)}")
            return ''
    
    def inject_SOC_id_input(self) -> None:
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
          
    def SOC_details_opened_check(self) -> None:
        try:
            self.driver.find_element(By.XPATH, "//h1[contains(@class, 'text-danger') and contains(text(), '404')]")
            logging.error(f"❌ Error 404, probably SOC {self.SOC_id} does not exist")
            self.inject_error_message(f"❌ Error 404, probably SOC {self.SOC_id} does not exist{self.ERROR_MESSAGE_ENDING}.")
        except NoSuchElementException:
            logging.info("✅ Success: no error 404")
    
    def SOC_locked_check(self) -> None:
        try:
            li_locked = self.driver.find_element(By.XPATH, "//li[contains(text(), 'Locked')]")
            logging.error(f"❌ SOC is locked, the script will be terminated: {li_locked.text}")
            self.inject_error_message(f"❌ SOC is locked, the script cannot proceed, close this window: {li_locked.text}")
        except NoSuchElementException:
            logging.info("✅ Success: SOC is not locked")
    
    def access_denied_check(self):
        # check for Access Denied
        try:
            access_denied = self.driver.find_element(By.XPATH, "//h1[contains(text(), 'Access Denied')]")
            logging.error(f"❌ {access_denied.text} - Access denied, probably SOC {self.SOC_id} is archived or in improper state")
            self.inject_error_message(f"❌ Access denied, probably SOC {self.SOC_id} is archived or in improper state{self.ERROR_MESSAGE_ENDING}.")
        except NoSuchElementException:
            logging.info("✅ Success: no access denied issue")

    def login_failed_check(self):
        # check for login issue
        try:
            # check if li tag with parent div[contains(@class, 'text-danger')] contains any text
            self.driver.find_element(By.XPATH, "//div[contains(@class, 'text-danger')]//li[text()]")
            logging.error("❌ Login issue, check the password in ini-file.")
            self.inject_error_message("❌ Login issue, check the password in ini-file, the script cannot proceed, close this window")
        except NoSuchElementException:
            logging.info("✅ Success: no login issue")                
    
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
        try:
            if self.get_current_role() == role:
                logging.info(f"✅ The role is already {role}, no need to switch")
                return
            self.driver.get(self.base_link + r"User/ChangeRole")
            
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
            self.inject_error_message(f"❌ Failed to switch the role{self.ERROR_MESSAGE_ENDING}.")

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
            self.inject_error_message(f"❌ Failed to accept SOC {self.SOC_id} for apply{self.ERROR_MESSAGE_ENDING}.")

    def update_points(self):
        # Kendo API approach failed (becomes too complicated), because the Kendo dropdowns are created dynamically 
        # by the updateOverrideFunctions.onGridDataBound() function, but they're not initialized yet when our script runs.
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
            self.inject_error_message(f"❌ Failed to update some points{self.ERROR_MESSAGE_ENDING}.")
                   
    def request_DB_for_SOC_id(self, SOC_id: str) -> str:
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

    def initialize_and_login(self):
        """Initialize browser and perform login with SOC input"""
        try:
            self.driver.maximize_window()
            self.driver.get(self.base_link)
        except WebDriverException as e:
            logging.error(f"❌ Failed to load {self.base_link} - {e.__class__.__name__}")
            self.inject_error_message(f"❌ Cannot access {self.base_link}. Check network connection.")

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
        
        if self.warning_message:
            self.inject_info_message(self.warning_message, style_addons={'color': 'darkorange'})

        self.inject_SOC_id_input()

    def wait_for_soc_input_and_submit(self):
        """Wait for SOC ID input and submit the form"""
        try:
            # the script will wait for MAX_WAIT_USER_INPUT_DELAY_SECONDS until ****
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(
                self.WaitForSOCInput((By.ID, "InjectedInput"), self)  # Pass self as bot_instance
            )
            
            # If browser closed, exit
            if self._is_browser_closed():
                logging.info("🏁 Browser closed by user during input")
                self.safe_exit()
            
            logging.info(f"✅ Valid SOC id {self.SOC_id} entered - proceeding with authentication")            
        except NoSuchWindowException:
            logging.warning(f"🏁  Browser windows was closed, end of script")
            self.safe_exit()
        except Exception as e:
            logging.error(f"❌ Failed to wait for SOC_id to be entered: {str(e)}")
            self.inject_error_message(f"❌ Failed to wait for SOC_id to be entered{self.ERROR_MESSAGE_ENDING}.")


        try:
            # get the SOC_id from the injected input field and press the submit the form
            raw_soc_id = self.driver.find_element(By.ID, "InjectedInput").get_attribute("value")
            
            # Strip leading zero if SOC ID is 8 digits and starts with 0
            if len(raw_soc_id) == 8 and raw_soc_id.startswith('0'):
                self.SOC_id = raw_soc_id[1:]  # Remove the first character
                logging.info(f"🔧 Stripped leading zero: '{raw_soc_id}' -> '{self.SOC_id}'")
            else:
                self.SOC_id = raw_soc_id

        except Exception as e:
            logging.error(f"❌ Failed to get the SOC_id from the injected field: {str(e)}")
            self.inject_error_message(f"❌ Failed to get SOC_id from the injected field{self.ERROR_MESSAGE_ENDING}.")

        if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
            if len(self.SOC_id) < 7:
                try:
                    full_SOC_id = self.request_DB_for_SOC_id(self.SOC_id)
                    self.SOC_id = full_SOC_id
                    if self.SOC_id is None:
                        raise ValueError("SOC_id cannot be None")
                except Exception as e:
                    logging.error(f"❌ Failed to request DB: {str(e)}")
                    self.inject_error_message(f"❌ Failed to request DB ({str(e)}){self.ERROR_MESSAGE_ENDING}.")                

        try:
            # press the login button - submit the form directly via JavaScript
            # "form?.submit();"" is same as "if (form) form.submit();""
            self.driver.execute_script("""
                var form = document.querySelector('form');
                form?.submit()
            """)
            logging.info("✅ Form submitted successfully")
        except Exception as e:
            logging.error(f"❌ Failed to submit the form: {str(e)}")
            self.inject_error_message(f"❌ Failed to submit the form{self.ERROR_MESSAGE_ENDING}.")

        self.login_failed_check()

    def navigate_to_soc_and_check_status(self):
        """Navigate to SOC details page and check/update status if needed"""
        # open SOC details web page
        SOC_view_base_link = self.base_link + r"Soc/Details/"
        self.driver.get(SOC_view_base_link + self.SOC_id)
        
        self.SOC_details_opened_check()
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
            self.inject_error_message(f'❌ SOC {self.SOC_id} status is "{SOC_status}"{self.ERROR_MESSAGE_ENDING}.', 
                                        locator, style_addons={'width': '100%', 'align': 'center'})

    def process_soc_roles(self):
        """Process SOC for each required role"""
        # for each role (usually OAC, OAV, depends on the values in the ini-file)
        for SOC_role in self.SOC_roles:
            # change the role
            self.switch_role(SOC_role)

            # navigate to Edit Overrides page
            SOC_update_base_link = self.base_link + r"Soc/UpdateOverride/"
            self.driver.get(SOC_update_base_link + self.SOC_id) #example: http://eptw.sakhalinenergy.ru/Soc/UpdateOverride/1458894

            # check if the SOC is locked or access is denied
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
            self.inject_error_message(f"❌ Failed to wait for user input ('Confirm' button){self.ERROR_MESSAGE_ENDING}.")

    def accept_SOC_to_apply(self) -> None:
        """Accept SOC for apply and wait for status change"""
        try:
            old_status = self.get_SOC_status()
            logging.info(f"⏳ Current SOC status: '{old_status}' - proceeding with accept for apply")
                        
            # Wait for Kendo components to initialize
            self.wait_for_kendo_dropdown("ActionsList")
                        
            # Build the action value
            action_value = f'/Soc/TriggerChangeWorkflowState/{self.SOC_id}?trigger=AcceptForApply'
                       
            # Set dropdown value
            set_action_script = """
                var dropdown = $('#ActionsList').data('kendoDropDownList');
                console.log('Dropdown object:', dropdown);
                console.log('Current value:', dropdown.value());
                dropdown.value(arguments[0]);
                dropdown.trigger('change');
                return {
                    success: true,
                    newValue: dropdown.value(),
                    text: dropdown.text()
                };
            """
            result = self.driver.execute_script(set_action_script, action_value)
            logging.info(f"✅ Action value set result: {result}")
            
            # Wait for value to be set with timeout handling
            WebDriverWait(self.driver, 10).until(
                lambda _: self.driver.execute_script(
                    "return $('#ActionsList').data('kendoDropDownList').value() === arguments[0];",
                    action_value
                )
            )
                        
            # Click apply button
            self.click_button((By.ID, 'ApplyActionButton'))
                       
            # Wait for status to actually change with better error handling
            logging.info(f"⏳ Waiting for status to change from '{old_status}'...")
            try:
                WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                    lambda driver: self.get_SOC_status() != old_status
                )
                new_status = self.get_SOC_status()
                logging.info(f"✅ SOC {self.SOC_id} successfully accepted - status changed to '{new_status}'")                                
            except Exception as timeout_error:
                logging.error(f"❌ Status did not change from '{old_status}' within timeout")
                raise timeout_error
                
        except NoSuchWindowException:
            logging.warning(f"🏁  Browser window was closed, end of script")
            self.safe_exit()
        except Exception as e:
            logging.error(f"❌ Failed to accept SOC {self.SOC_id} for apply: {str(e)}")
            self.inject_error_message(f"❌ Failed to accept SOC {self.SOC_id} for apply{self.ERROR_MESSAGE_ENDING}.")

    def run_automation(self):
        """Main automation workflow"""
        self.initialize_and_login()
        self.wait_for_soc_input_and_submit()
        self.navigate_to_soc_and_check_status()
        self.process_soc_roles()
        self.driver.quit()

if __name__ == "__main__":        
    bot = SOCBot()
    bot.run_automation()