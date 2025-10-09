# debug_stack.py
import inspect
import time
from functools import wraps

class StackDebugger:
    """
    Simple call stack debugging utility - NO LOGGING INTERFERENCE
    """
    
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.indent_level = 0
    
    def get_call_stack(self, limit=10):
        """
        Get current call stack as list of frame info
        """
        stack = []
        for frame_info in inspect.stack()[1:limit+1]:  # Skip current frame
            frame = frame_info.frame
            # Filter out large objects for readability
            locals_dict = {}
            for k, v in frame.f_locals.items():
                if not k.startswith('_') and not callable(v):
                    # Shorten long values for display
                    str_val = repr(v)
                    if len(str_val) > 50:
                        str_val = str_val[:47] + "..."
                    locals_dict[k] = str_val
            
            stack.append({
                'function': frame_info.function,
                'filename': frame_info.filename.split('\\')[-1],  # Windows paths
                'lineno': frame_info.lineno,
                'locals': locals_dict
            })
        return stack
    
    def print_stack(self, message="Call stack:", limit=8):
        """
        Print current call stack with optional message
        Uses print() to avoid interfering with logging
        """
        if not self.enabled:
            return
            
        stack = self.get_call_stack(limit)
        indent = "  " * self.indent_level
        
        print(f"{indent}🔍 {message}")
        for i, frame in enumerate(stack, 1):
            print(f"{indent}  {i}. {frame['filename']}:{frame['lineno']} - {frame['function']}()")
            if frame['locals']:
                locals_str = ", ".join(f"{k}={v}" for k, v in frame['locals'].items())
                print(f"{indent}     locals: {locals_str}")
        print()  # Empty line for separation
    
    def trace_calls(self, func):
        """
        Decorator to trace function calls - uses print() not logging
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not self.enabled:
                return func(*args, **kwargs)
                
            self.indent_level += 1
            indent = "  " * self.indent_level
            
            # Get class name if method
            class_name = ""
            if args and hasattr(args[0], '__class__'):
                class_name = f"{args[0].__class__.__name__}."
            
            # Use print() to avoid logging interference
            print(f"{indent}▶️  ENTER: {class_name}{func.__name__}()")
            
            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                end_time = time.time()
                
                # Shorten result representation
                result_repr = repr(result)
                if len(result_repr) > 100:
                    result_repr = result_repr[:97] + "..."
                
                print(f"{indent}✅ EXIT: {class_name}{func.__name__}() -> {result_repr} "
                      f"[{end_time - start_time:.3f}s]")
                return result
            except Exception as e:
                print(f"{indent}❌ ERROR: {class_name}{func.__name__}() -> {type(e).__name__}: {str(e)}")
                raise
            finally:
                self.indent_level -= 1
        
        return wrapper
    
    def track_variable(self, var_name, value):
        """
        Track variable changes with stack context - uses print()
        """
        if not self.enabled:
            return
            
        stack = self.get_call_stack(limit=3)
        caller = stack[0] if stack else {'function': 'unknown', 'lineno': 0}
        
        # Shorten long values
        value_repr = repr(value)
        if len(value_repr) > 100:
            value_repr = value_repr[:97] + "..."
        
        print(f"📊 VAR TRACK: {var_name} = {value_repr} "
              f"[in {caller['function']}() at line {caller['lineno']}]")

# Create global instance for easy use
debugger = StackDebugger()

# Convenience functions
def debug_stack(message="Call stack:", limit=8):
    """Quick function to print call stack - uses print()"""
    debugger.print_stack(message, limit)

def trace_calls(func):
    """Quick decorator to trace function calls"""
    return debugger.trace_calls(func)

def track(var_name, value):
    """Quick function to track variable changes"""
    debugger.track_variable(var_name, value)

def enable_debugging():
    """Enable debugging globally"""
    debugger.enabled = True
    print("🐛 Stack debugging ENABLED")

def disable_debugging():
    """Disable debugging globally"""
    debugger.enabled = False
    print("🐛 Stack debugging DISABLED")

# Example usage when run directly
if __name__ == "__main__":
    print("🧪 Stack Debugger Demo - No Logging Interference")
    debug_stack("Current stack in demo")