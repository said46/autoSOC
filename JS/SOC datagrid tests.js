// =========================================================================
// DATA EXTRACTION WITH DETAILED LOGGING
// =========================================================================

function extractOverridesTableData() {
    console.log("🔍 Starting data extraction from SOC overrides table...");
    
    try {
        console.log("📊 Step 1: Getting Kendo Grid reference");
        var grid = $('#Overrides').data('kendoGrid');
        
        if (!grid) {
            console.error("❌ Grid not found - $('#Overrides').data('kendoGrid') returned null");
            return null;
        }
        
        console.log("✅ Grid reference obtained successfully");
        
        if (!grid.dataSource) {
            console.error("❌ Grid dataSource is null or undefined");
            return null;
        }
        
        console.log("📊 Step 2: Retrieving grid data");
        var data = grid.dataSource.data();
        console.log(`📈 Found ${data.length} data items in grid`);
        
        if (data.length === 0) {
            console.warn("⚠️ No data items found in grid - returning empty result");
            return null;
        }

        // Expected column order for importer (9 columns)
        console.log("📋 Step 3: Setting up column headers");
        var headers = [
            'TagNumber', 'Description', 'OverrideType', 'OverrideMethod', 'Comment',
            'AppliedState', 'AdditionalValueAppliedState', 'RemovedState', 'AdditionalValueRemovedState'
        ];
        console.log("✅ Headers defined:", headers);

        console.log("🔄 Step 4: Processing data rows...");
        var rows = data.map(function(item, index) {
            console.log(`  Processing item ${index + 1}/${data.length}:`, item);
            
            var row = [
                item.TagNumber || '',
                item.Description || '',
                item.OverrideType ? (item.OverrideType.Title || '') : '',
                item.OverrideMethod ? (item.OverrideMethod.Title || '') : '',
                item.Comment || '',
                item.OverrideAppliedState ? (item.OverrideAppliedState.Title || '') : '',
                item.AdditionalValueAppliedState || '',
                item.OverrideRemovedState ? (item.OverrideRemovedState.Title || '') : '',
                item.AdditionalValueRemovedState || ''
            ];
            
            console.log(`  ✅ Row ${index + 1} processed:`, row);
            return row;
        });

        console.log("🎉 Step 5: Data extraction completed successfully");
        console.log(`📊 Final result: ${rows.length} rows with ${headers.length} columns`);
        console.log("📋 Headers:", headers);
        console.log("📄 First row sample:", rows[0]);
        
        return {
            headers: headers,
            rows: rows,
            summary: {
                totalRows: rows.length,
                totalColumns: headers.length,
                timestamp: new Date().toISOString()
            }
        };

    } catch (error) {
        console.error("💥 CRITICAL ERROR during data extraction:", error);
        console.error("Stack trace:", error.stack);
        return {
            error: error.message,
            stack: error.stack,
            timestamp: new Date().toISOString()
        };
    }
}

// =========================================================================
// GRID INSPECTION UTILITIES
// =========================================================================

function inspectGridStructure() {
    console.log("🔍 Inspecting grid structure...");
    
    try {
        var grid = $('#Overrides').data('kendoGrid');
        
        if (!grid) {
            console.error("❌ Grid not found");
            return null;
        }
        
        console.log("📊 Grid basic info:");
        console.log("  - Grid element:", $('#Overrides').length ? "Found" : "Not found");
        console.log("  - Grid object:", typeof grid);
        console.log("  - DataSource:", grid.dataSource ? "Available" : "Missing");
        
        if (grid.dataSource) {
            var data = grid.dataSource.data();
            console.log("  - Data items count:", data.length);
            console.log("  - Data items type:", Array.isArray(data) ? "Array" : typeof data);
            
            if (data.length > 0) {
                console.log("  - First item structure:", Object.keys(data[0]));
                console.log("  - First item sample:", data[0]);
            }
        }
        
        // Check column structure
        var columns = grid.columns || grid.options.columns;
        console.log("  - Columns definition:", columns);
        
        return {
            gridExists: !!grid,
            dataSourceExists: !!grid.dataSource,
            dataItemCount: grid.dataSource ? grid.dataSource.data().length : 0,
            firstItemKeys: grid.dataSource && grid.dataSource.data().length > 0 ? 
                          Object.keys(grid.dataSource.data()[0]) : []
        };
        
    } catch (error) {
        console.error("❌ Grid inspection failed:", error);
        return null;
    }
}

function checkDataItemStructure() {
    console.log("🔍 Checking data item structure...");
    
    try {
        var grid = $('#Overrides').data('kendoGrid');
        if (!grid || !grid.dataSource) return null;
        
        var data = grid.dataSource.data();
        if (data.length === 0) {
            console.warn("⚠️ No data items to inspect");
            return null;
        }
        
        var sampleItem = data[0];
        console.log("📋 Sample item properties:");
        
        // Check all properties
        for (var key in sampleItem) {
            var value = sampleItem[key];
            var valueType = typeof value;
            var valuePreview = value;
            
            if (valueType === 'object' && value !== null) {
                valuePreview = value.Title || value.Name || JSON.stringify(value).substring(0, 100);
            }
            
            console.log(`  - ${key}: ${valueType} = ${valuePreview}`);
        }
        
        return Object.keys(sampleItem);
        
    } catch (error) {
        console.error("❌ Data item inspection failed:", error);
        return null;
    }
}

// =========================================================================
// ALTERNATIVE EXTRACTION METHODS
// =========================================================================

function extractViaDataSource() {
    console.log("🔄 Alternative: Extracting via dataSource directly...");
    
    try {
        var grid = $('#Overrides').data('kendoGrid');
        if (!grid || !grid.dataSource) return null;
        
        var data = grid.dataSource.data();
        console.log(`📊 DataSource contains ${data.length} items`);
        
        // Try different property access patterns
        var results = [];
        
        for (var i = 0; i < Math.min(data.length, 3); i++) { // Check first 3 items
            var item = data[i];
            console.log(`🔍 Item ${i} analysis:`, item);
            
            var extracted = {
                TagNumber: item.TagNumber,
                Description: item.Description,
                OverrideType: item.OverrideType,
                OverrideMethod: item.OverrideMethod,
                Comment: item.Comment,
                OverrideAppliedState: item.OverrideAppliedState,
                AdditionalValueAppliedState: item.AdditionalValueAppliedState,
                OverrideRemovedState: item.OverrideRemovedState,
                AdditionalValueRemovedState: item.AdditionalValueRemovedState
            };
            
            console.log(`📝 Item ${i} extracted:`, extracted);
            results.push(extracted);
        }
        
        return results;
        
    } catch (error) {
        console.error("❌ Alternative extraction failed:", error);
        return null;
    }
}

// =========================================================================
// EXECUTION AND TESTING
// =========================================================================

function runCompleteTest() {
    console.log("🚀 STARTING COMPLETE EXTRACTION TEST");
    console.log("=" .repeat(50));
    
    // Step 1: Inspect grid structure
    console.log("📋 STEP 1: Grid Structure Inspection");
    var gridInfo = inspectGridStructure();
    console.log("Grid inspection result:", gridInfo);
    
    console.log("\n📋 STEP 2: Data Item Structure");
    var itemStructure = checkDataItemStructure();
    console.log("Item structure:", itemStructure);
    
    console.log("\n📋 STEP 3: Alternative Extraction");
    var altResults = extractViaDataSource();
    console.log("Alternative results:", altResults);
    
    console.log("\n📋 STEP 4: Main Extraction");
    var mainResults = extractOverridesTableData();
    console.log("Main extraction results:", mainResults);
    
    console.log("\n" + "=" .repeat(50));
    console.log("🏁 EXTRACTION TEST COMPLETED");
    
    return {
        gridInfo: gridInfo,
        itemStructure: itemStructure,
        altResults: altResults,
        mainResults: mainResults
    };
}

// =========================================================================
// QUICK TEST FUNCTION
// =========================================================================

function quickTest() {
    console.log("⚡ Quick test of SOC overrides extraction");
    var result = extractOverridesTableData();
    
    if (result && !result.error) {
        console.log("✅ SUCCESS: Data extracted successfully");
        console.log(`📊 ${result.rows.length} rows, ${result.headers.length} columns`);
        console.log("📋 Headers:", result.headers);
        
        if (result.rows.length > 0) {
            console.log("📄 First row:", result.rows[0]);
        }
        
        return result;
    } else {
        console.error("❌ FAILED: Could not extract data");
        console.error("Error:", result ? result.error : "Unknown error");
        return null;
    }
}

// =========================================================================
// AUTO-RUN ON PAGE LOAD (Optional)
// =========================================================================

// Uncomment to auto-run when pasting in DevTools

console.log("🔧 SOC Exporter Debug Tools Loaded");
console.log("Available functions:");
console.log("  - quickTest(): Quick data extraction test");
console.log("  - runCompleteTest(): Full diagnostic test");
console.log("  - extractOverridesTableData(): Main extraction function");
console.log("  - inspectGridStructure(): Grid inspection");
console.log("");
console.log("Run 'quickTest()' to start...");


// Make functions globally available
window.socExporter = {
    quickTest: quickTest,
    runCompleteTest: runCompleteTest,
    extractOverridesTableData: extractOverridesTableData,
    inspectGridStructure: inspectGridStructure,
    checkDataItemStructure: checkDataItemStructure,
    extractViaDataSource: extractViaDataSource
};