from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
import ctypes
from typing import Union, TypedDict
from abc import abstractmethod

from selenium.common.exceptions import (NoSuchWindowException, WebDriverException)
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

import time
import sys

import logging
from logging_setup import logging_setup


def message_box(title, text, style):
    """Display a Windows message box using ctypes"""
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)


# Typed dictionary for additional CSS styles in message injection
# total=False makes all keys optional
class StyleAddons(TypedDict, total=False):
    color: str
    width: Union[str, None]
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
        self.driver = self.create_driver()
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
        if self.driver:
            self.driver.quit()  # Clean up existing driver
        self.driver = driver    
    
    def use_existing_session(self, driver, soc_id: str = None) -> None:
        """
        Use an existing browser session instead of creating a new one.
        
        Args:
            driver: Existing WebDriver instance
            soc_id: Pre-obtained SOC ID (optional)
        """
        if self.driver and self.driver != driver:
            self.driver.quit()  # Clean up existing driver if different
        
        self.driver = driver
        self.session_reused = True
        
        if soc_id:
            self.SOC_id = soc_id
            logging.info(f"✅ Using existing session with SOC ID: {soc_id}")
        else:
            logging.info("✅ Using existing browser session")

    def safe_exit(self) -> None:
        """Clean up resources and exit safely, ensuring WebDriver is properly closed."""
        try:
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()
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
    
    def navigate_to_base(self) -> None:
        """Navigate to the base URL defined by child classes, maximizing the browser window."""
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
        except Exception:
            return True
    
    def _wait_for_browser_to_close(self, timeout=None) -> None:
        """
        Wait for the browser to be closed by the user with periodic status updates.
        
        Args:
            timeout: Maximum time to wait in seconds (defaults to MAX_WAIT_USER_INPUT_DELAY_SECONDS)
        """
        if timeout is None:
            timeout = self.MAX_WAIT_USER_INPUT_DELAY_SECONDS
        
        try:
            for i in range(timeout):
                if self._is_browser_closed():
                    logging.info("✅ Browser closed by user")
                    break
                # Log status every 30 seconds to avoid spam
                if i % 30 == 0:
                    remaining = timeout - i
                    logging.info(f"⏳ Waiting for browser close... ({remaining}s remaining)")
                time.sleep(1)
            else:
                logging.info(f"⏰ {timeout} second timeout reached - forcing exit")
        finally:
            self.safe_exit()
    
    # ===== ELEMENT INTERACTION METHODS =====
    
    def click_button(self, locator: tuple[str, str]):
        """
        Click on a web element with explicit waiting for it to be clickable.
        
        Args:
            locator: Tuple of (By strategy, locator value) e.g., (By.ID, "submit-button")
            
        Raises:
            Exception: If element is not found or not clickable within timeout
        """
        try:
            element = WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                EC.element_to_be_clickable(locator)
            )
            element.click()
        except Exception as e:
            logging.error(f"❌ Failed to click element with locator {locator}: {str(e)}")
            raise
    
    def wait_for_kendo_dropdown(self, element_id: str, timeout: int = 10) -> None:
        """
        Wait for a Kendo UI DropDownList to be fully initialized and ready.
        
        Args:
            element_id: HTML ID of the Kendo dropdown element
            timeout: Maximum time to wait in seconds
        """
        WebDriverWait(self.driver, timeout).until(
            lambda _: self.driver.execute_script(
                f"return typeof jQuery !== 'undefined' && jQuery('#{element_id}').data('kendoDropDownList') !== undefined;"
            )
        )
    
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
        if style_addons is None:
            style_addons = self.default_style_addons        
        self._inject_message(msg_text, locator, style_addons)
    
    def _inject_message_with_wait(self, msg_text: str, locator: tuple[str, str] = None, 
                                 style_addons: StyleAddons = None) -> None:
        """
        Internal method to inject message and wait for browser closure.
        
        Used for error scenarios where user intervention is required.
        """
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
    
    def _inject_message(self, msg_text: str, locator: tuple[str, str] = None, 
                       style_addons: StyleAddons = None) -> None:
        """
        Core message injection logic using JavaScript execution.
        
        Args:
            msg_text: The message text to inject
            locator: Optional tuple for relative positioning
            style_addons: Optional CSS style customization
        """
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
                div.textContent = `{msg_text}`;
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