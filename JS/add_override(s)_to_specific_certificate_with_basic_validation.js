/**
 * Pure JavaScript solution - add override(s) to specific certificate
 * Supports both single override and multiple overrides in one submission
 * Uses backend validation for business logic, basic frontend validation for required fields
 */

/**
 * Add one or more overrides to a certificate
 * @param {string} certificateId - The SOC certificate ID to add overrides to
 * @param {Object|Array} overrideData - Single override object or array of override objects
 * @returns {Promise} Promise that resolves when overrides are submitted
 * @throws {Error} If validation fails or server returns error
 */
function addOverride(certificateId, overrideData = {}) {
    console.log('🚀 Adding override(s) to certificate:', certificateId);
    
    // Normalize input: support both single object and array of objects
    const overridesArray = Array.isArray(overrideData) ? overrideData : [overrideData];
    
    console.log(`📦 Processing ${overridesArray.length} override(s)`);
    
    // BASIC VALIDATION - Check each override has required fields
    const validationErrors = [];
    
    overridesArray.forEach((override, index) => {
        const overrideErrors = [];
        
        // Check all required fields are provided
        if (!override.tagNumber) overrideErrors.push('tagNumber is required');
        if (!override.description) overrideErrors.push('description is required');
        if (!override.typeId) overrideErrors.push('typeId is required');
        if (!override.methodId) overrideErrors.push('methodId is required');
        if (!override.appliedStateId) overrideErrors.push('appliedStateId is required');
        if (!override.removedStateId) overrideErrors.push('removedStateId is required');
        
        if (overrideErrors.length > 0) {
            validationErrors.push(`Override ${index + 1}: ${overrideErrors.join(', ')}`);
        }
    });
    
    // Throw error if any validation failures
    if (validationErrors.length > 0) {
        const errorMessage = `Validation failed:\n${validationErrors.join('\n')}`;
        console.error('❌', errorMessage);
        throw new Error(errorMessage);
    }
    
    /**
     * Create override object structure for submission
     * @param {Object} override - Source override data
     * @param {number} index - Override index for ordering
     * @returns {Object} Formatted override object ready for JSON serialization
     */
    const createNewOverride = (override, index) => ({
        // Required fields - validated above
        TagNumber: override.tagNumber,
        Description: override.description,
        OverrideTypeId: override.typeId.toString(),
        OverrideMethodId: override.methodId.toString(),
        OverrideAppliedStateId: override.appliedStateId.toString(),
        OverrideRemovedStateId: override.removedStateId.toString(),
        
        // Optional fields with fallbacks
        Comment: override.comment || "",
        AdditionalValueAppliedState: override.additionalValue || "",
        
        // Optional nested objects
        OverrideType: { Title: override.typeTitle || "" },
        OverrideMethod: { Title: override.methodTitle || "" },
        OverrideAppliedState: { Title: override.appliedStateTitle || "" },
        OverrideRemovedState: { Title: override.removedStateTitle || "" },
        
        // System fields - defaults for new overrides
        CurrentOverrideStateId: "5", // "Не применено"
        CurrentState: { Title: "Не применено" },
        OrderId: index + 1,
        OverrideIndex: index + 1,
        SystemOverrideCertificateId: parseInt(certificateId),
        
        // Critical: ID must be undefined for new overrides
        Id: undefined,
        
        // Null fields for clean submission
        SystemOverrideCertificate: null,
        OverrideTypes: null,
        OverrideMethods: null,
        OverrideAppliedStates: null,
        OverrideRemovedStates: null,
        OverrideCurrentStates: null,
        OverridesJson: null,
        Overrides: [],
        ReturnUrl: null,
        AdditionalValueRemovedState: null,
        Title: null,
        
        // UI fields
        TypeMethod: `${override.typeTitle || ""} / ${override.methodTitle || ""}`.trim(),
        IsUnableToImplement: false,
        UnableToImplementReason: null,
        IsEditable: false
    });
    
    // Create override objects for ALL provided overrides
    const submissionOverrides = overridesArray.map(createNewOverride);
    
    // Prepare form data for submission
    const formData = new FormData();
    
    // Add all required form fields (empty values for hidden fields)
    formData.append('SystemOverrideCertificateId', certificateId);
    formData.append('TagNumber', '');
    formData.append('Description', '');
    formData.append('OverrideTypeId', '');
    formData.append('OverrideMethodId', '');
    formData.append('Comment', '');
    formData.append('OverrideAppliedStateId', '');
    formData.append('AdditionalValueAppliedState', '');
    formData.append('OverrideRemovedStateId', '');
    formData.append('CurrentOverrideStateId', '5');
    
    // Critical: Send ALL overrides as JSON in single field
    formData.append('OverridesJson', JSON.stringify(submissionOverrides));
    formData.append('__RequestVerificationToken', 'dummy-token-' + Date.now());
    
    // Construct submission URL
    const baseUrl = 'https://eptw-training.sakhalinenergy.ru';
    const submitUrl = `${baseUrl}/SOC/EditOverrides/${certificateId}`;
    
    console.log('🎯 Submitting to:', submitUrl);
    console.log('✅ Overrides to be added:', submissionOverrides);
    
    /**
     * Submit overrides to server
     * Backend handles complex business logic validation
     */
    return fetch(submitUrl, {
        method: 'POST',
        body: formData
    }).then(response => {
        if (response.ok) {
            console.log(`✅ ${submissionOverrides.length} override(s) added successfully to certificate ${certificateId}`);
            return response;
        } else {
            throw new Error(`Server error: ${response.status} ${response.statusText}`);
        }
    }).catch(error => {
        console.error('❌ Error adding override(s):', error);
        throw error;
    });
}

// ===== USAGE EXAMPLES =====

/**
 * Add a simple MOS override (Software blocking)
 * @param {string} certificateId - Target certificate ID
 */
function addMOSOverride(certificateId) {
    return addOverride(certificateId, {
        tagNumber: "MOS-TEST-001",
        description: "Тестовое переопределение МОС",
        typeId: 2,
        typeTitle: "Программная блокировка при тех.обслуживании",
        methodId: 2,
        methodTitle: "Установить MOS",
        comment: "Добавлено автоматически через JS",
        appliedStateId: 3,
        appliedStateTitle: "MOS включен",
        removedStateId: 4,
        removedStateTitle: "MOS выключен",
        additionalValue: ""
    });
}

/**
 * Add a hardware bypass override
 * @param {string} certificateId - Target certificate ID
 */
function addHardwareBypass(certificateId) {
    return addOverride(certificateId, {
        tagNumber: "VALVE-001",
        description: "Байпас клапана",
        typeId: 1,
        typeTitle: "Апаратный байпас",
        methodId: 1,
        methodTitle: "Установить аппаратный байпас",
        comment: "Для технического обслуживания",
        appliedStateId: 1,
        appliedStateTitle: "Установлен",
        removedStateId: 2,
        removedStateTitle: "Не установлен",
        additionalValue: ""
    });
}

/**
 * Add multiple overrides in single submission
 * @param {string} certificateId - Target certificate ID
 * @param {number} count - Number of overrides to add
 */
function addMultipleOverrides(certificateId, count = 3) {
    const overrides = [];
    for (let i = 1; i <= count; i++) {
        overrides.push({
            tagNumber: `BATCH-${i}-${certificateId}`,
            description: `Пакетное переопределение ${i}`,
            typeId: 2,
            methodId: 2,
            appliedStateId: 3,
            removedStateId: 4,
            comment: `Добавлено в пакете #${i}`
        });
    }
    return addOverride(certificateId, overrides);
}

// ===== USAGE INSTRUCTIONS =====
console.log(`
🎯 OVERRIDE MANAGEMENT API:

CORE FUNCTION:
addOverride(certificateId, overrideData) - Add one or multiple overrides

USAGE EXAMPLES:
// Single override
addOverride('1054470', {
    tagNumber: "TEST-TAG",
    description: "Test Description",
    typeId: 2, methodId: 2, 
    appliedStateId: 3, removedStateId: 4
});

// Multiple overrides (array)
addOverride('1054470', [
    { tagNumber: "TAG-1", description: "Desc 1", typeId: 2, methodId: 2, appliedStateId: 3, removedStateId: 4 },
    { tagNumber: "TAG-2", description: "Desc 2", typeId: 2, methodId: 2, appliedStateId: 3, removedStateId: 4 }
]);

HELPER FUNCTIONS:
addMOSOverride('1054470') - Add MOS override
addHardwareBypass('1054470') - Add hardware bypass
addMultipleOverrides('1054470', 5) - Add 5 overrides

💡 All complex validation handled by backend - just provide required fields!
`);

// Export for browser console use
if (typeof window !== 'undefined') {
    window.ePTWOverrideAPI = {
        addOverride,
        addMOSOverride,
        addHardwareBypass,
        addMultipleOverrides
    };
    console.log('✅ Override API available at window.ePTWOverrideAPI');
}