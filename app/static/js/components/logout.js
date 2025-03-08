/**
 * @fileoverview Handles post-logout cleanup operations.
 * Attempts to clear email state when returning from logout.
 * @author Beacon Team
 * @license Copyright 2025 Beacon
 */

/**
 * Attempts to clear the email state with exponential backoff.
 * Retries multiple times to ensure the clearEmailState function is available.
 * 
 * @param {number} retries - Number of remaining retry attempts
 * @return {void}
 */
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