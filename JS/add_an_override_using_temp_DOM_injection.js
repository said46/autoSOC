// Pure JavaScript solution - add override to specific certificate
function addOverride(certificateId, overrideData = {}) {
    console.log('🚀 Adding override to certificate:', certificateId);
    
    // Create COMPLETE override structure
    const createNewOverride = (index) => ({
        TagNumber: overrideData.tagNumber || "AUTO-TAG-" + Date.now(),
        Description: overrideData.description || "Автоматическое переопределение",
        OverrideTypeId: (overrideData.typeId || 2).toString(),
        OverrideType: {
            Title: overrideData.typeTitle || "Программная блокировка при тех.обслуживании"
        },
        OverrideMethodId: (overrideData.methodId || 2).toString(),
        OverrideMethod: {
            Title: overrideData.methodTitle || "Установить MOS"
        },
        Comment: overrideData.comment || "",
        OverrideAppliedStateId: (overrideData.appliedStateId || 3).toString(),
        OverrideAppliedState: {
            Title: overrideData.appliedStateTitle || "MOS включен"
        },
        OverrideRemovedStateId: (overrideData.removedStateId || 4).toString(),
        OverrideRemovedState: {
            Title: overrideData.removedStateTitle || "MOS выключен"
        },
        CurrentOverrideStateId: "5",
        CurrentState: {
            Title: "Не применено"
        },
        AdditionalValueAppliedState: overrideData.additionalValue || "",
        OrderId: index,
        OverrideIndex: index,
        SystemOverrideCertificateId: parseInt(certificateId),
        Id: undefined,
        SystemOverrideCertificate: null,
        OverrideTypes: null,
        OverrideMethods: null,
        OverrideAppliedStates: null,
        OverrideRemovedStates: null,
        OverrideCurrentStates: null,
        TypeMethod: `${overrideData.typeTitle || "Программная блокировка при тех.обслуживании"} / ${overrideData.methodTitle || "Установить MOS"}`,
        OverridesJson: null,
        Overrides: [],
        ReturnUrl: null,
        IsUnableToImplement: false,
        UnableToImplementReason: null,
        IsEditable: false,
        AdditionalValueRemovedState: null,
        Title: null
    });
    
    // Create the submission data
    const overrides = [createNewOverride(1)];
    const formData = new FormData();
    
    // Add all required fields
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
    formData.append('OverridesJson', JSON.stringify(overrides));
    formData.append('__RequestVerificationToken', 'dummy-token-' + Date.now());
    
    // Construct the URL
    const baseUrl = 'https://eptw-training.sakhalinenergy.ru';
    const submitUrl = `${baseUrl}/SOC/EditOverrides/${certificateId}`;
    
    console.log('🎯 Submitting to:', submitUrl);
    console.log('✅ New override:', overrides[0]);
    
    // Submit the data
    return fetch(submitUrl, {
        method: 'POST',
        body: formData
    }).then(response => {
        if (response.ok) {
            console.log('✅ Override added successfully to certificate', certificateId);
            return response;
        } else {
            throw new Error(`Server error: ${response.status} ${response.statusText}`);
        }
    }).catch(error => {
        console.error('❌ Error adding override:', error);
        throw error;
    });
}

// ===== USAGE EXAMPLES =====

// Example 1: Simple MOS override
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

// Example 2: Quick minimal override
function addQuickOverride(certificateId) {
    return addOverride(certificateId, {
        tagNumber: "QUICK-" + Math.floor(Math.random() * 1000),
        description: "Быстрое переопределение",
        comment: "Добавлено за секунду"
    });
}

// Example 3: Hardware bypass override
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

// Example 4: Forced value override
function addForcedValue(certificateId) {
    return addOverride(certificateId, {
        tagNumber: "LVL-001",
        description: "Замена уровнемера",
        typeId: 3,
        typeTitle: "Программная форсировка",
        methodId: 4,
        methodTitle: "Принудительно заморожено с фиксированным значением",
        comment: "Калибровка датчика",
        appliedStateId: 12,
        appliedStateTitle: "Форсировано",
        removedStateId: 13,
        removedStateTitle: "Расфорсировано",
        additionalValue: "50%"
    });
}

// Example 5: Add multiple overrides to same certificate
function addMultipleOverrides(certificateId, count = 3) {
    const promises = [];
    for (let i = 1; i <= count; i++) {
        promises.push(
            addOverride(certificateId, {
                tagNumber: `BATCH-${i}-${certificateId}`,
                description: `Пакетное переопределение ${i}`,
                comment: `Добавлено в пакете #${i}`
            })
        );
    }
    return Promise.all(promises);
}

// ===== TEST FUNCTIONS =====

// Test with specific certificate
function testCertificate(certificateId = '1054470') {
    console.log('🧪 Testing certificate:', certificateId);
    return addQuickOverride(certificateId);
}

// Test all override types on certificate
function testAllTypes(certificateId = '1054470') {
    console.log('🧪 Testing all override types on certificate:', certificateId);
    
    const tests = [
        () => addMOSOverride(certificateId),
        () => addHardwareBypass(certificateId),
        () => addForcedValue(certificateId)
    ];
    
    // Execute tests sequentially
    return tests.reduce((promise, testFunc) => {
        return promise.then(() => testFunc());
    }, Promise.resolve());
}

// ===== USAGE INSTRUCTIONS =====
console.log(`
🎯 Pure Override Functions Available:

BASIC:
addOverride(certificateId, data) - Add custom override

EXAMPLES:
1. addQuickOverride('1054470') - Quick override
2. addMOSOverride('1054470') - MOS override  
3. addHardwareBypass('1054470') - Hardware bypass
4. addForcedValue('1054470') - Forced value
5. addMultipleOverrides('1054470', 5) - Multiple overrides

TEST:
testCertificate('1054470') - Test specific certificate
testAllTypes('1054470') - Test all override types

💡 Example: Run testCertificate('1054470') to test!
`);

// Export for extension use
if (typeof window !== 'undefined') {
    window.ePTWOverrideAPI = {
        addOverride,
        addQuickOverride,
        addMOSOverride,
        addHardwareBypass,
        addForcedValue,
        addMultipleOverrides,
        testCertificate,
        testAllTypes
    };
    console.log('✅ Override API available at window.ePTWOverrideAPI');
}