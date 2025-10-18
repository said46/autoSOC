// Get ALL Kendo DropDownLists on the page
var allDropdowns = $('[data-role=dropdownlist]').map(function() {
    return $(this).data('kendoDropDownList');
}).get();

console.log('Found dropdowns', allDropdowns.length);
allDropdowns.forEach(function(dd, index) {
    console.log(`Dropdown ${index}`, dd.element.attr('id'));
});