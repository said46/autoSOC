import logging
import sys
import colorama

colorama.init()

class ColoredFormatter(logging.Formatter):
    def __init__(self):
        from colorama import Fore, Style
        self.Fore = Fore
        self.Style = Style
        super().__init__()
    
    def format(self, record):
        record.msg = f"{self.Fore.RED}{record.msg}{self.Style.RESET_ALL}"
        return super().format(record)

def logging_setup():
    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Clear any existing handlers (optional, but safe)
    if logger.hasHandlers():
        logger.handlers.clear()

    # --- File Handler ---
    import __main__
    log_filename = __main__.__file__[__main__.__file__.rfind("\\")+1:-3] + ".log"
    file_handler = logging.FileHandler(log_filename, encoding='utf-8', mode='w')
    format_string = "%(asctime)s\tline: %(lineno)d\tfunction: %(funcName)s ---> %(message)s"    
    file_formatter = logging.Formatter(format_string)
    
    if sys.stdout.isatty():
        # if in TTY use ColoredFormatter
        console_formatter = ColoredFormatter()
        console_formatter._fmt = format_string
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