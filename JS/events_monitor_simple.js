// Simplified Kendo UI Monitor
(function() {
    'use strict';
    
    console.log('🔍 Kendo Monitor Started');
    
    // Monitor DataSource reads
    const originalRead = window.kendo.data.DataSource.prototype.read;
    window.kendo.data.DataSource.prototype.read = function() {
        console.log('📡 DataSource Read:', this.options?.transport?.read?.url || 'unknown');
        return originalRead.apply(this, arguments);
    };
    
    // Monitor DropDownList value changes
    const originalValue = window.kendo.ui.DropDownList.prototype.value;
    window.kendo.ui.DropDownList.prototype.value = function(value) {
        if (value !== undefined && value !== this._value) {
            console.log('🎯 Dropdown Change:', this.element.attr('id'), '->', value);
        }
        return originalValue.apply(this, arguments);
    };
    
    // Quick status check
    window.checkDropdowns = function() {
        console.group('📊 Dropdown Status');
        ['OverrideTypeId', 'OverrideMethodId', 'OverrideAppliedStateId', 'OverrideRemovedStateId'].forEach(id => {
            const dd = jQuery('#' + id).data('kendoDropDownList');
            console.log(id + ':', dd ? `Value: ${dd.value()}, Items: ${dd.dataItems().length}` : 'Not found');
        });
        console.groupEnd();
    };
    
    console.log('✅ Monitor Active - Use checkDropdowns()');
})();