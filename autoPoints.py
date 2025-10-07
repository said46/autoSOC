from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
import ctypes

from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoSuchWindowException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

import time
import logging
import configparser
import re
import sys

import colorama
from colorama import Fore, Back, Style

from autoDB import SQLQueryDirect

colorama.init()

class ColoredFormatter(logging.Formatter):
    def format(self, record):
        record.msg = f"{Fore.RED}{record.msg}{Style.RESET_ALL}"
        return super().format(record)

def setup_logging():
    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Clear any existing handlers (optional, but safe)
    if logger.hasHandlers():
        logger.handlers.clear()

    # --- File Handler ---
    log_filename = __file__[__file__.rfind("\\")+1:-3] + ".log"
    file_handler = logging.FileHandler(log_filename, encoding='utf-8', mode='w')
    format_string = "%(asctime)s\tline: %(lineno)d\tfunction: %(funcName)s ---> %(message)s"    
    file_formatter = logging.Formatter(format_string)
    if sys.stdout.isatty():
        # if in TTY use ColoredFormatter
        console_formatter = ColoredFormatter(format_string)
        print("👆 TTY detected")
    else:
        # otherwise use plain Formatter
        console_formatter = logging.Formatter(format_string)
        print("👆 TTY is not detected")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # --- Console Handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

def message_box(title, text, style):
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)

#  Styles:
#  0 : OK *** #  1 : OK | Cancel *** 2 : Abort | Retry | Ignore *** 3 : Yes | No | Cancel ***  
# 4 : Yes | No *** 5 : Retry | Cancel *** 6 : Cancel | Try Again | Continue

class SOCBot:
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
                logging.info(f"{str(e)}")
                return False

    def __init__(self):
        setup_logging()
         
        self.setup_global_exception_handler()
        
        # Use ConfigParser without interpolation
        config = configparser.ConfigParser(interpolation=None)
        config_file = config.read('autoPoints.ini', encoding="utf8")

        if not config_file:
            logging.warning("⚠️  Config file 'autoPoints.ini' not found. Using default values.")
        
        self.user_name = config.get('Settings', 'user_name', fallback='xxxxxx')
        self.password = config.get('Settings', 'password', fallback='******')

        self.MAX_WAIT_USER_INPUT_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_USER_INPUT_DELAY_SECONDS', fallback=300)
        self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_PAGE_LOAD_DELAY_SECONDS', fallback=30)
        self.SOC_id = config.get('Settings', 'SOC_id', fallback='')
        self.SOC_roles = config.get('Roles', 'SOC_roles', fallback='OAC,OAV').split(',')
        self.base_link = config.get('Settings', 'base_link', fallback='http://eptw.sakhalinenergy.ru/')
        self.good_statuses = config.get(
            'Statuses',
            'good_statuses', 
            fallback='принято для установки-запрошено для удаления-установлено, не подтверждено-удалено, не подтверждено').split('-')        
        self.SOC_status_approved_for_apply = config.get('Statuses', 'SOC_status_approved_for_apply', fallback='одобрено для установки')
        sql_template = config.get('SQL', 'SOC_query', fallback="").strip(' \n\r\t')
        self.SQL_template = sql_template
        # check if SQL starts with SELECT to prevent undesirable changes in the database
        if sql_template and sql_template.strip().lower().startswith('select'):
            self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = config.getboolean('Settings', 'CONNECT_TO_DB_FOR_PARTIAL_SOC_ID', fallback=False)
        else:
            self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
            logging.warning("⚠️  SQL query in ini-file doesn't start with SELECT or is empty, use of database is off")
        
        if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
            self.SOC_ID_PATTERN = r"^\d{4,8}\+$"
        else:
            self.SOC_ID_PATTERN = r"^\d{7,8}\+$"

        self.driver = self.create_driver()

    def create_driver(self) -> WebDriver:
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        #options.add_argument("--headless=new")
        options.add_argument("--log-level=3")
        options.add_argument("--silent")
        options.add_argument("--disable-dev-shm-usage")        
        return webdriver.Chrome(options=options)

    def safe_exit(self):
        try:
            time.sleep(2)
            # check if the driver needs to be closed and close it if so
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()   
        except Exception as e:
            logging.error(f"❌ Error during cleanup: {e}")        
        finally:
            sys.exit()
        
    # the function checks the language image on the web page
    # !!! NOT USED !!!
    def switch_lang_if_not_eng(self):
        xpath = "//img[contains(@src,'/images/gb.jpg')]"
        try:
            self.driver.find_element(By.XPATH, xpath)
            # if gb.jpg is on the page, it's English, no actions required
            logging.info("switch_lang_if_not_eng: English! Good!")
            return
        except NoSuchElementException:
            # if gb.jpg is NOT on the page, it's not English, need to switch to it
            logging.info("switch_lang_if_not_eng: Not English! Not Good!")
            # FUTURE: switch to English here
            return

    def click_button(self, locator):
        try:
            element = WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                EC.element_to_be_clickable(locator)
            )
            element.click()
        except Exception as e:
            logging.error(f"❌ Failed to click element with locator {locator}: {e}")
            raise
    
    # the function checks label "Состояние: ***** on the SOC details web page and return the status
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
        
    def setup_global_exception_handler(self):
        """Handle uncaught exceptions to ensure cleanup"""
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                # Don't intercept Ctrl+C
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
                
            logging.error("💥 Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
            self.safe_exit()
    
        sys.excepthook = handle_exception            

    def _is_browser_closed(self):
        """Check if browser window is actually closed"""
        try:
            # Try to get window handles - if it fails, browser is closed
            _ = self.driver.current_url
            return False
        except (WebDriverException, NoSuchWindowException, ConnectionRefusedError, ConnectionAbortedError):
            return True
        except Exception as e:
            # Any other exception, assume browser is gone
            logging.info(f"💥 Browser check exception: {e}")
            return True    

    def _wait_for_browser_to_close(self, timeout=None):
        """Wait for browser close with quick polling"""
        if timeout is None:
            timeout = self.MAX_WAIT_USER_INPUT_DELAY_SECONDS

        try:
            for i in range(timeout):
                if self._is_browser_closed():
                    logging.info("✅ Browser closed by user")
                    break
                if i % 30 == 0:  # Remind every 30 seconds
                    remaining = timeout - i
                    logging.info(f"⏳ Waiting for browser close... ({remaining}s remaining)")
                time.sleep(1)
            else:
                logging.info(f"⏰ {timeout} second timeout reached - forcing exit")
        finally:
            self.safe_exit()    
    
    def inject_error_message(self, msg_text="message is not defined", locator=None):
        """
        Args:
            msg_text: message text
            locator:    1. Tuple (e.g., (By.ID, "my_id")) to locate the element.
                        2. any string, i.e. "absolute positioning"
        """    
       
        try:
            if locator:
                if (isinstance(locator, tuple)):
                    by, value = locator
                    if by == By.XPATH:
                        js_code = """
                            function getElementBy(path) 
                            {
                                return document.evaluate(
                                    path,
                                    document,
                                    null,                    
                                    XPathResult.FIRST_ORDERED_NODE_TYPE, // The desired result type (e.g., FIRST_ORDERED_NODE_TYPE for a single node)
                                    null
                                ).singleNodeValue; // Returns the single node found, or null if none
                            }

                            const parent_element = getElementBy(arguments[1]);
                            const div = document.createElement('div');
                            div.textContent = arguments[0];
                            div.style.fontSize = "16px"
                            div.style.color = "red";
                            div.style.fontWeight = 'bold';
                            div.style.display = 'inline-block';
                            div.style.position = 'relative';
                            div.style.textAlign = 'center';
                            div.style.width = "100%"
                            parent_element.insertBefore(div, parent_element.firstChild);
                        """
                    else:
                        raise NotImplementedError("Only XPath is supported")
                else:
                    raise ValueError("Only tuple is supported")
            
                try:
                    self.driver.execute_script(js_code, msg_text, value)
                except Exception as e:
                    logging.error(f"❌ Failed to inject Error Message with XPATH={value}: {str(e)}")
            else:
                js_code = """
                    const div = document.createElement('div');
                    div.style.cssText = `
                        position: fixed;
                        top: 100px;
                        left: 50%;
                        transform: translateX(-50%);
                        background: white;
                        padding: 10px;
                        border: 2px solid red;
                        z-index: 9999;
                        font-weight: bold;
                        color: red;
                    `;
                    div.textContent = arguments[0];
                    document.body.appendChild(div);
                """
                
                try:
                    self.driver.execute_script(js_code, msg_text)
                except NoSuchWindowException as e:
                    logging.error(f"👆 User closed the browser window.")
                    self.safe_exit()            
                except Exception as e:
                    logging.error(f"❌ Failed to inject Error Message with absolute positioning: {str(e)}")
                    self.safe_exit()
        except Exception as e:
            logging.error(f"❌ Failed to inject error message: {e}")
           

        # Waiting logic
        if self._is_browser_closed():
            logging.info("✅ Browser already closed - instant exit")
            self.safe_exit()
        else:
            logging.info(f"⏳ Browser open - waiting up to {self.MAX_WAIT_USER_INPUT_DELAY_SECONDS} seconds for user to close it")
            self._wait_for_browser_to_close()

    def inject_info_message(self, msg_text="message is not defined", locator=None):
        # after updating all the points with the current role we need to inform the user that he/she should press 
        # the confirm button to proceed. We inject the text information to the left of the buttons using JavaScript

        if locator:
            if (isinstance(locator, tuple)):
                by, value = locator
                if by == By.XPATH:
                    js_code = """
                        function getElementByXpath(path) {
                        return document.evaluate(
                            path, // The XPath expression string
                            document, // The context node for the query (usually the document)
                            null, // A namespace resolver (null for HTML documents or when no namespace prefixes are used)
                            XPathResult.FIRST_ORDERED_NODE_TYPE, // The desired result type (e.g., FIRST_ORDERED_NODE_TYPE for a single node)
                            null // An existing XPathResult to reuse (null for a new one)
                        ).singleNodeValue; // Returns the single node found, or null if none
                        }

                        const xpath = arguments[1];
                        const parent_element = getElementByXpath(xpath) || document.body;
                        const div = document.createElement('div');
                        div.textContent = arguments[0];
                        div.style.color = "lawngreen";
                        div.style.fontWeight = 'bold';
                        div.style.display = 'inline-block';
                        div.style.position = 'relative';
                        div.style.textAlign = 'right';
                        parent_element.insertBefore(div, parent_element.firstChild);
                    """
                else:
                    raise NotImplementedError("Only XPath is supported")
            else:
                raise ValueError("Only tuple is supported")

        try:
            self.driver.execute_script(js_code, msg_text, value)
            logging.info(f"✅ Info message injected successfully")
        except Exception as e:
            logging.error(f"❌ Failed to inject info message: {e}")
            self.inject_error_message(f"❌ Failed to info message, the script cannot proceed, close this window.")
    
    def inject_SOC_id_input(self):
        try:
            # JS code to inject SOC_id input field into the login web page
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
        except Exception as e:
            logging.error(f"❌ Failed to inject SOC_id input field into the login web page: {e}")
            self.inject_error_message(f"❌ Failed to inject SOC_id input field, the script cannot proceed, close this window.")

    def switch_role(self, role: str):
        try:
            # first, open the role change web page
            self.driver.get(self.base_link + r"User/ChangeRole")
            # find the invisible input field used by the web page script to remember the chosen short role (like OAC, OAV)
            input_text = self.driver.find_element(By.ID, 'CurrentRoleName')
            # change the value of the found field to requited value ("OAC", "OAV" and etc.)
            self.driver.execute_script(f'arguments[0].value="{role}"', input_text)
            # press the confirm button
            self.click_button((By.ID, 'ConfirmHeader'))            
            logging.info(f"✅ The role switched to {role} successfully")
        except Exception as e:
            logging.error(f"❌ Failed to switch the role: {e}")
            self.inject_error_message(f"❌ Failed to switch the role, the script cannot proceed, close this window.")

    def SOC_details_opened_check(self):
        # check for 404 error, it takes place when SOC_id does not exist
        try:
            self.driver.find_element(By.XPATH, "//h1[contains(@class, 'text-danger') and contains(text(), '404')]")
            logging.error(f"❌ Error 404, probably SOC {self.SOC_id} does not exist")
            self.inject_error_message(f"❌ Error 404, probably SOC {self.SOC_id} does not exist, the script cannot proceed, close this window.")
        except NoSuchElementException:
            logging.info("✅ Success: no error 404")

    def SOC_locked_check(self):
        # check if the SOC is locked
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
            self.inject_error_message(f"❌ Access denied, probably SOC {self.SOC_id} is archived or in improper state, the script cannot proceed, close this window.")
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

    def accept_SOC_to_apply(self):
        try:
            # accept the SOC for apply, for that
            # find invisible input field used by the web page script to remember the required action    
            input_text = self.driver.find_element(By.ID, 'ActionsList')
            # force the value of this input field to AcceptForApply
            self.driver.execute_script(f'arguments[0].value="/Soc/TriggerChangeWorkflowState/{self.SOC_id}?trigger=AcceptForApply"', input_text)    
            # and click the GO button            
            self.click_button((By.ID, 'ApplyActionButton'))
            logging.info(f"✅ SOC {self.SOC_id} has been accepted for apply successfully")
        except Exception as e:
            logging.error(f"❌ Failed to accept the SOC {self.SOC_id} for apply: {e}")
            self.inject_error_message(f"❌ Failed to accept the SOC {self.SOC_id} for apply, the script cannot proceed, close this window.")

    def update_points(self):
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
                        drop.select_by_index(1)
                        selected_text = drop.first_selected_option.text
                        logging.info(f"✅ Point {point_index} has been updated to {selected_text}")
                except Exception as e:
                    logging.warning(f"⚠️ Точка не обновлена: {str(e)}")
                    message_box("⚠️ Точка не обновлена", f"{str(e)}", 0)
        except NoSuchElementException as e:
            logging.error(f"❌ Failed to update points: {e}")
            self.inject_error_message(f"❌ Failed to update some points, the script cannot proceed, close this window.")
                  
    def request_DB_for_SOC_id(self, SOC_id: str) -> str:
        SQL = self.SQL_template.format(soc_id=SOC_id)

        with SQLQueryDirect(
            server="yuzdc1-v-76096.sakhalin2.ru\\ins02",
            database="DWH_STAGING_IN",
            username="OPF_Master_Tracker", 
            password="22!o6/2o22"
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
        self.driver.get(self.base_link)
        self.driver.maximize_window()

        # login
        self.driver.find_element(By.ID, "UserName").send_keys(self.user_name)
        self.driver.find_element(By.ID, "Password").send_keys(self.password)

        self.inject_SOC_id_input()

        # the script will wait for MAX_WAIT_USER_INPUT_DELAY_SECONDS minutes until the SOC_id in the injected input field corresponds to the template
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
            self.inject_error_message(f"❌ Failed to wait for SOC_id to be entered, the script cannot proceed, close this window.")

        # get the SOC_id from the injected input field and press the login button
        try:    
            # [:-1] removes the last character (+)
            self.SOC_id = self.driver.find_element(By.ID, "InjectedInput").get_attribute("value")[:-1]
        except Exception as e:
            logging.error(f"❌ Failed to get the SOC_id from the injected field: {e}")
            self.inject_error_message(f"❌ Failed to get SOC_id from the injected field, the script cannot proceed, close this window.")

        if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
            if len(self.SOC_id) < 7:
                try:
                    full_SOC_id = self.request_DB_for_SOC_id(self.SOC_id)
                    self.SOC_id = full_SOC_id
                    if self.SOC_id is None:
                        raise ValueError("SOC_id cannot be None")
                except Exception as e:
                    logging.error(f"❌ Failed to request DB: {e}")
                    self.inject_error_message(f"❌ Failed to request DB ({e}), the script cannot proceed, close this window.")                

        try:
            # press login button
            xpath = "//button[@type='submit']"
            self.click_button((By.XPATH, xpath))
        except Exception as e:
            logging.error(f"❌ Failed to press the button: {e}")
            self.inject_error_message(f"❌ Failed to press the button, the script cannot proceed, close this window.")

        self.login_failed_check()
        
        # open SOC details web page
        SOC_view_base_link = self.base_link + r"Soc/Details/"
        self.driver.get(SOC_view_base_link + self.SOC_id) # http://eptw-traning.sakhalinenergy.ru/Soc/Details/1054470

        self.SOC_details_opened_check()
        SOC_status = self.check_SOC_status()

        # if SOC_status == "approved for apply", there is a need to change the role to OAC and accept the SOC for apply
        SOC_status_approved_for_apply = self.SOC_status_approved_for_apply
        if SOC_status == SOC_status_approved_for_apply:
            # switch the role to OAC
            self.switch_role('OAC')
            # open SOC details web page - not sure it is necessary, as it will be opened automatically after changing the role
            self.driver.get(SOC_view_base_link + self.SOC_id)
            self.accept_SOC_to_apply()

            time.sleep(1)
            # xpath = "//label[normalize-space()='Состояние']"
            # WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(EC.presence_of_element_located((By.XPATH, xpath)))

        SOC_status = self.check_SOC_status()

        if SOC_status not in self.good_statuses:
            logging.error(f'❌ SOC {self.SOC_id} status is "{SOC_status}", the script cannot proceed.')
            locator = (By.XPATH, "//div[@id='issowFormContainer']//div[contains(@class, 'user-form')]")
            self.inject_error_message(f'❌ SOC {self.SOC_id} status is "{SOC_status}", the script cannot proceed, close this window.', locator)

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

            #time.sleep(1)
            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(EC.presence_of_element_located((By.ID, "CurrentStateSelect")))
            self.update_points()
            
            msg = '⚠️ Скрипт ожидает нажатия кнопки "Подтвердить".'
            xpath = "//div[@id='bottomWindowButtons']/div"
            self.inject_info_message(msg, (By.XPATH, xpath))
            try:
                # after injecting the text, the script waits for MAX_WAIT_USER_INPUT_DELAY_SECONDS minutes for the web page title to be changed
                # to "СНД - Домашняя страница", to ensure the user pressed the confirm button
                WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(EC.title_is("СНД - Домашняя страница"))
            except NoSuchWindowException as e:
                logging.error(f"User closed the browser window.")
                self.safe_exit()
            except Exception as e:
                logging.error(f"❌ Failed to wait for user input ('Confirm' button): {e}")
                self.inject_error_message(f"❌ Failed to wait for user input ('Confirm' button), the script cannot proceed, close this window.")

        self.driver.quit()


if __name__ == "__main__":        
    bot = SOCBot()
    bot.run_automation()