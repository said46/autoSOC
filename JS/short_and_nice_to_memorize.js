events = $._data($('#OverrideMethodId')[0], 'events');

// Monitor ALL AJAX requests
$(document).ajaxComplete(function(event, xhr, settings) {
    console.log("🔍 AJAX Call:", settings.url, "Method:", settings.type);
});

// Monitor AJAX requests with url containing 'Override'
$(document).ajaxComplete(function(event, xhr, settings) {
    console.log("🔍 AJAX Call:", settings.url, "Method:", settings.type);
    if (settings.type === 'GET' && settings.url.includes('Override')) {
        console.log("📌 Possible cascade URL:", settings.url);
    }
});

// EVEN NICER!!!!!!!!
$(document).ajaxComplete(function(event, xhr, settings) {
    console.log("🔍 AJAX:", settings.url, "Method:", settings.type);
    console.log("   Response:", xhr.responseText); // See actual data returned
    console.log("   Status:", xhr.status); // HTTP status code
});

// Type Changed → Call /SOC/GetOverrideMethodsByType?overrideTypeId=X
// Method Changed → Call /SOC/GetOverrideStatesByMethod?overrideMethodId=Y
