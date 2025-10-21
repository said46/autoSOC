// Override fetch to log all requests
const originalFetch = window.fetch;
window.fetch = function(...args) {
    console.log('Fetch called:', args);
    return originalFetch.apply(this, args);
};

// Override XMLHttpRequest
const originalXHR = window.XMLHttpRequest;
window.XMLHttpRequest = function() {
    const xhr = new originalXHR();
    const originalOpen = xhr.open;
    xhr.open = function(method, url) {
        console.log('XHR:', method, url);
        return originalOpen.apply(this, arguments);
    };
    return xhr;
};


// Monitor all network activity
window.addEventListener('fetch', e => console.log('Fetch:', e.request.url));