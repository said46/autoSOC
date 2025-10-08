from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
import ctypes
from typing import Union, TypedDict
from typing_extensions import override

from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoSuchWindowException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

import time
import configparser
import re
import sys

from autoDB import SQLQueryDirect

import logging
from logging_setup import logging_setup

def message_box(title, text, style):
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)

# typed dictionary for additional CSS styles
# total=True if all keys are required
class StyleAddons(TypedDict, total=False):
    color: str
    width: Union[str, None]
    align: str   

class BaseWebBot:
    """Base class for web automation bots with common functionality"""
    
    def __init__(self, config_file='autoPoints.ini'):
        logging_setup() 
        self.setup_global_exception_handler()
        self.config = self.load_config(config_file)
        self.driver = self.create_driver()
        self.default_style_addons = {'color': 'red', 'width': None, 'align': 'center'}
    
    def load_config(self, config_file) -> configparser.ConfigParser:
        """Load configuration from INI file"""
        config = configparser.ConfigParser(interpolation=None)
        config.read(config_file, encoding="utf8")
        
        if not config:
            logging.warning(f"⚠️  Config file '{config_file}' not found. Using default values.")
        
        # Common settings
        self.user_name = config.get('Settings', 'user_name', fallback='xxxxxx')
        self.password = config.get('Settings', 'password', fallback='******')
        self.base_link = config.get('Settings', 'base_link', fallback='http://eptw.sakhalinenergy.ru/')
        self.MAX_WAIT_USER_INPUT_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_USER_INPUT_DELAY_SECONDS', fallback=300)
        self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_PAGE_LOAD_DELAY_SECONDS', fallback=30)

        return config
    
    def create_driver(self) -> WebDriver:
        """Create and configure WebDriver instance"""
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_argument("--log-level=3")
        options.add_argument("--silent")
        options.add_argument("--disable-dev-shm-usage")
        return webdriver.Chrome(options=options)
    
    def safe_exit(self) -> None:
        """Clean up resources and exit safely"""
        try:
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()
        except Exception as e:
            logging.error(f"❌ Error during cleanup: {e}")
        finally:
            sys.exit()
    
    def setup_global_exception_handler(self):
        """Handle uncaught exceptions to ensure cleanup"""
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            logging.error("💥 Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
            self.safe_exit()
        sys.excepthook = handle_exception
    
    def _is_browser_closed(self) -> bool:
        """Check if browser window is actually closed"""
        try:
            _ = self.driver.current_url
            return False
        except Exception:
            return True
    
    def _wait_for_browser_to_close(self, timeout=None) -> None:
        """Wait for browser close with quick polling"""
        if timeout is None:
            timeout = self.MAX_WAIT_USER_INPUT_DELAY_SECONDS
        
        try:
            for i in range(timeout):
                if self._is_browser_closed():
                    logging.info("✅ Browser closed by user")
                    break
                if i % 30 == 0:
                    remaining = timeout - i
                    logging.info(f"⏳ Waiting for browser close... ({remaining}s remaining)")
                time.sleep(1)
            else:
                logging.info(f"⏰ {timeout} second timeout reached - forcing exit")
        finally:
            self.safe_exit()
    
    def click_button(self, locator: tuple[str, str]):
        """Click on element with waiting"""
        try:
            element = WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                EC.element_to_be_clickable(locator)
            )
            element.click()
        except Exception as e:
            logging.error(f"❌ Failed to click element with locator {locator}: {e}")
            raise
        
    def inject_error_message(self, msg_text: str, locator: tuple[str, str] = None, 
                             style_addons: StyleAddons = None) -> None:
        """Inject error message and wait for browser closure"""
        if style_addons is None:
            style_addons = self.default_style_addons
        self._inject_message_with_wait(msg_text, locator, style_addons)
    
    def inject_info_message(self, msg_text: str, locator: tuple[str, str] = None, style_addons: StyleAddons = None) -> None:
        """Inject info message (no waiting for browser closure)"""
        if style_addons is None:
            style_addons = self.default_style_addons        
        self._inject_message(msg_text, locator, style_addons)
    
    def _inject_message_with_wait(self, msg_text: str, locator: tuple[str, str] = None, style_addons: StyleAddons = None) -> None:
        """Inject message and wait for browser closure (for errors)"""
        if style_addons is None:
            style_addons = self.default_style_addons        
        self._inject_message(msg_text, locator, style_addons)
        
        # Wait for browser closure only for error messages
        if self._is_browser_closed():
            logging.info("✅ Browser already closed - instant exit")
            self.safe_exit()
        else:
            logging.info(f"⏳ Browser open - waiting up to {self.MAX_WAIT_USER_INPUT_DELAY_SECONDS} seconds for user to close it")
            self._wait_for_browser_to_close()
    
    def _inject_message(self, msg_text: str, locator: tuple[str, str] = None, style_addons: StyleAddons = None) -> None:
        """Core message injection logic"""
        if style_addons is None:
            style_addons = self.default_style_addons        
        
        try:
            if locator:
                if not isinstance(locator, tuple) or len(locator) != 2:
                    raise ValueError("locator must be a tuple (by, value)")
                
                by, value = locator
                if by != By.XPATH:
                    raise NotImplementedError("Only XPath is supported")
                
                js_code = self._get_injection_js_code(msg_text, value, "relative", style_addons)
            else:
                js_code = self._get_injection_js_code(msg_text, None, "absolute", style_addons)
            
            self.driver.execute_script(js_code)
            logging.info(f"✅ message injected successfully")
            
        except NoSuchWindowException:
            logging.warning("⚠️  Browser window was closed")
            self.safe_exit()
        except Exception as e:
            logging.error(f"❌ Failed to inject message: {e}")
    
    def _get_injection_js_code(self, msg_text: str, xpath: str, position: str, style_addons: StyleAddons = None) -> str:
        """Generate JavaScript code for message injection"""
        
        if style_addons is None:
            style_addons = self.default_style_addons        
        
        # Extract values from style_addons
        color = style_addons.get('color', self.default_style_addons['color'])
        width = style_addons.get('width') # Returns None if key missing
        align = style_addons.get('align', self.default_style_addons['align'])
        
        # Build conditional width CSS
        width_css = f"width: {width};" if width else ""
        
        if position == "absolute":
            return f"""
                const div = document.createElement('div');
                div.style.cssText = `
                    position: fixed;
                    top: 100px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: white;
                    padding: 10px;
                    color: {color};
                    border: 2px solid {color};
                    z-index: 9999;
                    font-weight: bold;
                    text-align: {align};
                    {width_css}
                `;
                div.textContent = `{msg_text}`;
                document.body.appendChild(div);
            """
        else:
            # For relative positioning (with locator)
            return f"""
                function getElementByXpath(path) {{
                    return document.evaluate(
                        path,
                        document,
                        null,
                        XPathResult.FIRST_ORDERED_NODE_TYPE,
                        null
                    ).singleNodeValue;
                }}
                const parent_element = getElementByXpath(`{xpath}`) || document.body;
                const div = document.createElement('div');
                div.style.cssText = `
                    font-size: 14px;
                    color: {color};
                    font-weight: bold;
                    display: inline-block;
                    position: relative;
                    text-align: {align};
                    {width_css}
                `;
                div.textContent = `{msg_text}`;
                parent_element.insertBefore(div, parent_element.firstChild);
            """
        
    def wait_for_kendo_dropdown(self, element_id: str, timeout: int = 10) -> None:
        """Wait for Kendo UI DropDownList to be initialized"""
        WebDriverWait(self.driver, timeout).until(
            lambda _: self.driver.execute_script(
                f"return typeof jQuery !== 'undefined' && jQuery('#{element_id}').data('kendoDropDownList') !== undefined;"
            )
        )
    
class SOCBot(BaseWebBot):    
    """Specialized bot for SOC points automation"""
    FINAL_STATE_DROPDOWN_INDEX = 1
    EXPECTED_HOME_PAGE_TITLE = "СНД - Домашняя страница"
    ERROR_MESSAGE_ENDING = ", the script cannot proceed, close this window."
    
    
    class WaitForValueToMatchTemplate:
        """
        Callable class to wait until an element's value matches a given template.
        
        Args:
            locator: Tuple (e.g., (By.ID, "my_id")) to locate the element.
            template: Expected value template. Can be:
                      - A string (exact match)
                      - A compiled regex pattern (using re.compile)
        """
        def __init__(self, locator, template):
            self.locator = locator
            self.template = template

        def __call__(self, driver):
            try:
                element = driver.find_element(*self.locator)
                value = element.get_attribute("value")  # For input fields
                
                # Handle string template (exact match)
                if isinstance(self.template, str):
                    return value == self.template
                
                # Handle regex template
                elif hasattr(self.template, 'match'):
                    return self.template.match(value) is not None
                
                # Optional: Add other template types (e.g., partial match)
                else:
                    raise ValueError("❌ Template must be a string or compiled regex pattern")
                    
            except NoSuchWindowException as e:
                logging.info(f"⚠️  The browser was closed while waiting for user input")
                # Note: safe_exit is now on SOCBot instance, but this class is standalone
                # We leave this as-is to avoid deeper refactoring per your request
                raise
            except Exception as e:
                # return False if element not found or other errors, log the exception text
                logging.info(f"❌ {str(e)}")
                return False
    
    def __init__(self):
        super().__init__('autoPoints.ini')
        self.warning_message: str | None = None
        self.load_soc_specific_config()        
    
    def load_soc_specific_config(self):
        """Load SOC-specific configuration"""
        config = self.config  # Use the config object from parent
        
        self.SOC_id = config.get('Settings', 'SOC_id', fallback='')
        self.SOC_roles = config.get('Roles', 'SOC_roles', fallback='OAC,OAV').split(',')
        self.good_statuses = config.get(
            'Statuses',
            'good_statuses', 
            fallback='принято для установки-запрошено для удаления-установлено, не подтверждено-удалено, не подтверждено').split('-')
        self.SOC_status_approved_for_apply = config.get('Statuses', 'SOC_status_approved_for_apply', fallback='одобрено для установки')
                      
        self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = config.getboolean('Database', 'CONNECT_TO_DB_FOR_PARTIAL_SOC_ID', fallback=False)
                           
        # Database configuration
        if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
            try:
                self.db_server = config.get('Database', 'server')
                self.db_database = config.get('Database', 'database') 
                self.db_username = config.get('Database', 'username')
                self.db_password = config.get('Database', 'password')
                
                # Validate none are empty
                if not all([self.db_server, self.db_database, self.db_username]):
                    raise configparser.NoOptionError('Database', 'Some database credentials are empty')
                                
                self.SQL_template = config.get('SQL', 'SOC_query', fallback="").strip(' \n\r\t')
                if self.SQL_template and not self.SQL_template.strip().lower().startswith('select'):
                    raise ValueError                        
            
            except (configparser.NoSectionError, configparser.NoOptionError) as e:            
                self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
                self.warning_message = f"⚠️  Database configuration incomplete: {e}. Disabling database features."
                logging.warning(self.warning_message)
            except ValueError as e:
                self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
                self.warning_message = "⚠️  SQL query in ini-file doesn't start with SELECT or is empty. Disabling database features."
                logging.warning(self.warning_message)        

        if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
            self.SOC_ID_PATTERN = r"^\d{4,8}\+$"
            self.warning_message = "✅  Database features are on in ini-file, you can use partial SOC id starting from 4 digits"
        else:
            self.SOC_ID_PATTERN = r"^\d{7,8}\+$"
            self.warning_message = "⚠️  Database features are off in ini-file, use full SOC id."
    
    # SOC-specific methods that now use base class error handling
    def check_SOC_status(self) -> str:    
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
            logging.error(f"❌ Failed to get SOC status: {e}")        
            self.inject_error_message(f"❌ Failed to get SOC status: {e}")
            return ''
    
    def inject_SOC_id_input(self) -> None:
        try:
            js_code = """
                var input = document.createElement('input');
                input.type = 'text';
                input.id = 'InjectedInput';
                input.placeholder = 'Enter SOC number';
                input.className = "form-control control-lg"
                input.style.marginTop = "5px"
                const referenceElement = document.getElementById('Password');
                referenceElement.insertAdjacentElement('afterend', input);
                input.focus();
            """
            self.driver.execute_script(js_code)
        except NoSuchWindowException:
            logging.warning(f"⚠️  Browser windows was closed, end of script")
            self.safe_exit()                 
        except Exception as e:
            logging.error(f"❌ Failed to inject SOC_id input field into the login web page: {e}")
            self.inject_error_message(f"❌ Failed to inject SOC_id input field")
          
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
    
    def switch_role(self, role: str) -> None:
        try:
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
            logging.warning(f"⚠️  Browser windows was closed, end of script")
            self.safe_exit()           
        except Exception as e:
            logging.error(f"❌ Failed to switch the role: {e}")
            self.inject_error_message(f"❌ Failed to switch the role{self.ERROR_MESSAGE_ENDING}.")

    def accept_SOC_to_apply(self) -> None:
        """Accept SOC for apply and wait for status change"""
        try:
            # Get current status before applying
            old_status = self.check_SOC_status()
            logging.info(f"⏳ Current SOC status: '{old_status}' - proceeding with accept for apply")
            
            # Wait for Kendo components to initialize
            self.wait_for_kendo_dropdown("ActionsList")
            
            # Build the action value
            action_value = f'/Soc/TriggerChangeWorkflowState/{self.SOC_id}?trigger=AcceptForApply'
            
            # Set dropdown value
            set_action_script = """
                var dropdown = $('#ActionsList').data('kendoDropDownList');
                dropdown.value(arguments[0]);
                dropdown.trigger('change');
            """
            self.driver.execute_script(set_action_script, action_value)
            
            # Wait for value to be set
            WebDriverWait(self.driver, 10).until(
                lambda _: self.driver.execute_script(
                    "return $('#ActionsList').data('kendoDropDownList').value() === arguments[0];",
                    action_value
                )
            )
            
            # Click apply button
            self.click_button((By.ID, 'ApplyActionButton'))
            
            # Wait for status to actually change
            logging.info(f"⏳ Waiting for status to change from '{old_status}'...")
            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                lambda _: self.check_SOC_status() != old_status
            )
            
            new_status = self.check_SOC_status()
            logging.info(f"✅ SOC {self.SOC_id} successfully accepted - status changed to '{new_status}'")
            
        except NoSuchWindowException:
            logging.warning(f"⚠️  Browser window was closed, end of script")
            self.safe_exit()
        except Exception as e:
            logging.error(f"❌ Failed to accept SOC {self.SOC_id} for apply: {e}")
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
            logging.error(f"❌ Failed to update points: {e}")
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

    def run_automation(self):
        try:
            self.driver.maximize_window()
            self.driver.get(self.base_link)
        except WebDriverException as e:
            logging.error(f"❌ Failed to load {self.base_link} - {e.__class__.__name__}")
            self.inject_error_message(f"❌ Cannot access {self.base_link}. Check network connection.")

        # login
        try:
            self.driver.find_element(By.ID, "UserName").send_keys(self.user_name)
            self.driver.find_element(By.ID, "Password").send_keys(self.password)
        except NoSuchElementException as e:
            logging.error(f"❌ Failed to find 'Username' or 'Password' input fields: {e}")
            self.inject_error_message(f"❌ Failed to find 'Username' or 'Password' input fields {self.ERROR_MESSAGE_ENDING}.")
        
        if self.warning_message:
            self.inject_info_message(self.warning_message, style_addons={'color': 'darkorange'})

        self.inject_SOC_id_input()

        # the script will wait for MAX_WAIT_USER_INPUT_DELAY_SECONDS until the SOC_id in the injected input field corresponds to the template
        pattern = re.compile(self.SOC_ID_PATTERN)
        try:
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(
                self.WaitForValueToMatchTemplate((By.ID, "InjectedInput"), pattern)
            )
        except NoSuchWindowException:
            logging.warning(f"⚠️  Browser windows was closed, end of script")
            self.safe_exit()
        except Exception as e:
            logging.error(f"❌ Failed to wait for SOC_id to be entered: {e}")
            self.inject_error_message(f"❌ Failed to wait for SOC_id to be entered{self.ERROR_MESSAGE_ENDING}.")

        # get the SOC_id from the injected input field and press the login button
        try:    
            # [:-1] removes the last character (+)
            self.SOC_id = self.driver.find_element(By.ID, "InjectedInput").get_attribute("value")[:-1]
        except Exception as e:
            logging.error(f"❌ Failed to get the SOC_id from the injected field: {e}")
            self.inject_error_message(f"❌ Failed to get SOC_id from the injected field{self.ERROR_MESSAGE_ENDING}.")

        if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
            if len(self.SOC_id) < 7:
                try:
                    full_SOC_id = self.request_DB_for_SOC_id(self.SOC_id)
                    self.SOC_id = full_SOC_id
                    if self.SOC_id is None:
                        raise ValueError("SOC_id cannot be None")
                except Exception as e:
                    logging.error(f"❌ Failed to request DB: {e}")
                    self.inject_error_message(f"❌ Failed to request DB ({e}){self.ERROR_MESSAGE_ENDING}.")                

        try:
            # press login button
            xpath = "//button[@type='submit']"
            self.click_button((By.XPATH, xpath))
        except Exception as e:
            logging.error(f"❌ Failed to press the button: {e}")
            self.inject_error_message(f"❌ Failed to press the button{self.ERROR_MESSAGE_ENDING}.")

        self.login_failed_check()
        
        # open SOC details web page
        SOC_view_base_link = self.base_link + r"Soc/Details/"
        self.driver.get(SOC_view_base_link + self.SOC_id) # http://eptw-traning.sakhalinenergy.ru/Soc/Details/1054470

        self.SOC_details_opened_check()
        SOC_status = self.check_SOC_status()

        # if SOC_status == "approved for apply", there is a need to change the role to OAC and accept the SOC for apply
        if SOC_status == self.SOC_status_approved_for_apply:
            # switch the role to OAC
            self.switch_role('OAC')
            # open SOC details web page - not sure it is necessary, as it will be opened automatically after changing the role
            self.driver.get(SOC_view_base_link + self.SOC_id)
            self.accept_SOC_to_apply()
            # Waiting is inside of accept_SOC_to_apply functiion!!!            

        SOC_status = self.check_SOC_status()

        if SOC_status not in self.good_statuses:
            logging.error(f'❌ SOC {self.SOC_id} status is "{SOC_status}", the script cannot proceed.')
            locator = (By.XPATH, "//div[@id='issowFormContainer']//div[contains(@class, 'user-form')]")
            self.inject_error_message(f'❌ SOC {self.SOC_id} status is "{SOC_status}"{self.ERROR_MESSAGE_ENDING}.', 
                                        locator, style_addons={'width': '100%', 'align': 'center'})

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
                logging.error(f"❌ Failed to wait for user input ('Confirm' button): {e}")
                self.inject_error_message(f"❌ Failed to wait for user input ('Confirm' button){self.ERROR_MESSAGE_ENDING}.")

        self.driver.quit()    

if __name__ == "__main__":        
    bot = SOCBot()
    bot.run_automation()
