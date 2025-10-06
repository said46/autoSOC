def inject_error_message(self, msg_text="message is not defined", locator=None):
    """Fast exit - if browser is open, wait briefly; if closed, exit immediately"""
    try:
        # ... your existing injection code ...
    except Exception as e:
        logging.error(f"❌ Failed to inject error message: {e}")
    
    # Smart waiting logic
    if self._is_browser_closed():
        logging.info("✅ Browser already closed - instant exit")
        self.safe_exit()
    else:
        logging.info("👆 Browser open - waiting up to 30 seconds for user to close it")
        self._wait_for_browser_close_quick()

def _wait_for_browser_close_quick(self, timeout=30):
    """Wait for browser close with quick polling"""
    try:
        for i in range(timeout):
            if self._is_browser_closed():
                logging.info("✅ Browser closed by user")
                break
            if i % 5 == 0:  # Remind every 5 seconds
                remaining = timeout - i
                logging.info(f"⏳ Waiting for browser close... ({remaining}s remaining)")
            time.sleep(1)
        else:
            logging.info(f"⏰ {timeout} second timeout reached - forcing exit")
    finally:
        self.safe_exit()