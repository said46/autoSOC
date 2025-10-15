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
# total=False makes all keys optional
class StyleAddons(TypedDict, total=False):
    color: str
    width: str | None
    align: str


class BaseWebBot:
    """
    Base class for web automation bots with common functionality.

    This abstract class provides foundational methods for web automation including:
    - WebDriver management and configuration
    - Error handling and exception management
    - Message injection for user feedback
    - Browser state monitoring
    - Common interaction patterns

    Child classes must implement the abstract base_link property.
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
        # Suppress unnecessary logging and errors
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_argument("--log-level=3")  # Only fatal errors
        options.add_argument("--silent")  # Suppress console output
        options.add_argument("--disable-dev-shm-usage")  # Prevent shared memory issues
        return webdriver.Chrome(options=options)

    def set_driver(self, driver):
        """Allow external driver injection for session reuse."""
        # DriverManager handles quitting old driver if necessary
        self.driver = driver

    def safe_exit(self) -> None:
        """Clean up resources and exit safely, ensuring WebDriver is properly closed."""
        try:
            if hasattr(self, 'driver') and self.driver:
                DriverManager.quit_driver()
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

    # ===== NAVIGATION METHODS =====

    def check_browser_alive_or_exit(self, context: str = "") -> None:
        """
        Check if browser is alive. Exit safely if closed.

        Args:
            context: Optional context for logging what operation was interrupted
        """        
        if self.is_browser_alive():
            if context:
                logging.info(f"🏁 Browser closed during: {context}")
            else:
                logging.info("🏁 Browser closed")
            self.safe_exit()


    def navigate_to_base(self) -> None:
        """Navigate to the base URL defined by child classes, maximizing the browser window."""
        # Check browser state before navigation
        self.check_browser_alive_or_exit("navigate_to_base")
            
        try:
            self.driver.maximize_window()
            self.driver.get(self.base_link)  # Uses the abstract property
        except WebDriverException as e:
            logging.error(f"❌ Failed to load {self.base_link} - {e.__class__.__name__}")
            self.inject_error_message(f"❌ Cannot access {self.base_link}. Check network connection.")

    # ===== EXCEPTION AND ERROR HANDLING =====

    def setup_global_exception_handler(self):
        """Set up a global exception handler to ensure proper cleanup on unexpected errors."""
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                # Allow normal handling of Ctrl+C
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            logging.error("💥 Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
            self.safe_exit()
        sys.excepthook = handle_exception

    # ===== BROWSER STATE MONITORING =====

    def _is_browser_closed(self) -> bool:
        """Check if the browser window has been closed by the user."""
        try:
            _ = self.driver.current_url  # Will raise exception if browser is closed
            return False
        except WebDriverException: # More specific exception catch
            return True

    def is_browser_alive(self) -> bool:
        """Public API for browser state checking"""
        return not self._is_browser_closed()

    def check_browser_alive_or_exit(self, context: str = "") -> None:
        """Termination pattern - for void methods"""
        if not self.is_browser_alive():
            logging.info(f"🏁 Browser closed during: {context}")
            self.safe_exit()

    def _wait_for_browser_to_close(self, timeout: int = 3600) -> bool:
        """
        Wait for browser to be closed by user, with proper error handling.
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

    # ===== ELEMENT INTERACTION METHODS =====

    def click_button(self, locator, timeout: int = 10) -> bool:
        """Click button with detailed error reporting"""
        # Check browser state before interaction
        self.check_browser_alive_or_exit("click_button")
            
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable(locator)
            )
            element.click()
            logging.info(f"✅ Successfully clicked button: {locator}")
            return True
        except TimeoutException:
            logging.error(f"⏰ Timeout: Button {locator} not clickable after {timeout} seconds")
            return False
        except Exception as e:
            logging.error(f"❌ Error clicking button {locator}: {str(e)}")
            return False

    # ===== DOM elements readiness =====

    def _wait_for_element_visibility(self, element_id: str, timeout: int = 5) -> bool:
        """Wait for element to become visible."""
        # Check browser state before waiting
        self.check_browser_alive_or_exit("_wait_for_element_visibility")
            
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((By.ID, element_id))
            )
            return True
        except TimeoutException:
            return False
    
    # ===== MESSAGE INJECTION METHODS =====

    def inject_error_message(self, msg_text: str, locator: tuple[str, str] = None,
                             style_addons: StyleAddons = None) -> None:
        """
        Inject an error message and wait for browser closure.

        Use for fatal errors where the script cannot continue.

        Args:
            msg_text: The error message to display
            locator: Optional tuple (By.XPATH, xpath) to position message relative to an element
            style_addons: Optional CSS style overrides
        """
        # Check browser state before message injection
        self.check_browser_alive_or_exit("inject_error_message")
            
        if style_addons is None:
            style_addons = self.default_style_addons
        msg_text = msg_text + self.ERROR_MESSAGE_ENDING
        self._inject_message_with_wait(msg_text, locator, style_addons)

    def inject_info_message(self, msg_text: str, locator: tuple[str, str] = None,
                           style_addons: StyleAddons = None) -> None:
        """
        Inject an informational message without waiting for browser closure.

        Use for non-fatal notifications where the script continues execution.

        Args:
            msg_text: The info message to display
            locator: Optional tuple (By.XPATH, xpath) to position message relative to an element
            style_addons: Optional CSS style overrides
        """
        # Check browser state before message injection
        self.check_browser_alive_or_exit("inject_info_message")
            
        if style_addons is None:
            style_addons = self.default_style_addons
        self._inject_message(msg_text, locator, style_addons)

    def _inject_message_with_wait(self, message: str, element_locator: tuple = None, 
                                style_addons: dict = None, wait_timeout: int = None) -> bool:
        """
        Inject message and wait for browser close, with built-in browser state checking.
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
                
            logging.info(f"⏳ Browser open - waiting up to {wait_timeout} seconds for user to close it")
            
            # Wait for browser to close with periodic state checks
            return self._wait_for_browser_to_close(wait_timeout)
            
        except Exception as e:
            logging.error(f"❌ Message injection with wait failed: {e}")
            return False

    def _inject_message(self, msg_text: str, locator: tuple[str, str] = None,
                       style_addons: StyleAddons = None) -> None:
        """
        Core message injection logic using JavaScript execution.

        Args:
            msg_text: The message text to inject
            locator: Optional tuple for relative positioning
            style_addons: Optional CSS style customization
        """
        # Check browser state before DOM manipulation
        self.check_browser_alive_or_exit("_inject_message")
            
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
            logging.error(f"❌ Failed to inject message: {str(e)}")

    def _get_injection_js_code(self, msg_text: str, xpath: str, position: str,
                              style_addons: StyleAddons = None) -> str:
        """
        Generate JavaScript code for DOM message injection.

        Args:
            msg_text: Text content of the message
            xpath: XPath for relative positioning (if applicable)
            position: "absolute" for fixed positioning, "relative" for element-relative
            style_addons: CSS style customization options

        Returns:
            JavaScript code as string for execution
        """
        if style_addons is None:
            style_addons = self.default_style_addons

        # Extract values from style_addons with defaults
        color = style_addons.get('color', self.default_style_addons['color'])
        width = style_addons.get('width')  # Returns None if key missing
        align = style_addons.get('align', self.default_style_addons['align'])

        # Sanitize msg_text for use in JS string literal (basic escaping)
        # Using repr() and slicing off the quotes is a common way for simple strings.
        # For more complex data, json.dumps(msg_text) is often safer.
        import json
        escaped_msg_text = json.dumps(msg_text)[1:-1] # Remove surrounding quotes from json string

        # Sanitize xpath for use in JS string literal (basic escaping)
        escaped_xpath = json.dumps(xpath)[1:-1] if xpath is not None else ""

        # Build conditional width CSS
        width_css = f"width: {width};" if width else ""

        if position == "absolute":
            # Fixed positioning at top of viewport
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
            # Relative positioning near specified element
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