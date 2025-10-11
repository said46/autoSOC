// Kendo UI Monitor Script for DevTools Console
// Paste this in browser console to monitor Kendo dropdown activities

(function() {
    'use strict';
    
    console.log('🔍 Kendo UI Monitor Started...');
    
    // Store original methods to monitor
    const originalDataSourceRead = window.kendo.data.DataSource.prototype.read;
    const originalDropDownListValue = window.kendo.ui.DropDownList.prototype.value;
    const originalDropDownListTrigger = window.kendo.ui.DropDownList.prototype.trigger;
    
    // Monitor DataSource.read() calls
    window.kendo.data.DataSource.prototype.read = function() {
        const stack = new Error().stack;
        console.group('📡 Kendo DataSource.read()');
        console.log('DataSource:', this);
        console.log('Options:', arguments[0]);
        console.log('Stack:', stack);
        console.groupEnd();
        
        return originalDataSourceRead.apply(this, arguments);
    };
    
    // Monitor DropDownList value changes
    window.kendo.ui.DropDownList.prototype.value = function(value) {
        console.group('🎯 Kendo DropDownList.value()');
        console.log('Element:', this.element.attr('id'));
        console.log('New Value:', value);
        console.log('Current Value:', this._value);
        console.log('Data Items:', this.dataItems().length);
        console.groupEnd();
        
        return originalDropDownListValue.apply(this, arguments);
    };
    
    // Monitor DropDownList events
    window.kendo.ui.DropDownList.prototype.trigger = function(eventName, eventData) {
        console.group('⚡ Kendo DropDownList.trigger()');
        console.log('Element:', this.element.attr('id'));
        console.log('Event:', eventName);
        console.log('Event Data:', eventData);
        console.groupEnd();
        
        return originalDropDownListTrigger.apply(this, arguments);
    };
    
    // Monitor AJAX requests
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        console.group('🌐 Fetch Request');
        console.log('URL:', args[0]);
        console.log('Options:', args[1]);
        console.groupEnd();
        
        return originalFetch.apply(this, args).then(response => {
            console.group('🌐 Fetch Response');
            console.log('URL:', args[0]);
            console.log('Status:', response.status);
            response.clone().text().then(text => {
                console.log('Response Preview:', text.substring(0, 200));
            });
            console.groupEnd();
            return response;
        });
    };
    
    // Monitor jQuery AJAX requests
    if (window.jQuery) {
        const originalAjax = jQuery.ajax;
        jQuery.ajax = function(...args) {
            console.group('🔄 jQuery AJAX Request');
            console.log('URL:', args[0]?.url || args[0]);
            console.log('Data:', args[0]?.data);
            console.log('Type:', args[0]?.type || 'GET');
            console.groupEnd();
            
            return originalAjax.apply(this, args).done(function(data, textStatus, jqXHR) {
                console.group('🔄 jQuery AJAX Response');
                console.log('URL:', jqXHR.responseURL);
                console.log('Status:', jqXHR.status);
                console.log('Data Preview:', typeof data === 'string' ? data.substring(0, 200) : data);
                console.groupEnd();
            });
        };
    }
    
    // Utility function to check dropdown status
    window.checkKendoDropdowns = function() {
        console.group('📊 Kendo Dropdown Status Report');
        
        const dropdownIds = [
            'OverrideTypeId', 'OverrideMethodId', 
            'OverrideAppliedStateId', 'OverrideRemovedStateId'
        ];
        
        dropdownIds.forEach(id => {
            const dropdown = jQuery('#' + id).data('kendoDropDownList');
            if (dropdown) {
                console.group('📋 ' + id);
                console.log('Exists:', true);
                console.log('Value:', dropdown.value());
                console.log('Data Items:', dropdown.dataItems().length);
                console.log('DataSource:', dropdown.dataSource);
                console.log('Enabled:', !dropdown.element.is(':disabled'));
                console.log('Pending Requests:', dropdown.dataSource?._pendingRequests);
                console.groupEnd();
            } else {
                console.log('❌ ' + id + ': Not found or not initialized');
            }
        });
        
        console.groupEnd();
    };
    
    // Utility to trigger dropdown data load
    window.triggerDropdownLoad = function(dropdownId) {
        const dropdown = jQuery('#' + dropdownId).data('kendoDropDownList');
        if (dropdown && dropdown.dataSource) {
            console.log('🚀 Triggering data load for:', dropdownId);
            dropdown.dataSource.read();
            return true;
        } else {
            console.log('❌ Cannot trigger load for:', dropdownId);
            return false;
        }
    };
    
    // Utility to simulate change event
    window.triggerChangeEvent = function(dropdownId) {
        const dropdown = jQuery('#' + dropdownId).data('kendoDropDownList');
        if (dropdown) {
            console.log('⚡ Triggering change event for:', dropdownId);
            dropdown.trigger('change');
            return true;
        } else {
            console.log('❌ Cannot trigger change for:', dropdownId);
            return false;
        }
    };
    
    console.log('✅ Kendo UI Monitor Active!');
    console.log('Available commands:');
    console.log('• checkKendoDropdowns() - Check all dropdown status');
    console.log('• triggerDropdownLoad("OverrideMethodId") - Force data load');
    console.log('• triggerChangeEvent("OverrideTypeId") - Trigger change event');
    
})();