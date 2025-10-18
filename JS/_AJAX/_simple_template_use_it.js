// OPF installation Id is 43!!!
// call getRolesByInstallation for installationId from 1 to 9
// BUT only if there is more than one role (usually Guest)
const getRolesByInstallation = (installationId) => {
    return $.ajax({
        url: "/data/GetInstallationRoles",
        data: { installationId },
        dataType: "json"
    })
    .then(roles => {
        console.log('Roles:', roles);
        return roles;
    })
    .fail((xhr, status, error) => {
        console.error('AJAX Error:', error);
        return []; // Return empty array instead of failing
    });
};

const arr = Array.from({length: 20}, (_, i) => (i + 1).toString());

// Process sequentially (one after another)
async function fetchAllRoles() {
    for (const installationId of arr) {
        console.log(`\n📡 Fetching roles for installation ${installationId}...`);
        try {
            const roles = await getRolesByInstallation(installationId);
			if (roles.length < 1) {
				console.log(`✅ Installation ${installationId} roles:`, roles);
			}
        } catch (error) {
            console.error(`❌ Installation ${installationId} failed:`, error);
        }
    }
}

fetchAllRoles();