async function fetchAndSaveOverrideData(certIdFromPopup) {
  console.log('Using Certificate ID:', certIdFromPopup);
  const fullUrl = 'http://eptw.sakhalinenergy.ru/Soc/GetOverrides/' + certIdFromPopup;

  try {
    const response = await fetch(fullUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: 'sort=&group=&filter='
    });

    if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
    
    const data = await response.json();
    
    // Convert JSON to CSV format with proper comma delimiter
    const csvContent = convertJsonToCsv(data, certIdFromPopup);
    
    // Use UTF-8 with BOM
    const BOM = '\uFEFF';
    const blob = new Blob([BOM + csvContent], { 
      type: 'text/csv; charset=utf-8'
    });
    
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `override_data_${certIdFromPopup}.csv`;
    a.click();
    URL.revokeObjectURL(url);

    console.log('CSV download started for ID:', certIdFromPopup);
    return `Success for ID: ${certIdFromPopup}`;
  } catch (error) {
    console.error(`Error for ID ${certIdFromPopup}:`, error);
    return `Error: ${error.message}`;
  }
}

function convertJsonToCsv(data, certId) {
  const currentDate = new Date().toLocaleString('sv-SE').replace('T', ' ');
  
  let csvContent = '';
  
  // Add metadata as separate lines (not as CSV rows)
  csvContent += `SOC Overrides Export\n`;
  csvContent += `SOC ID: ${certId}\n`;
  csvContent += `Export Date: ${currentDate}\n`;
  
  let overrideData = [];
  let totalOverrides = 0;
  
  if (Array.isArray(data)) {
    overrideData = data;
    totalOverrides = data.length;
  } else if (data && typeof data === 'object') {
    if (data.Data && Array.isArray(data.Data)) {
      overrideData = data.Data;
      totalOverrides = data.Data.length;
    } else {
      overrideData = [data];
      totalOverrides = 1;
    }
  }
  
  csvContent += `Total Overrides: ${totalOverrides}\n`;
  csvContent += `\n`;
  
  if (overrideData.length === 0) {
    csvContent += `No override data found\n`;
    return csvContent;
  }
  
  // Headers matching your Excel template
  const headers = [
    'TagNumber',
    'Description', 
    'OverrideType',
    'OverrideMethod',
    'Comment',
    'AppliedState',
    'AdditionalValueAppliedState',
    'RemovedState',
    'AdditionalValueRemovedState'
  ];
  
  // Add CSV headers with comma delimiter
  csvContent += headers.join(',') + '\n';
  
  // Add data rows with proper CSV formatting
  overrideData.forEach(item => {
    const row = [
      item.TagNumber || '',
      item.Description || '',
      item.OverrideType ? (item.OverrideType.Title || '') : '',
      item.OverrideMethod ? (item.OverrideMethod.Title || '') : '',
      item.Comment || '',
      item.OverrideAppliedState ? (item.OverrideAppliedState.Title || '') : '',
      item.AdditionalValueAppliedState || '',
      item.OverrideRemovedState ? (item.OverrideRemovedState.Title || '') : '',
      item.AdditionalValueRemovedState || ''
    ].map(value => {
      // Escape CSV special characters: quotes, commas, and newlines
      const stringValue = String(value);
      if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n') || stringValue.includes('\r')) {
        return `"${stringValue.replace(/"/g, '""')}"`;
      }
      return stringValue;
    });
    
    csvContent += row.join(',') + '\n';
  });
  
  return csvContent;
}

// Usage
fetchAndSaveOverrideData(1959341);