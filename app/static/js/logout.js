// Wait for page load and retry a few times if needed
function attemptClear(retries = 5) {
    if (window.clearEmailState) {
        window.clearEmailState();
    } else if (retries > 0) {
        // Try again in 100ms
        setTimeout(() => attemptClear(retries - 1), 100);
    }
}

// Check if we're coming from a logout
if (new URLSearchParams(window.location.search).get('from_logout')) {
    // Start attempting to clear
    attemptClear();
} 