// working example of changing OverrideTypeId, making OverrideMethodId to bind its dataSet, so it makes it possible next script to change OverrideMethodId
// BUT same is not working with #OverrideTypeId, even though I can see it has items available!!!!!!!!!

const new_value = '3';
var dropdown = $('#OverrideTypeId').data('kendoDropDownList');
if (!dropdown) {
	console.log('Kendo dropdown not found: OverrideTypeId');
}

var oldValue = dropdown.value();
console.log(`old value: ${oldValue}`);
dropdown.value(new_value);

if (oldValue !== new_value) {
	dropdown.trigger('change', {
		sender: dropdown,
		value: new_value,
		oldValue: oldValue
	});
	
var element = $('#OverrideTypeId')[0];
if (element) {
	var domEvent = new Event('change', { bubbles: true });
	element.dispatchEvent(domEvent);
}
}

// Test getting methods for different override types
$.ajax({
    method: "GET",
    url: "/SOC/GetOverrideMethodsByType?overrideTypeId=1", // Try 1, 2, 3, 4, 5
    success: function(data) {
        console.log("✅ Override Methods for Type 1:", data);
        console.log("Number of methods:", data.length);
        
        if (Array.isArray(data)) {
            data.forEach(function(method, index) {
                console.log(`Method ${index + 1}:`, method);
                // Expected format: {Value: 1, Text: "Method Name"}
            });
        }
    },
    error: function(xhr, status, error) {
        console.log("❌ Error:", error, "Status:", xhr.status);
    }
});

// VM7855:11 Method 1: {Id: 1, Title: 'Установить аппаратный байпас', TitleLocalization: 'Установить аппаратный байпас', Code: 0, ShortForm: 'Аппар. байпас', …}
