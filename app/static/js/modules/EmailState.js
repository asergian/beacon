/**
 * @fileoverview Module responsible for managing the state of emails in the application.
 * Provides methods for adding, removing, and retrieving emails, as well as handling
 * state transitions and cleanup operations.
 * @author Beacon Team
 * @license Copyright 2025 Beacon
 */

import { EmailUI } from './EmailUI.js';

/**
 * @const {number} MAX_EMAILS - Maximum number of emails to keep in memory
 */
const MAX_EMAILS = 500; // Maximum number of emails to keep in memory

/**
 * @private {Array<Object>} emails - List of email objects
 * @private {Map<string, Object>} emailMap - Map of email IDs to email objects
 * @private {string|null} selectedEmailId - ID of the currently selected email
 * @private {Object|null} userSettings - User settings object
 * @private {boolean} hasInitialized - Whether the email state has been initialized
 */
// State variables
let emails = [];
let emailMap = new Map();
let selectedEmailId = null;
let userSettings = null;
let hasInitialized = false;

/**
 * EmailState - Manages the application state related to emails.
 * This module provides an interface for accessing and manipulating the email data.
 * @namespace
 */
export const EmailState = {
    /**
     * Gets the current array of emails.
     * @return {Array<Object>} The array of email objects
     */
    get emails() { return emails; },
    
    /**
     * Gets the map of email IDs to email objects.
     * @return {Map<string, Object>} The map of email objects
     */
    get emailMap() { return emailMap; },
    
    /**
     * Gets the ID of the currently selected email.
     * @return {string|null} The selected email ID or null if none selected
     */
    get selectedEmailId() { return selectedEmailId; },
    
    /**
     * Gets the current user settings.
     * @return {Object|null} The user settings object or null if not set
     */
    get userSettings() { return userSettings; },
    
    /**
     * Gets whether the email state has been initialized.
     * @return {boolean} True if the email state has been initialized
     */
    get hasInitialized() { return hasInitialized; },
    
    /**
     * Sets the ID of the selected email.
     * @param {string} id - The ID of the email to select
     * @return {void}
     */
    setSelectedEmailId(id) { 
        selectedEmailId = id; 
    },
    
    /**
     * Sets the user settings.
     * @param {Object} settings - The user settings object
     * @return {void}
     */
    setUserSettings(settings) { 
        userSettings = settings; 
    },
    
    /**
     * Sets the initialization status.
     * @param {boolean} value - The initialization status
     * @return {void}
     */
    setHasInitialized(value) { 
        hasInitialized = value; 
    },
    
    /**
     * Adds emails to the state, avoiding duplicates and managing the cache size.
     * Skips emails that are already in the state and have been analyzed.
     * Updates the UI after adding emails.
     * 
     * @param {Array<Object>} newEmails - Array of email objects to add
     * @param {boolean} isAnalyzed - Whether these emails have been analyzed
     * @return {void}
     */
    addEmails(newEmails, isAnalyzed = true) {
        // Count new and duplicate emails for logging purposes
        let newCount = 0;
        let duplicateCount = 0;
        
        console.log(`Adding ${newEmails.length} emails to state, isAnalyzed=${isAnalyzed}`);
        
        newEmails.forEach(email => {
            // Check if this email is already in our state and analyzed
            const existingEmail = emailMap.get(email.id);
            if (existingEmail && existingEmail.isAnalyzed) {
                // Skip this email as it's already in our state and analyzed
                duplicateCount++;
                return;
            }
            
            // Add to our email map
            emailMap.set(email.id, {
                ...email,
                isAnalyzed: isAnalyzed
            });
            newCount++;
        });
        
        // Log results
        if (newCount > 0) {
            console.log(`Added ${newCount} new emails to state`);
        }
        if (duplicateCount > 0) {
            console.log(`Skipped ${duplicateCount} duplicate emails`);
        }

        // Update our sorted emails array
        this.updateEmailsArray();
        
        // Clean up old emails if we have too many
        if (emails.length > MAX_EMAILS) {
            this.cleanupOldEmails();
        }
    },
    
    /**
     * Removes a single email from the state by ID.
     * Updates the UI after removing the email.
     * 
     * @param {string} emailId - ID of the email to clear
     * @return {void}
     */
    clearEmail(emailId) {
        if (emailMap.has(emailId)) {
            emailMap.delete(emailId);
            this.updateEmailsArray();
        }
    },
    
    /**
     * Clears all email state, including the UI.
     * Resets all state variables and clears the UI components.
     * 
     * @return {void}
     */
    clearAll() {
        console.log('Clearing email state');
        
        // Clear email data
        emails.length = 0;
        emailMap.clear();
        selectedEmailId = null;
        hasInitialized = false;
        
        // Clear UI
        EmailUI.clearEmailList();
        EmailUI.clearEmailDetails();
        
        // Force garbage collection if available
        if (window.gc) window.gc();
    },
    
    /**
     * Cleans up old emails when the cache exceeds the maximum size.
     * Keeps only the most recent emails up to MAX_EMAILS.
     * 
     * @return {void}
     */
    cleanupOldEmails() {
        if (emailMap.size <= MAX_EMAILS) return;
        
        console.log(`Cleaning up old emails (current size: ${emailMap.size})`);
        
        // Convert to array for sorting
        const emailArray = Array.from(emailMap.values());
        
        // Sort by date, newest first
        emailArray.sort((a, b) => new Date(b.date) - new Date(a.date));
        
        // Keep only the newest MAX_EMAILS
        const emailsToKeep = emailArray.slice(0, MAX_EMAILS);
        
        // Clear the map and add back only the emails we want to keep
        emailMap.clear();
        emailsToKeep.forEach(email => emailMap.set(email.id, email));
        
        // Update emails array
        this.updateEmailsArray();
        
        console.log(`Cleanup complete (new size: ${emailMap.size})`);
        
        // Force garbage collection if available
        if (window.gc) window.gc();
    },
    
    /**
     * Retrieves an email by its ID.
     * 
     * @param {string} emailId - ID of the email to get
     * @return {Object|null} The email object or null if not found
     */
    getEmailById(emailId) {
        return emailMap.get(emailId) || null;
    },
    
    /**
     * Updates the emails array from the current map and renders the email list.
     * This ensures the UI is synchronized with the current state.
     * 
     * @return {void}
     */
    updateEmailsArray() {
        emails = Array.from(emailMap.values());
        
        // Import EmailUI and render email list
        import('./EmailUI.js').then(module => {
            const { EmailUI } = module;
            EmailUI.renderEmailList();
        }).catch(error => {
            console.error('Error importing EmailUI module:', error);
        });
    }
}; 