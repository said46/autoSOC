events = $._data($('#OverrideMethodId')[0], 'events');

// Find the Correct URL by Monitoring Network
// First, open browser Network tab, then trigger a type change manually
// Then run this to see what URLs are being called:

// Monitor all AJAX requests temporarily
$(document).ajaxComplete(function(event, xhr, settings) {
    console.log("🔍 AJAX Call:", settings.url, "Method:", settings.type);
    if (settings.type === 'GET' && settings.url.includes('Override')) {
        console.log("📌 Possible cascade URL:", settings.url);
    }
});

// Type Changed → Call /SOC/GetOverrideMethodsByType?overrideTypeId=X
// Method Changed → Call /SOC/GetOverrideStatesByMethod?overrideMethodId=Y
