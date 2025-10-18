// ALL dropdown lists on a page
console.log('Kendo DropDown IDs:', $('[data-role="dropdownlist"]').map(function() {
    return $(this).attr('id') || 'No ID';
}).get());

// events into console
const dd_id = 'CurrentRoleName';
events = $._data($(`#${dd_id}`)[0], 'events');
//console.log(JSON.stringify(events, null, 2));


//  all kendoDropDownList events with handlers, inspect in DevTools:
// 0 -> handler -> [[FunctionLocation]], it will be a clickable 
// link like app.min.js?v=duA3KX0…tuzfTaqxjOihlwNUc:1
window.dropdownHandlers = $('select, input').map(function() {
    const kendoDropdown = $(this).data('kendoDropDownList');
    if (kendoDropdown) {
        const jqueryEvents = $._data(this, 'events');
        if (jqueryEvents && jqueryEvents.change) {
            return {
                element: this,
                elementId: this.id,
                handler: jqueryEvents.change[0].handler
            };
        }
    }
    return null;
}).get().filter(Boolean);