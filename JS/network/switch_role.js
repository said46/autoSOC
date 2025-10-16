// Example of proper automation approach (conceptual)
async function changeRole(roleName) {
    // First, you'd need to:
    // 1. Login properly
    // 2. Extract fresh CSRF tokens
    // 3. Make the request with current session
    
    const response = await fetch('/User/ChangeRole', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
            CurrentRoleName: roleName,
            ReturnUrl: '/',
            IsMenuButton: 'True',
            __RequestVerificationToken: 'FRESH_TOKEN_HERE' // Get this dynamically
        })
    });
    
    return response;
}
