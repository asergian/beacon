/**
 * @fileoverview Handles email API calls and operations for the email application.
 * This module provides methods to interact with the server for sending emails,
 * fetching user settings, and managing email data.
 * @author Beacon Team
 * @license Copyright 2025 Beacon
 */

import { showToast } from './EmailUtils.js';
import { EmailUI } from './EmailUI.js';

/**
 * EmailService - Handles API calls and operations related to emails.
 * Provides methods for communicating with the server to send and fetch emails,
 * as well as managing user settings and other email-related operations.
 * @namespace
 */
export const EmailService = {
    /**
     * Fetches user settings from the server.
     * Updates the global configuration with user preferences like days_back.
     * Logs the retrieved settings and any conversion or default values applied.
     *
     * @return {Promise<Object|null>} The user settings object or null if an error occurs
     */
    async fetchUserSettings() {
        try {
            const response = await fetch('/user/api/settings');
            if (response.ok) {
                const data = await response.json();
                if (data.status === 'success' && data.settings) {
                    // Store user settings in a global variable
                    const userSettings = data.settings;
                    
                    // Always apply the user's days_back setting, even in demo mode
                    // Ensure it's converted to an integer to prevent type errors in the server
                    if (userSettings.email_preferences && userSettings.email_preferences.days_to_analyze !== undefined) {
                        const daysToAnalyze = userSettings.email_preferences.days_to_analyze;
                        // Force conversion to integer
                        window.config.days_back = parseInt(daysToAnalyze, 10) || 1;
                        console.log('Updated days_back setting:', window.config.days_back, '(original value:', daysToAnalyze, ')');
                    } else {
                        window.config.days_back = 1; // Default if not set
                        console.log('Using default days_back setting: 1');
                    }
                    
                    console.log('Updated user settings:', userSettings);
                    return userSettings;
                }
            }
            return null;
        } catch (error) {
            console.warn('Failed to fetch user settings:', error);
            return null;
        }
    },

    /**
     * Sends an email response to the server.
     * Collects data from the response form and sends it to the API endpoint.
     * Shows appropriate toast messages based on the server response.
     *
     * @return {Promise<boolean>} True if the email was sent successfully, false otherwise
     */
    async sendEmailResponse() {
        // Get form data
        const to = document.getElementById('response-to').value;
        const cc = document.getElementById('response-cc').value;
        const subject = document.getElementById('response-subject').value;
        const content = window.editor.getData();
        const originalEmailId = window.selectedEmailId;

        // Validate form
        if (!to || !subject || !content) {
            showToast('Please fill in all required fields', 'error');
            return;
        }

        // Show loading state
        const sendButton = document.getElementById('send-button');
        if (sendButton) {
            const originalText = sendButton.innerHTML;
            sendButton.disabled = true;
            sendButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Sending...';
        }

        try {
            const response = await fetch('/email/api/emails/send_email', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    to,
                    cc,
                    subject,
                    content,
                    original_email_id: originalEmailId
                })
            });
            
            // Check if response is ok
            if (!response.ok) {
                const errorText = await response.text();
                let errorData;
                try {
                    errorData = JSON.parse(errorText);
                } catch (e) {
                    errorData = { message: 'Server error occurred' };
                }
                throw new Error(errorData.message || `Server error: ${response.status}`);
            }

            const data = await response.json();

            if (data.success) {
                // Show success message with information about which method was used
                let successMessage = 'Email sent successfully';
                if (data.sent_via === 'gmail_api') {
                    successMessage += ' via your Gmail account';
                } else {
                    successMessage += ' via Beacon mail server';
                }
                showToast(successMessage, 'success');
                
                // Reset form
                window.editor.setData('');
                
                // Only update UI if we have a valid original email
                if (originalEmailId) {
                    EmailUI.updateEmailItemUI(originalEmailId);
                }
            } else {
                throw new Error(data.message || 'Failed to send email');
            }
        } catch (error) {
            console.error('Error sending email:', error);
            showToast(error.message || 'Failed to send email', 'error');
        } finally {
            // Reset button state
            if (sendButton) {
                sendButton.disabled = false;
                sendButton.innerHTML = '<svg class="button-icon" viewBox="0 0 24 24" width="18" height="18"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" fill="currentColor"></path></svg> Send';
            }
        }
    }
}; 