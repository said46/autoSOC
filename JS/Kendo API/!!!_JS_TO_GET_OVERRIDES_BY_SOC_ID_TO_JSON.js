function fetchAndLogOverrideData(certificateId) {
    const baseUrl = 'https://eptw-training.sakhalinenergy.ru/Soc/GetOverrides/';
    const fullUrl = baseUrl + certificateId;
  
    // Define the request body (standard Kendo params when no sorting/filtering is applied)
    const requestBody = 'sort=&group=&filter=';
  
    // Define the fetch options
    const fetchOptions = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: requestBody
    };
  
    // Perform the fetch request
    fetch(fullUrl, fetchOptions)
      .then(response => {
        // Check if the response status is OK (200-299)
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
        // Parse the response as JSON
        return response.json();
      })
      .then(data => {
        // Convert the received data object to a pretty-printed JSON string
        const prettyJsonString = JSON.stringify(data, null, 2);
        console.log(`Pretty JSON response for Certificate ID ${certificateId}:`);
        console.log(prettyJsonString);
  
        // Optional: Attempt to create a downloadable file directly in the browser console
        // Note: This might be blocked by some browsers depending on the context.
        /*
        const blob = new Blob([prettyJsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `override_data_${certificateId}.json`; // Suggest a filename
        document.body.appendChild(a); // Required for Firefox
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url); // Clean up the URL object
        */
      })
      .catch(error => {
        // Handle any errors during the fetch or processing
        console.error(`Error fetching override data for ID ${certificateId}:`, error);
      });
  }
  
  // Example usage:
  fetchAndLogOverrideData('1050638'); // Call the function with your specific ID
  // You can call it again with a different ID like this:
  // fetchAndLogOverrideData('999999');