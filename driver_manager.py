# driver_manager.py
import logging
from selenium.webdriver.chrome.webdriver import WebDriver

class DriverManager:
    """
    Singleton class to manage WebDriver instance across all bot classes.
    Ensures only one driver instance exists during the application lifecycle.
    
    Singleton Pattern Explanation:
    - Only one instance of this class can exist in the entire application
    - Provides global access point to the WebDriver instance
    - Prevents multiple browser windows from being created accidentally
    - Centralizes driver lifecycle management
    """
    
    # Class-level variables (shared across all instances)
    _instance = None    # Stores the single instance of DriverManager
    _driver = None      # Stores the actual WebDriver instance
    
    def __new__(cls):
        """
        Override __new__ to control instance creation.
        This is the core of the Singleton pattern.
        
        Returns:
            DriverManager: The single instance of this class
        """
        if cls._instance is None:
            # First time: create the single instance
            cls._instance = super(DriverManager, cls).__new__(cls)
            logging.info("🚀 DriverManager singleton created")
        # Always return the same instance
        return cls._instance
    
    @classmethod
    def set_driver(cls, driver: WebDriver) -> None:
        """
        Set the WebDriver instance for the entire application.
        
        Args:
            driver: WebDriver instance to be managed
            
        Behavior:
            - If no driver exists: stores the new driver
            - If different driver exists: quits old one, stores new one
            - If same driver exists: no action needed
        """
        if cls._driver is not None and cls._driver != driver:
            # Safety check: avoid memory leaks from orphaned drivers
            logging.warning("⚠️ Replacing existing driver instance")
            try:
                cls._driver.quit()  # Clean up the old driver
            except Exception as e:
                logging.warning(f"⚠️ Could not quit old driver: {e}")
                # Continue anyway - we're replacing it
        
        cls._driver = driver
        logging.info("✅ Driver set in DriverManager")
    
    @classmethod
    def get_driver(cls) -> WebDriver:
        """
        Get the WebDriver instance.
        
        Returns:
            WebDriver: The managed driver instance
            
        Raises:
            RuntimeError: If driver hasn't been set yet
        """
        if cls._driver is None:
            # Prevent NullPointerException-like errors
            raise RuntimeError("Driver not initialized. Call set_driver() first.")
        return cls._driver
    
    @classmethod
    def quit_driver(cls) -> None:
        """
        Safely quit the WebDriver instance.
        
        Features:
            - Exception-safe: won't crash if driver is already closed
            - Null-safe: handles case where driver was never set
            - Idempotent: can be called multiple times safely
        """
        if cls._driver is not None:
            try:
                cls._driver.quit()
                logging.info("✅ Driver quit successfully")
            except Exception as e:
                # Log but don't crash - driver might be already closed
                logging.error(f"❌ Error quitting driver: {e}")
            finally:
                # Always clear the reference to prevent reuse of closed driver
                cls._driver = None
    
    @classmethod
    def is_driver_set(cls) -> bool:
        """
        Check if driver is initialized and ready to use.
        
        Returns:
            bool: True if driver exists and can be used
        """
        return cls._driver is not None