# base_web_bot.py
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
import ctypes
from typing import TypedDict
from abc import abstractmethod

from selenium.common.exceptions import (NoSuchWindowException, WebDriverException, TimeoutException)
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

import time
import sys

import logging
from logging_setup import logging_setup
from driver_manager import DriverManager

def message_box(title, text, style):
    """Display a Windows message box using ctypes"""
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)

# Typed dictionary for additional CSS styles in message injection
class StyleAddons(TypedDict, total=False):
    color: str
    width: str | None
    align: str


class BaseWebBot:
    """
    Base class for web automation bots with user-centric design.
    
    Core Principles:
    1. Browser window NEVER closes without user intervention
    2. User can close browser AT ANY TIME - scripts must handle this gracefully
    3. All user communication happens through HTML message injection
    4. Logging is for developers, messages are for users
    5. Users control the workflow pace through interactive pauses
    """

    def __init__(self):
        """Initialize the web bot with logging, exception handling, and WebDriver setup."""
        logging_setup()
        self.setup_global_exception_handler()

        # Check if driver already exists in singleton
        if DriverManager.is_driver_set():
            self.driver = DriverManager.get_driver()
            logging.info("✅ Reusing existing driver from DriverManager")
        else:
            self.driver = self.create_driver()
            DriverManager.set_driver(self.driver)
            logging.info("✅ New driver created and stored in DriverManager")

        self.default_style_addons = {'color': 'red', 'width': None, 'align': 'center'}
        self.MAX_WAIT_USER_INPUT_DELAY_SECONDS = 300  # Default timeout for user actions
        self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS = 20    # Default timeout for page loads
        self.ERROR_MESSAGE_ENDING = ", the script cannot proceed, close this window."
    
    # ===== CORE WEBDRIVER MANAGEMENT =====

    def create_driver(self) -> WebDriver:
        """Create and configure a Chrome WebDriver instance with optimized options."""
        options = Options()
        # Suppress unnecessary logging and errors to keep console clean
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_argument("--log-level=3")  # Only fatal errors
        options.add_argument("--silent")  # Suppress console output
        options.add_argument("--disable-dev-shm-usage")  # Prevent shared memory issues
        return webdriver.Chrome(options=options)

    def set_driver(self, driver):
        """Allow external driver injection for session reuse."""
        self.driver = driver

    def safe_exit(self) -> None:
        """
        Clean up resources and exit safely.
        
        IMPORTANT: If browser is still open, it remains under user control.
        If browser was closed by user, we clean up driver resources.
        """
        try:
            if self.is_browser_alive():
                logging.info("🏁 Script execution completed - browser remains open for user")
                # Browser still open - user in control, no driver cleanup needed
            else:
                logging.info("🏁 Browser closed by user - cleaning up driver resources")
                DriverManager.quit_driver()  # Clean up since user already closed browser
                
        except Exception as e:
            logging.error(f"❌ Error during cleanup: {str(e)}")
        finally:
            sys.exit()

    # ===== ABSTRACT PROPERTIES (MUST BE IMPLEMENTED BY CHILD CLASSES) =====

    @property
    @abstractmethod
    def base_link(self) -> str:
        """Child classes MUST define this property to specify the base URL."""
        pass

    # ===== BROWSER STATE MONITORING - CRITICAL FOR USER CLOSURE HANDLING =====

    def is_browser_alive(self) -> bool:
        """
        Check if the browser window is still open and responsive.
        
        Returns:
            bool: True if browser is alive, False if user closed it
        """
        try:
            # This will raise an exception if browser is closed
            _ = self.driver.current_url
            return True
        except (NoSuchWindowException, WebDriverException):
            return False

    def check_browser_alive_or_exit(self, context: str = "") -> None:
        """
        Check if browser is alive. If user closed it, exit gracefully.
        
        This is used in methods that don't return values (void methods)
        where browser closure should terminate the operation.
        """
        if not self.is_browser_alive():
            if context:
                logging.info(f"🏁 Browser closed by user during: {context}")
            else:
                logging.info("🏁 Browser closed by user")
            self.safe_exit()

    def safe_browser_operation(self, operation_name: str) -> bool:
        """
        Safe wrapper for operations that should continue if browser is closed.
        
        Returns:
            bool: True if browser is alive and operation can proceed, 
                  False if user closed browser (operation should stop)
        """
        if not self.is_browser_alive():
            logging.info(f"🏁 Browser closed by user during: {operation_name}")
            return False
        return True

    # ===== NAVIGATION METHODS =====

    def navigate_to_base(self) -> bool:
        """
        Navigate to the base URL defined by child classes.
        
        Returns:
            bool: True if navigation successful, False if browser was closed by user
        """
        if not self.safe_browser_operation("navigate_to_base"):
            return False
            
        try:
            self.driver.maximize_window()
            self.driver.get(self.base_link)
            logging.info(f"✅ Navigated to: {self.base_link}")
            return True
        except WebDriverException as e:
            # Check if browser was closed during navigation
            if not self.is_browser_alive():
                logging.info("🏁 Browser closed by user during navigation")
                return False
                
            logging.error(f"❌ Failed to load {self.base_link} - {e.__class__.__name__}")
            self.inject_error_message(f"❌ Cannot access {self.base_link}. Check network connection.")
            return False

    # ===== EXCEPTION AND ERROR HANDLING =====

    def setup_global_exception_handler(self):
        """Set up a global exception handler to ensure proper cleanup on unexpected errors."""
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                # Allow normal handling of Ctrl+C
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
                
            logging.error("💥 Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
            
            # Check if browser is still alive to show error message
            if self.is_browser_alive():
                error_msg = f"💥 Unexpected error: {exc_value}"
                self.inject_error_message(error_msg)
            else:
                logging.info("🏁 Browser already closed by user during error")
                
            self.safe_exit()
            
        sys.excepthook = handle_exception

    # ===== ELEMENT INTERACTION METHODS WITH BROWSER CLOSURE HANDLING =====

    def click_button(self, locator, timeout: int = 10) -> bool:
        """
        Click button with browser closure handling.
        
        Returns:
            bool: True if click successful, False if failed or browser closed
        """
        if not self.safe_browser_operation("click_button"):
            return False
            
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable(locator)
            )
            element.click()
            logging.info(f"✅ Successfully clicked button: {locator}")
            return True
        except TimeoutException:
            # Check if browser closed during wait
            if not self.is_browser_alive():
                logging.info(f"🏁 Browser closed by user while waiting for button: {locator}")
                return False
            logging.error(f"⏰ Timeout: Button {locator} not clickable after {timeout} seconds")
            return False
        except Exception as e:
            # Check if browser closed during operation
            if not self.is_browser_alive():
                logging.info(f"🏁 Browser closed by user during button click: {locator}")
                return False
            logging.error(f"❌ Error clicking button {locator}: {str(e)}")
            return False

    def _wait_for_element_visibility(self, element_id: str, timeout: int = 5) -> bool:
        """
        Wait for element to become visible with browser closure handling.
        
        Returns:
            bool: True if element visible, False if timeout or browser closed
        """
        if not self.safe_browser_operation("_wait_for_element_visibility"):
            return False
            
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((By.ID, element_id))
            )
            return True
        except TimeoutException:
            # Check if browser closed during wait
            if not self.is_browser_alive():
                logging.info(f"🏁 Browser closed by user while waiting for element: {element_id}")
                return False
            return False
        except Exception as e:
            if not self.is_browser_alive():
                logging.info(f"🏁 Browser closed by user during element visibility check: {element_id}")
                return False
            logging.error(f"❌ Error waiting for element {element_id}: {str(e)}")
            return False

    # ===== MESSAGE INJECTION METHODS WITH BROWSER CLOSURE HANDLING =====

    def inject_error_message(self, msg_text: str, locator: tuple[str, str] = None,
                             style_addons: StyleAddons = None) -> None:
        """
        Inject an error message and wait for browser closure.
        
        Use for fatal errors where the script cannot continue.
        """
        if not self.safe_browser_operation("inject_error_message"):
            return
            
        if style_addons is None:
            style_addons = self.default_style_addons
        msg_text = msg_text + self.ERROR_MESSAGE_ENDING
        self._inject_message_with_wait(msg_text, locator, style_addons)

    def inject_info_message(self, msg_text: str, locator: tuple[str, str] = None,
                           style_addons: StyleAddons = None) -> None:
        """
        Inject an informational message without waiting for browser closure.
        
        Use for non-fatal notifications where the script continues execution.
        """
        if not self.safe_browser_operation("inject_info_message"):
            return
            
        if style_addons is None:
            style_addons = self.default_style_addons
        self._inject_message(msg_text, locator, style_addons)

    def _inject_message_with_wait(self, message: str, element_locator: tuple = None, 
                                style_addons: dict = None, wait_timeout: int = None) -> bool:
        """
        Inject message and wait for browser close, with built-in browser state checking.
        
        Returns:
            bool: True if message injected and browser closed by user,
                  False if browser already closed or timeout
        """
        # Check browser state first
        if not self.is_browser_alive():
            logging.info("ℹ️ Browser already closed - skipping message injection")
            return False
            
        try:
            # Inject the message
            if not self._inject_message(message, element_locator, style_addons):
                return False
                
            # Set default timeout if not provided
            if wait_timeout is None:
                wait_timeout = self.MAX_WAIT_USER_INPUT_DELAY_SECONDS
                
            logging.info(f"⏳ Waiting up to {wait_timeout} seconds for user to close browser...")
            
            # Wait for browser to close with periodic state checks
            return self._wait_for_browser_to_close(wait_timeout)
            
        except Exception as e:
            logging.error(f"❌ Message injection with wait failed: {e}")
            return False

    def _inject_message(self, msg_text: str, locator: tuple[str, str] = None,
                       style_addons: StyleAddons = None) -> bool:
        """
        Core message injection logic using JavaScript execution.
        
        Returns:
            bool: True if message injected successfully, False if failed or browser closed
        """
        if not self.safe_browser_operation("_inject_message"):
            return False
            
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
            logging.info(f"✅ Message injected successfully: {msg_text[:50]}...")
            return True

        except NoSuchWindowException:
            logging.info("🏁 Browser closed by user during message injection")
            return False
        except Exception as e:
            # Check if browser closed during operation
            if not self.is_browser_alive():
                logging.info("🏁 Browser closed by user during message injection")
                return False
            logging.error(f"❌ Failed to inject message: {str(e)}")
            return False

    def _wait_for_browser_to_close(self, timeout: int = 3600) -> bool:
        """
        Wait for browser to be closed by user, with proper error handling.
        
        Returns:
            bool: True if browser closed by user, False if timeout reached
        """
        try:
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                if not self.is_browser_alive():
                    logging.info("✅ Browser closed by user")
                    return True
                time.sleep(1)  # Check every second
                
            logging.info("⏰ Timeout reached - browser still open")
            return False
            
        except Exception as e:
            logging.error(f"❌ Error waiting for browser close: {e}")
            return False

    def _get_injection_js_code(self, msg_text: str, xpath: str, position: str,
                              style_addons: StyleAddons = None) -> str:
        """
        Generate JavaScript code for DOM message injection.
        (This method remains unchanged from your original implementation)
        """
        if style_addons is None:
            style_addons = self.default_style_addons

        color = style_addons.get('color', self.default_style_addons['color'])
        width = style_addons.get('width')
        align = style_addons.get('align', self.default_style_addons['align'])

        import json
        escaped_msg_text = json.dumps(msg_text)[1:-1]
        escaped_xpath = json.dumps(xpath)[1:-1] if xpath is not None else ""

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
                div.textContent = `{escaped_msg_text}`;
                document.body.appendChild(div);
            """
        else:
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
                const parent_element = getElementByXpath(`{escaped_xpath}`) || document.body;
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
                div.textContent = `{escaped_msg_text}`;
                parent_element.insertBefore(div, parent_element.firstChild);
            """
