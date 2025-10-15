// Get available methods for override type via AJAX
async function getOverrideMethodsByType(overrideTypeId) {
    try {
        const response = await fetch(`/SOC/GetOverrideMethodsByType?overrideTypeId=${overrideTypeId}`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' },
            credentials: 'include'
        });
        
        const data = await response.json();
        console.log(`✅ Methods for type ${overrideTypeId}:`, data);
        return { success: true, data };
    } catch (error) {
        console.error(`❌ Failed to get methods for type ${overrideTypeId}:`, error);
        return { success: false, error };
    }
}

// Get available states for override method via AJAX
async function getOverrideStatesByMethod(overrideMethodId) {
    try {
        const response = await fetch(`/SOC/GetOverrideStatesByMethod?overrideMethodId=${overrideMethodId}`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' },
            credentials: 'include'
        });
        
        const data = await response.json();
        console.log(`✅ States for method ${overrideMethodId}:`, data);
        return { success: true, data };
    } catch (error) {
        console.error(`❌ Failed to get states for method ${overrideMethodId}:`, error);
        return { success: false, error };
    }
}

// Get method details with states
async function getMethodDetails(method) {
    const statesResult = await getOverrideStatesByMethod(method.Value);
    
    if (statesResult.success) {
        const stateNames = statesResult.data.map(s => s.Text);
        return `   📝 ${method.Text} → States: ${stateNames}`;
    } else {
        return `   📝 ${method.Text} → States: Unknown (failed to fetch)`;
    }
}

// Process a single type and its methods
async function processType(typeId, typeName) {
    const methodsResult = await getOverrideMethodsByType(typeId);
    
    if (!methodsResult.success) {
        console.log(`❌ Failed to get methods for ${typeName}`);
        return;
    }
    
    console.log(`\n🎯 ${typeName} (ID:${typeId}):`);
    
    // Process all methods in parallel for better performance
    const methodDetails = await Promise.all(
        methodsResult.data.map(method => getMethodDetails(method))
    );
    
    methodDetails.forEach(detail => console.log(detail));
}

// Discover all available options for debugging/mapping
async function discoverAllOptions() {
    console.log("🔍 Discovering all available cascade options...");
    
    const typeMapping = {
        1: "Байпас",
        2: "Блокировка", 
        3: "Форсировка",
        4: "Логики",
        5: "Сигнализации"
    };
    
    // Process types sequentially for cleaner output
    for (const [typeId, typeName] of Object.entries(typeMapping)) {
        await processType(parseInt(typeId), typeName);
    }
    
    console.log("✅ Discovery complete!");
}

// Test a specific type with detailed output
async function testType(typeId, typeName = `Type ${typeId}`) {
    console.log(`\n🧪 Testing ${typeName} (ID: ${typeId})...`);
    
    const methodsResult = await getOverrideMethodsByType(typeId);
    
    if (!methodsResult.success) {
        console.log(`❌ No methods found for ${typeName}`);
        return;
    }
    
    console.log(`📋 Found ${methodsResult.data.length} methods:`);
    
    for (const method of methodsResult.data) {
        const statesResult = await getOverrideStatesByMethod(method.Value);
        
        if (statesResult.success) {
            const stateNames = statesResult.data.map(s => s.Text);
            console.log(`   🔸 ${method.Text} → ${stateNames.length} states: ${stateNames.join(', ')}`);
        } else {
            console.log(`   🔸 ${method.Text} → No states available`);
        }
    }
}

// Quick discovery of all types (fast, minimal output)
async function quickDiscover() {
    console.log("🚀 Quick discovery of all types...");
    
    const typeMapping = {
        1: "Байпас", 2: "Блокировка", 3: "Форсировка", 
        4: "Логики", 5: "Сигнализации"
    };
    
    for (const [typeId, typeName] of Object.entries(typeMapping)) {
        const methodsResult = await getOverrideMethodsByType(parseInt(typeId));
        
        if (methodsResult.success) {
            const methodNames = methodsResult.data.map(m => m.Text);
            console.log(`\n${typeName}: ${methodNames.length} methods`);
            console.log(`  ${methodNames.join(', ')}`);
        } else {
            console.log(`\n${typeName}: Failed to load methods`);
        }
    }
}

// 1. Full detailed discovery
await discoverAllOptions();

// 2. Test specific types
await testType(1, "Байпас");
await testType(2, "Блокировка");

// 3. Quick overview
await quickDiscover();

// 4. Individual method checks
const methods = await getOverrideMethodsByType(3);
if (methods.success) {
    const firstMethod = methods.data[0];
    const states = await getOverrideStatesByMethod(firstMethod.Value);
}
