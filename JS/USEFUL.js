// Get the dropdown and explore its structure
var dd = $('#CurrentRoleName').data('kendoDropDownList');

// See ALL properties and methods
console.dir(dd);

// Explore dataSource deeply
console.log('=== DATA SOURCE EXPLORATION ===');
console.log('Raw data:', dd.dataSource.data());
console.log('Options:', dd.dataSource.options);
console.log('Schema:', dd.dataSource.schema);
console.log('Transport:', dd.dataSource.transport);

// See the actual DOM element Kendo creates
console.log('Kendo wrapper:', dd.wrapper);
console.log('List element:', dd.list);

// THIS IS CRAZY ))
// How Kendo Maintains Consistency:
// javascript
// When you select an item, Kendo does:
dd.value("OAC"); // This automatically:

// 1. Updates data selection
// 2. Updates UI classes (.k-state-selected)  
// 3. Triggers change events
// 4. Ensures consistent: true

// Get ALL Kendo DropDownLists on the page
var allDropdowns = $('[data-role="dropdownlist"]').map(function() {
    return $(this).data('kendoDropDownList');
}).get();

console.log('Found dropdowns:', allDropdowns.length);
allDropdowns.forEach(function(dd, index) {
    console.log(`Dropdown ${index}:`, dd.element.attr('id'));
});