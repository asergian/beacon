/**
 * @fileoverview Main entry point for email functionality.
 * This file serves as a facade for the modular components of the email system.
 * It initializes the email interface and exposes core functionality to the global scope.
 * @author Beacon Team
 * @license Copyright 2025 Beacon
 */

// Import modules
import { EmailState } from './EmailState.js';
import { EmailUI } from './EmailUI.js';
import { EmailService } from './EmailService.js';
import { EmailEvents } from './EmailEvents.js';
import { showToast } from './EmailUtils.js';

/**
 * Update config with email-specific defaults.
 * These settings control how the email system behaves by default.
 */
if (typeof window.config === 'undefined') {
    window.config = {};
}
window.config.days_back = 1;  // Increased default to show more emails
window.config.batch_size = 50;  // Batch size for UI updates

/**
 * Initialize the page when DOM is loaded.
 * This sets up event listeners and prepares the email interface.
 */
document.addEventListener('DOMContentLoaded', () => {
    EmailEvents.initializePage();
});

/**
 * Clears the current email response after confirmation.
 * This function wipes the content from the email editor.
 * 
 * @return {void}
 */
function clearEmailResponse() {
    if (confirm('Are you sure you want to clear this email response?')) {
        // Clear CKEditor content
        if (window.editor) {
            window.editor.setData('');
        }
        
        showToast('Email response cleared', 'info');
    }
}

/**
 * Expose necessary functions globally for event handlers.
 * These functions are attached to the window object to be accessed
 * by HTML event handlers and other scripts.
 */
window.clearEmailState = EmailState.clearAll;
window.loadEmailDetails = EmailUI.loadEmailDetails.bind(EmailUI);
window.sendEmailResponse = EmailService.sendEmailResponse;
window.filterEmails = EmailUI.filterEmails.bind(EmailUI);
window.clearEmailResponse = clearEmailResponse; 