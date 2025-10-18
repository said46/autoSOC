// getInstallationsBySiteUrl = "/data/getInstallationsBySite"
$.ajax({
    url: "".concat(this.getInstallationsBySiteUrl, "?siteId="),
    dataType: "json",
    cache: true
})
.then(function(response) {
    console.log('Installations response:', response);
    console.log('JSON:', JSON.stringify(response, null, 2));
    fillDropDown(e.installationSelector, response);
})
.fail(function(xhr, status, error) {
    console.error('AJAX Error:', error);
});