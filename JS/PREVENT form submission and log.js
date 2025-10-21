// Enhanced interception with FILE DOWNLOAD capability
function interceptOverrideSubmissions() {
    console.log('🔍 INTERCEPTING OVERRIDE SUBMISSIONS...');
    
    const forms = document.querySelectorAll('form');
    forms.forEach((form, index) => {
        console.log(`📋 Form ${index}:`, form.action);
        
        const originalSubmit = form.submit;
        
        form.submit = function() {
            console.log('\n=== 🚀 FORM SUBMIT INTERCEPTED ===');
            
            // Capture ALL form data
            const formData = new FormData(this);
            const captureData = {
                timestamp: new Date().toISOString(),
                action: this.action,
                method: this.method,
                formData: {},
                overrides: [],
                hiddenFields: {}
            };
            
            // Process form data
            for (let [key, value] of formData.entries()) {
                captureData.formData[key] = value;
                
                if (key === 'OverridesJson') {
                    try {
                        captureData.overrides = JSON.parse(value);
                    } catch (e) {
                        captureData.overrides = ['PARSE_ERROR: ' + e.message];
                    }
                }
            }
            
            // Capture hidden fields
            this.querySelectorAll('input[type="hidden"]').forEach(input => {
                captureData.hiddenFields[input.name] = input.value;
            });
            
            // Save to file
            saveCaptureToFile(captureData);
            
            console.log('📁 Data saved to file! Check downloads for override-capture.json');
            console.log('🛑 Submission prevented');
            
            return false;
        };
    });
    
    console.log('✅ Form interception active!');
}

// Save captured data to downloadable file
function saveCaptureToFile(captureData) {
    const dataStr = JSON.stringify(captureData, null, 2);
    const dataBlob = new Blob([dataStr], {type: 'application/json'});
    
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `override-capture-${Date.now()}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

// Function to test our current implementation
function captureOurImplementation() {
    console.log('🎯 CAPTURING OUR CURRENT IMPLEMENTATION...');
    
    const testOverride = {
        tagNumber: "TEST-CAPTURE-001",
        description: "Testing our implementation capture",
        typeId: 2,
        methodId: 2,
        appliedStateId: 3,
        removedStateId: 4,
        comment: "This is from our function"
    };
    
    // Simulate what our function would send
    const ourData = {
        timestamp: new Date().toISOString(),
        source: 'our-implementation',
        overrideData: testOverride,
        generatedOverridesJson: generateTestOverrideJson('1054470', [testOverride])
    };
    
    saveCaptureToFile(ourData);
    console.log('📁 Our implementation data saved to file!');
}

// Helper to generate our OverridesJson for comparison
function generateTestOverrideJson(certificateId, overridesArray) {
    const submissionOverrides = overridesArray.map((override, index) => ({
        TagNumber: override.tagNumber,
        Description: override.description,
        OverrideTypeId: override.typeId.toString(),
        OverrideMethodId: override.methodId.toString(),
        OverrideAppliedStateId: override.appliedStateId.toString(),
        OverrideRemovedStateId: override.removedStateId.toString(),
        Comment: override.comment || "",
        AdditionalValueAppliedState: override.additionalValue || "",
        OverrideType: { Title: override.typeTitle || "" },
        OverrideMethod: { Title: override.methodTitle || "" },
        OverrideAppliedState: { Title: override.appliedStateTitle || "" },
        OverrideRemovedState: { Title: override.removedStateTitle || "" },
        CurrentOverrideStateId: "5",
        CurrentState: { Title: "Не применено" },
        OrderId: index + 1,
        OverrideIndex: index + 1,
        SystemOverrideCertificateId: parseInt(certificateId),
        Id: undefined,
        // ... other fields
    }));
    
    return JSON.stringify(submissionOverrides);
}

// Re-enable form submissions
function allowFormSubmissions() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        delete form.submit;
    });
    console.log('✅ Form submissions re-enabled!');
}

// Auto-run interception
interceptOverrideSubmissions();

console.log(`
🎯 CAPTURE INSTRUCTIONS:

PHASE 1 - CAPTURE WEB APP BEHAVIOR:
1. Add an override manually in the web app UI
2. Fill all fields normally
3. Click "Save" button
4. A JSON file will download with EXACT web app data

PHASE 2 - CAPTURE OUR IMPLEMENTATION:
5. Run: captureOurImplementation()
6. Another JSON file downloads with our data

PHASE 3 - COMPARE:
7. Compare the two JSON files side by side
8. Look for differences in OverridesJson structure

🛑 Submissions are currently BLOCKED
✅ Run allowFormSubmissions() to re-enable normal behavior
`);