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
    const prettyJson = JSON.stringify(data, null, 2);
    
    // Trigger download
    const blob = new Blob([prettyJson], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `override_data_${certIdFromPopup}.json`;
    a.click();
    URL.revokeObjectURL(url);

    console.log('Download started for ID:', certIdFromPopup);
    return `Success for ID: ${certIdFromPopup}`;
  } catch (error) {
    console.error(`Error for ID ${certIdFromPopup}:`, error);
    return `Error: ${error.message}`;
  }
}

fetchAndSaveOverrideData(1959341);
