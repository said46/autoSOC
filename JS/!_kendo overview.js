// Summary of Connection Flow:
// User selects a value in OverrideTypeId dropdown
// JavaScript event triggers in SOC.EditOverrides class
// AJAX call to /SOC/GetOverrideMethodsByType?overrideTypeId=SELECTED_VALUE
// Server returns methods applicable to the selected type
// OverrideMethodId dropdown is populated with the returned data
// Similar cascade happens from OverrideMethodId to state dropdowns
// This is a classic cascade dropdown pattern where the options in child dropdowns depend on the selection in parent dropdowns.
// The actual cascade logic is handled in the SOC.EditOverrides class (defined in /js/app.min.js), which likely contains:
// Event handler on OverrideTypeId change
// AJAX call to /SOC/GetOverrideMethodsByType?overrideTypeId=X
// Data binding to populate OverrideMethodId dropdown
// Similar cascade from OverrideMethodId to state dropdowns via /SOC/GetOverrideStatesByMethod



http://eptw.sakhalinenergy.ru/js/app.min.js

var dropdown = $("#dropdown").data("kendoDropDownList");

// Get/set value
dropdown.value();                    // Get current value
dropdown.value("new_value");         // Set value

// Data items
dropdown.dataItem();                 // Get selected data item
dropdown.dataItems();                // Get all data items
dropdown.text();                     // Get displayed text

// Data source
dropdown.dataSource.read();          // Reload data
dropdown.dataSource.filter({});      // Filter data

// Open/close
dropdown.open();                     // Open dropdown
dropdown.close();                    // Close dropdown
dropdown.toggle();                   // Toggle open/close

// Enable/disable
dropdown.enable();                   // Enable control
dropdown.disable();                 // Disable control
dropdown.readonly();                // Set readonly

// Search
dropdown.search("text");            // Search items
dropdown.select();                  // Get selected index

// Typical data item structure
{
    text: "Display Text",    // Displayed in dropdown
    value: "unique_value",   // Actual value
    customField: "data"      // Custom fields
}

// Accessing items
var selectedItem = dropdown.dataItem();
console.log(selectedItem.text);
console.log(selectedItem.value);

// All items
var allItems = dropdown.dataItems();
allItems.forEach(function(item) {
    console.log(item.text, item.value);
});

$("#dropdown").kendoDropDownList({
    dataSource: data,
    change: function(e) {
        console.log("Value changed:", this.value());
        console.log("Selected item:", this.dataItem());
    },
    select: function(e) {
        console.log("Item selected:", e.item);
        console.log("Data item:", e.dataItem);
    },
    open: function(e) {
        console.log("Dropdown opened");
    },
    close: function(e) {
        console.log("Dropdown closed");
    },
    dataBound: function(e) {
        console.log("Data loaded:", this.dataItems().length);
    },
    filtering: function(e) {
        console.log("Filtering:", e.filter);
        // e.preventDefault() to cancel
    }
});

var dropdown = $("#dropdown").data("kendoDropDownList");

// Bind events
dropdown.bind("change", function(e) {
    console.log("Change event:", this.value());
});

dropdown.bind("dataBound", function(e) {
    console.log("Data loaded");
});

$("#parentDropdown").kendoDropDownList({
    change: function() {
        var childDropdown = $("#childDropdown").data("kendoDropDownList");
        childDropdown.dataSource.filter({ 
            parentId: this.value() 
        });
    }
});

$("#dropdown").kendoDropDownList({
    dataSource: {
        transport: {
            read: {
                url: "/api/data",
                type: "GET"
            }
        }
    },
    dataTextField: "name",
    dataValueField: "id",
    delay: 500,                    // Delay before search
    minLength: 3                   // Minimum chars to search
});

var dd = $("#dropdown").data("kendoDropDownList");

// Check if dropdown has value
if (dd.value()) {
    // Do something
}

// Reload and reset
dd.dataSource.read().then(function() {
    dd.value("");  // Clear selection
});

// Find item by value
var item = dd.dataItems().find(function(i) {
    return i.value === "search_value";
});

// Access properties
dd.options.dataTextField;      // Field for display text
dd.options.dataValueField;     // Field for value
dd.options.optionLabel;        // Placeholder text
dd.list;                       // Access the list object
dd.popup;                      // Access popup object