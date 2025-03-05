/**
 * @fileoverview Utility functions for email handling and UI interaction.
 * Provides helper functions for date formatting, email parsing, notifications,
 * loading indicators, and batch processing.
 * @author Beacon Team
 * @license Copyright 2025 Beacon
 */

/**
 * Formats a date string to a more readable format based on its recency.
 * Returns different formats depending on how recent the date is:
 * - Less than a day: shows time (e.g., "2:30 PM")
 * - Yesterday: shows "Yesterday"
 * - Less than a week: shows day name (e.g., "Monday")
 * - This year: shows month and day (e.g., "Jun 15")
 * - Earlier years: shows full date (e.g., "Jun 15, 2023")
 * 
 * @param {Date|string} dateString - Date object or ISO date string
 * @return {string} Formatted date string
 */
export function formatDate(dateString) {
    if (!dateString) return 'Unknown Date';
    
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    // Less than a day ago
    if (diffDays < 1) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    
    // Yesterday
    if (diffDays === 1) {
        return 'Yesterday';
    }
    
    // Less than a week ago
    if (diffDays < 7) {
        return date.toLocaleDateString([], { weekday: 'long' });
    }
    
    // This year
    if (date.getFullYear() === now.getFullYear()) {
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
    
    // Earlier years
    return date.toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' });
}

/**
 * Extracts an email address from a text string.
 * First looks for the pattern "anything <email@example.com>",
 * then falls back to a simple email regex pattern if that fails.
 * 
 * @param {string} text - Text containing an email address
 * @return {string|null} The extracted email address or null if not found
 */
export function extractEmailAddress(text) {
    if (!text) return null;
    
    // Look for pattern "anything <email@example.com>"
    const matches = text.match(/<([^>]+)>/);
    if (matches && matches[1]) {
        return matches[1].trim();
    }
    
    // Or just look for something that looks like an email address
    const emailMatches = text.match(/[\w.-]+@[\w.-]+\.\w+/);
    if (emailMatches && emailMatches[0]) {
        return emailMatches[0].trim();
    }
    
    return null;
}

/**
 * Shows a toast notification message to the user.
 * Creates and adds a toast element to the DOM, automatically removing it after 5 seconds.
 * If no toast container exists, creates one and appends it to the body.
 * 
 * @param {string} message - Message to display in the toast
 * @param {string} type - Message type ('info', 'success', 'warning', 'error')
 * @return {void}
 */
export function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    // Add to DOM
    const toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        const container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
        container.appendChild(toast);
    } else {
        toastContainer.appendChild(toast);
    }
    
    // Trigger reflow to enable CSS transition
    toast.offsetHeight;
    
    // Show toast
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
    
    // Auto-hide after timeout
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.remove();
        }, 300); // Wait for fade-out transition to complete
    }, 5000);
}

/**
 * Shows the loading bar with a message.
 * Updates the loading text element with the provided message.
 * 
 * @param {string} message - Message to display in the loading bar
 * @return {void}
 */
export function showLoadingBar(message) {
    const loadingBar = document.getElementById('loading-bar');
    if (!loadingBar) return;
    
    const loadingText = loadingBar.querySelector('.loading-text');
    if (loadingText) {
        loadingText.textContent = message;
    }
    
    loadingBar.style.display = 'flex';
}

/**
 * Hides the loading bar.
 * Sets the display style of the loading bar element to 'none'.
 * 
 * @return {void}
 */
export function hideLoadingBar() {
    const loadingBar = document.getElementById('loading-bar');
    if (loadingBar) {
        loadingBar.style.display = 'none';
    }
}

/**
 * Formats a tag text by capitalizing the first letter and lowercasing the rest.
 * 
 * @param {string} text - Tag text to format
 * @return {string} Formatted tag text
 */
export function formatTagText(text) {
    if (!text) return '';
    return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
}

/**
 * Processes updates in batches to prevent UI freezing.
 * Divides the processing into smaller chunks and schedules them using setTimeout
 * to allow the browser to handle user interactions between batches.
 * 
 * @param {Array<*>} updates - Array of items to process
 * @param {function(*): void} processFunction - Function to call on each item
 * @param {number=} batchSize - Number of items to process per batch (default: 50)
 * @param {function(): void=} onComplete - Function to call when all processing is complete
 * @return {void}
 */
export function batchProcess(updates, processFunction, batchSize = 50, onComplete = null) {
    let index = 0;
    
    function processNextBatch() {
        const endIndex = Math.min(index + batchSize, updates.length);
        
        for (let i = index; i < endIndex; i++) {
            processFunction(updates[i], i);
        }
        
        index = endIndex;
        
        if (index < updates.length) {
            setTimeout(processNextBatch, 0);
        } else if (onComplete) {
            onComplete();
        }
    }
    
    processNextBatch();
} 