from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
import ctypes
from typing import Union, TypedDict
from abc import abstractmethod

from selenium.common.exceptions import NoSuchWindowException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

import time
import sys

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
    
    def __init__(self):
        logging_setup() 
        self.setup_global_exception_handler()        
        self.driver = self.create_driver()
        self.default_style_addons = {'color': 'red', 'width': None, 'align': 'center'}
        self.MAX_WAIT_USER_INPUT_DELAY_SECONDS = 300 # default if not redefined in a child
        self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS = 20   # default if not redefined in a child
        self.ERROR_MESSAGE_ENDING = ", the script cannot proceed, close this window."

       # Force child classes to load their configuration
        self.load_configuration()        
    
    @abstractmethod
    def load_configuration(self) -> None:
        """
        Abstract method that child classes MUST implement to load their specific configuration.
        This ensures all bots properly handle their configuration setup.
        """
        pass    
    
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
            logging.error(f"❌ Error during cleanup: {str(e)}")
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
            logging.error(f"❌ Failed to click element with locator {locator}: {str(e)}")
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
            logging.error(f"❌ Failed to inject message: {str(e)}")
    
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
