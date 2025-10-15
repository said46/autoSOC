import requests
import json

#############################################################################################
# EXAMPLE OF USAGE
# In your main workflow - discover options first
success, _, _ = self.discover_available_options()

# Then process records with enhanced validation
for record in self.override_records:
    success, error_msg, severity = self.process_type_method_cascade_with_ajax(record)
    if not success:
        logging.error(f"❌ Cascade failed: {error_msg}")
        continue
#############################################################################################      
# DEFINITIONS TO ADD TO SOC_BASE_MIXIN TO TEST - DIRECT AJAX REQUESTS!!!
def _ajax_get(self, endpoint: str, params: dict = None) -> OperationResult:
    """
    Make AJAX GET request to SOC endpoints.
    Returns (success, data_or_error, severity)
    """
    if not self._safe_browser_operation("AJAX request"):
        return False, "Browser closed", ErrorLevel.TERMINAL
        
    try:
        # Get cookies from Selenium for authentication
        selenium_cookies = self.driver.get_cookies()
        session = requests.Session()
        
        # Transfer cookies from Selenium to requests session
        for cookie in selenium_cookies:
            session.cookies.set(cookie['name'], cookie['value'])
        
        # Build full URL
        base_url = self._base_link.rstrip('/')
        full_url = f"{base_url}{endpoint}"
        
        # Make request
        response = session.get(full_url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        logging.info(f"✅ AJAX {endpoint} returned {len(data) if isinstance(data, list) else 'data'}")
        return True, data, None
        
    except Exception as e:
        logging.error(f"❌ AJAX {endpoint} failed: {e}")
        return False, f"AJAX request failed: {e}", ErrorLevel.RECOVERABLE

def get_override_methods(self, type_id: int) -> OperationResult:
    """Get available methods for override type via AJAX"""
    return self._ajax_get("/SOC/GetOverrideMethodsByType", {"overrideTypeId": type_id})

def get_override_states(self, method_id: int) -> OperationResult:
    """Get available states for override method via AJAX"""
    return self._ajax_get("/SOC/GetOverrideStatesByMethod", {"overrideMethodId": method_id})

def smart_find_dropdown_item(self, dropdown_id: str, search_text: str, 
                           fallback_ajax_endpoint: str = None, 
                           ajax_params: dict = None) -> OperationResult:
    """
    Smart dropdown item finder that uses AJAX as fallback.
    Returns (success, item_or_error, severity)
    """
    # First try normal dropdown lookup
    item = self._find_dropdown_item_by_text(dropdown_id, search_text)
    if item:
        return True, item, None
    
    # If not found and AJAX endpoint provided, check server data
    if fallback_ajax_endpoint and ajax_params:
        success, data, severity = self._ajax_get(fallback_ajax_endpoint, ajax_params)
        if success and data:
            # Search in AJAX data
            search_lower = search_text.lower()
            for server_item in data:
                item_text = server_item.get('Text', '')
                if search_lower in item_text.lower():
                    logging.info(f"🔍 Found in server data: {item_text}")
                    return True, server_item, None
            
            # Item doesn't exist on server
            available_items = [item.get('Text', '?') for item in data]
            error_msg = f"Item '{search_text}' not found. Available: {available_items}"
            return False, error_msg, ErrorLevel.RECOVERABLE
    
    return False, f"Item '{search_text}' not found in dropdown", ErrorLevel.RECOVERABLE

def process_type_method_cascade_with_ajax(self, record: dict) -> OperationResult:
    """Enhanced cascade with AJAX data validation"""
    type_value = self.map_override_type(record['type_text'])
    if not type_value:
        return True, None, None
    
    # 1. FIRST check what methods are available via AJAX
    success, methods_data, severity = self.get_override_methods(type_value)
    if success:
        available_methods = [m.get('Text', '') for m in methods_data]
        logging.info(f"📋 Server has {len(available_methods)} methods for type {type_value}: {available_methods}")
        
        # Validate user's method choice exists
        if record['method_text'] and not any(record['method_text'].lower() in m.lower() for m in available_methods):
            return False, f"Method '{record['method_text']}' not available. Options: {available_methods}", ErrorLevel.FATAL
    
    # 2. Now trigger the UI cascade
    if not self.trigger_cascade_change("OverrideTypeId", type_value):
        return False, "Failed to trigger Type cascade", ErrorLevel.FATAL
    
    # 3. Only proceed if method selection is needed and valid
    if record['method_text']:
        # Wait for dropdown to populate
        if not self._wait_for_kendo_widget_ready('OverrideMethodId', 10):
            logging.warning("⚠️ Method dropdown not ready, but we know data exists - continuing")
        
        return self.process_method_selection(record)
    
    return True, None, None

def process_method_selection_with_ajax(self, record: dict) -> OperationResult:
    """Enhanced method selection with AJAX state validation"""
    # Use AJAX to pre-validate and get states
    method_item = self._find_dropdown_item_by_text("OverrideMethodId", record['method_text'])
    if not method_item:
        return False, f"Method not found: {record['method_text']}", ErrorLevel.FATAL
    
    # Check what states are available for this method
    success, states_data, severity = self.get_override_states(method_item['value'])
    if success:
        available_states = [s.get('Text', '') for s in states_data]
        logging.info(f"📋 Server has {len(available_states)} states for method {method_item['value']}: {available_states}")
        
        # Validate user's state choices exist
        if record['applied_state_text'] and not any(record['applied_state_text'].lower() in s.lower() for s in available_states):
            logging.warning(f"⚠️ Applied state '{record['applied_state_text']}' not in server options: {available_states}")
        
        if record['removed_state_text'] and not any(record['removed_state_text'].lower() in s.lower() for s in available_states):
            logging.warning(f"⚠️ Removed state '{record['removed_state_text']}' not in server options: {available_states}")
    
    # Proceed with normal method selection
    if not self.trigger_cascade_change("OverrideMethodId", method_item['value']):
        return False, "Failed to trigger Method cascade", ErrorLevel.FATAL
    
    return True, None, None

def discover_available_options(self) -> OperationResult:
    """Discover all available options for debugging/mapping"""
    logging.info("🔍 Discovering all available cascade options...")
    
    type_mapping = {
        1: "Байпас", 2: "Блокировка", 3: "Форсировка", 
        4: "Логики", 5: "Сигнализации"
    }
    
    for type_id, type_name in type_mapping.items():
        success, methods, severity = self.get_override_methods(type_id)
        if success and methods:
            logging.info(f"\n🎯 {type_name} (ID:{type_id}):")
            for method in methods:
                method_id = method['Value']
                method_name = method['Text']
                
                # Get states for this method
                success, states, severity = self.get_override_states(method_id)
                state_names = [s['Text'] for s in states] if success else ["Unknown"]
                
                logging.info(f"   📝 {method_name} → States: {state_names}")
    
    return True, None, None
