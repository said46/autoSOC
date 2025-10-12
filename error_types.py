# error_types.py
from enum import Enum

class ErrorLevel(Enum):
    RECOVERABLE = 1
    FATAL = 2
    TERMINAL = 3

# For methods that return (success, error_message, severity)
OperationResult = tuple[bool, str | None, ErrorLevel]

# For methods that return (success, data, error_message, severity)  
DataOperationResult = tuple[bool, any, str | None, ErrorLevel]