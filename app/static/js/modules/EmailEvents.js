/**
 * @fileoverview Handles event setup and initialization for the email module.
 * This module manages server-sent events (SSE) connections, event listeners,
 * and initializes the email interface by connecting to the API endpoints.
 * @author Beacon Team
 * @license Copyright 2025 Beacon
 */

import { EmailState } from './EmailState.js';
import { EmailService } from './EmailService.js';
import { showLoadingBar, hideLoadingBar } from './EmailUtils.js';

/**
 * @const {number} MAX_RECONNECT_ATTEMPTS - Maximum number of reconnection attempts
 * @const {number} RECONNECT_DELAY - Delay between reconnection attempts in milliseconds
 */
const MAX_RECONNECT_ATTEMPTS = 3;
const RECONNECT_DELAY = 2000; // 2 seconds

/**
 * @private {EventSource|null} eventSource - Server-sent events connection
 * @private {number} reconnectAttempts - Count of reconnection attempts made
 * @private {boolean} emailsLoadedSuccessfully - Flag to track if emails have been loaded successfully
 * @private {boolean} sseConnectedOnce - Flag to track if we've had at least one successful connection
 */
let eventSource = null;
let reconnectAttempts = 0;
let emailsLoadedSuccessfully = false; // Flag to track if emails have been loaded successfully
let sseConnectedOnce = false; // Flag to track if we've had at least one successful connection

/**
 * EmailEvents - Handles event setup and connection management.
 * This namespace provides methods for initializing the email page,
 * managing server-sent events connections, and handling various
 * email-related events.
 * @namespace
 */
export const EmailEvents = {
    /**
     * Initializes the email page by setting up event listeners and establishing
     * connections to the server for real-time updates.
     * Checks if the page has the required email elements before proceeding.
     * Only initializes once even if called multiple times.
     *
     * @return {Promise<void>} A promise that resolves when initialization is complete
     */
    async initializePage() {
        console.log('Initializing email page...');
        
        // Check if we're on the email summary page by looking for specific elements
        const emailList = document.querySelector('.email-list');
        const emailDetails = document.getElementById('email-details');
        const loadingBar = document.getElementById('loading-bar');
        
        // Only initialize if we have all the required email page elements
        if (!emailList || !emailDetails || !loadingBar) {
            console.log('Not on email summary page, skipping initialization');
            return;
        }
        
        if (EmailState.hasInitialized) {
            console.log('Page already initialized, skipping');
            return;
        }
        
        console.log('Starting fresh initialization...');
        EmailState.setHasInitialized(true);
        
        // Reset module-level flags for a fresh start
        emailsLoadedSuccessfully = false;
        sseConnectedOnce = false;
        reconnectAttempts = 0;
        
        // Initialize loading indicators
        this._initializeLoadingIndicators();
        
        // Set up event listeners
        this._setupEventListeners();
        
        EmailState.clearAll();
        
        try {
            // Initialize editor if not already done in the template
            if (window.BalloonEditor && !document.querySelector('.ck-editor__editable')) {
                await this._initializeEditor();
            } else {
                console.log('CKEditor already initialized in the HTML template');
            }
        } catch (e) {
            console.log('Error initializing CKEditor:', e);
        }
        
        try {
            // Set a timeout to prevent hanging if setupSSEConnection never resolves or rejects
            const connectionPromise = this.setupSSEConnection();
            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => reject(new Error('Connection timed out')), 30000); // 30 second timeout
            });
            
            await Promise.race([connectionPromise, timeoutPromise]);
        } catch (error) {
            console.error('Error loading emails:', error);
            // Reset initialization flag so we can try again
            EmailState.setHasInitialized(false);
            
            // Show error message to the user
            this._updateLoadingIndicators(
                100,
                `Error loading emails: ${error.message}. Please refresh the page to try again.`,
                true
            );
            
            // If we still have an open connection, close it
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
        }
    },
    
    /**
     * Sets up event listeners for interactive elements on the page.
     * Attaches handlers to filter selectors, send button, and other UI elements.
     * 
     * @private
     * @return {void}
     */
    _setupEventListeners() {
        // Set up filter event listeners
        const priorityFilter = document.getElementById('priority-filter');
        const categoryFilter = document.getElementById('category-filter');
        const actionFilter = document.getElementById('action-filter');
        
        if (priorityFilter) priorityFilter.addEventListener('change', window.filterEmails);
        if (categoryFilter) categoryFilter.addEventListener('change', window.filterEmails);
        if (actionFilter) actionFilter.addEventListener('change', window.filterEmails);
        
        // Set up email response functionality
        const sendButton = document.getElementById('send-button');
        if (sendButton) {
            // Remove the onclick attribute if it exists and add event listener
            sendButton.removeAttribute('onclick');
            sendButton.addEventListener('click', window.sendEmailResponse);
        }
        
        // Set up discard button
        const clearButton = document.getElementById('clear-button');
        if (clearButton) {
            clearButton.removeAttribute('onclick');
            clearButton.addEventListener('click', window.clearEmailResponse);
        }
        
        // Initialize CKEditor if the response editor element exists
        const responseEditor = document.getElementById('response-editor');
        if (responseEditor && typeof window.ClassicEditor !== 'undefined') {
            console.log('CKEditor already initialized in the HTML template');
        }
    },
    
    /**
     * Sets up the Server-Sent Events connection for real-time email updates.
     * Handles reconnection logic and ensures only one active connection exists.
     * Shows appropriate loading indicators during connection process.
     * 
     * @return {Promise<void>} A promise that resolves when the connection is established
     */
    async setupSSEConnection() {
        // If emails have been loaded successfully and we've had at least one connection, don't reconnect
        if (emailsLoadedSuccessfully && sseConnectedOnce) {
            console.log('Emails already loaded, skipping reconnection');
            return Promise.resolve();
        }
        
        // Close existing connection if any
        if (eventSource) {
            console.log('Closing existing EventSource connection');
            eventSource.close();
            eventSource = null;
        }
        
        // Show connecting message
        this._updateLoadingIndicators(5, 'Connecting to server...');
        
        try {
            // Check if we're in demo mode
            const isDemoMode = document.body.hasAttribute('data-demo-mode');
            
            // Choose the appropriate API endpoint based on demo mode
            const streamEndpoint = isDemoMode 
                ? '/demo/api/emails/stream' 
                : '/email/api/emails/stream';
                
            console.log(`Connecting to ${streamEndpoint} (Demo Mode: ${isDemoMode})`);
            
            // Create new EventSource with credentials
            eventSource = new EventSource(streamEndpoint, {
                withCredentials: true  // Include cookies for auth
            });
            
            // Set up common event handlers
            this._setupEventHandlers(eventSource);
            
            // Return a promise that resolves when connected
            return new Promise((resolve, reject) => {
                eventSource.addEventListener('connected', (event) => {
                    console.log('SSE connection established');
                    sseConnectedOnce = true;
                    
                    // Update loading indicator to show connection success
                    this._updateLoadingIndicators(10, 'Connected. Retrieving emails...');
                    
                    resolve();
                });
                
                // Handle close event from server
                eventSource.addEventListener('close', (event) => {
                    console.log('Server requested connection close:', event);
                    if (eventSource) {
                        console.log('Closing EventSource on server request');
                        eventSource.close();
                        eventSource = null;
                    }
                    resolve();
                });
                
                // Handle errors
                eventSource.addEventListener('error', (event) => {
                    console.error('SSE connection error:', event);
                    
                    // Try to extract error data if it's a MessageEvent with data
                    let errorMessage = null;
                    let isServerError = false;
                    
                    try {
                        if (event instanceof MessageEvent && event.data) {
                            const data = JSON.parse(event.data);
                            // Log the full error object for debugging
                            console.error('Server error full data:', data);
                            
                            if (data.message) {
                                errorMessage = data.message;
                                isServerError = true;
                                console.error('Server error details:', errorMessage);
                            }
                        }
                    } catch (e) {
                        console.log('Error event is not a parseable MessageEvent, treating as connection error');
                    }
                    
                    // If emails already loaded, ignore error
                    if (emailsLoadedSuccessfully) {
                        console.log('Emails already loaded, ignoring connection error');
                        if (eventSource) {
                            eventSource.close();
                            eventSource = null;
                        }
                        console.log('Closing EventSource after error (emails already loaded)');
                        resolve(); // Resolve the promise since we already have emails
                        return;
                    }
                    
                    // Close current connection before attempting reconnect
                    if (eventSource) {
                        console.log('Closing EventSource before reconnect attempt');
                        eventSource.close();
                        eventSource = null;
                    }
                    
                    // Handle reconnection if we haven't exceeded max attempts
                    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                        reconnectAttempts++;
                        console.log(`Reconnecting... Attempt ${reconnectAttempts} of ${MAX_RECONNECT_ATTEMPTS}`);
                        
                        // Update loading indicator to show reconnection attempt
                        this._updateLoadingIndicators(
                            5,
                            `Connection lost. Reconnecting (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`
                        );
                        
                        // Schedule reconnection attempt with increasing delay
                        const delay = RECONNECT_DELAY * Math.pow(1.5, reconnectAttempts - 1);
                        console.log(`Waiting ${delay}ms before reconnection attempt ${reconnectAttempts}`);
                        
                        setTimeout(() => {
                            console.log(`Starting reconnection attempt ${reconnectAttempts}`);
                            
                            // Call setupSSEConnection again to try reconnecting
                            this.setupSSEConnection()
                                .catch(err => {
                                    console.error(`Reconnection attempt ${reconnectAttempts} failed:`, err);
                                });
                        }, delay);
                    } else {
                        console.error(`Maximum reconnect attempts (${MAX_RECONNECT_ATTEMPTS}) reached, giving up`);
                        
                        // Show error in loading indicator
                        this._updateLoadingIndicators(
                            100,
                            `Failed to connect after ${MAX_RECONNECT_ATTEMPTS} attempts. Please refresh the page to try again.`,
                            false
                        );
                    }
                    
                    // Always reject the promise since there was an error
                    reject(new Error('SSE connection error'));
                });
            });
        } catch (error) {
            console.error('Error setting up SSE connection:', error);
            throw error;
        }
    },
    
    /**
     * Sets up event handlers for the SSE connection to process incoming events.
     * Handles various event types including 'status', 'email', 'batch', etc.
     * Updates loading indicators and EmailState based on received events.
     * 
     * @param {EventSource} source - The EventSource object to attach handlers to
     * @private
     * @return {void}
     */
    _setupEventHandlers(source) {
        // Status updates
        source.addEventListener('status', (event) => {
            const data = JSON.parse(event.data);
            console.log('Status update:', data.message);
            
            // Show relevant status messages
            if (data.message.includes('Loading') || 
                data.message.includes('Found') || 
                data.message.includes('Processing') || 
                data.message.includes('Analyzed') || 
                data.message.includes('Analysis complete')) {
                
                // Determine progress percentage (estimate based on message)
                let progress = 10; // Default starting progress
                let displayMessage = data.message;
                
                // Extract processing counts if available
                if (data.message.includes('Processing') && data.count !== undefined && data.total !== undefined) {
                    progress = Math.min(70, 20 + Math.floor((data.count / data.total) * 50));
                    displayMessage = `Analyzed: ${data.count}/${data.total} (${Math.round(data.count/data.total*100)}%)`;
                } else if (data.message.includes('Found')) {
                    progress = 20;
                    // Extract number of emails if available
                    const match = data.message.match(/Found (\d+) new emails/);
                    if (match && match.length === 2) {
                        const newEmails = parseInt(match[1]);
                        if (!isNaN(newEmails)) {
                            displayMessage = `Found ${newEmails} new emails`;
                        }
                    }
                } else if (data.message.includes('Processing')) {
                    progress = 40;
                } else if (data.message.includes('Analyzed')) {
                    progress = 70;
                    // Extract completion information if available
                    const match = data.message.match(/Analyzed (\d+) of (\d+)/);
                    if (match && match.length === 3) {
                        const analyzed = parseInt(match[1]);
                        const total = parseInt(match[2]);
                        if (!isNaN(analyzed) && !isNaN(total) && total > 0) {
                            progress = 20 + Math.floor((analyzed / total) * 50);
                            displayMessage = `Analyzing: ${analyzed}/${total} (${Math.round(analyzed/total*100)}%)`;
                        }
                    }
                } else if (data.message.includes('complete')) {
                    progress = 100;
                }
                
                // Update the loading indicators
                this._updateLoadingIndicators(progress, displayMessage);
            }
        });
        
        // Initial stats event (contains total counts before processing starts)
        source.addEventListener('initial_stats', (event) => {
            const data = JSON.parse(event.data);
            console.log('Initial stats received:', data);
            
            // Store the total counts for use in progress calculations
            this.totalEmails = data.total_fetched || 0;
            this.newEmails = data.new_emails || 0;
            this.cachedEmails = data.cached || 0;
            
            console.log(`Email processing stats: ${this.newEmails} new, ${this.cachedEmails} cached, ${this.totalEmails} total`);
            
            // Update loading indicator with initial stats
            if (this.newEmails > 0) {
                this._updateLoadingIndicators(
                    30,
                    `Starting analysis of ${this.newEmails} new emails`
                );
            }
        });
        
        // Cached emails
        source.addEventListener('cached', (event) => {
            const data = JSON.parse(event.data);
            if (data.emails && data.emails.length > 0) {
                console.log(`Received ${data.emails.length} cached emails from server`);
                
                // Set flag indicating we've loaded emails successfully
                emailsLoadedSuccessfully = true;
                console.log('Emails loaded successfully from cache, emailsLoadedSuccessfully =', emailsLoadedSuccessfully);
                
                // Check if we should replace all emails (for filtered cache updates)
                const shouldReplace = data.replace_previous === true;
                
                if (shouldReplace) {
                    console.log('Replacing previous emails with filtered cached emails');
                    // Clear all emails before adding the new filtered set
                    EmailState.clearAll();
                }
                
                // Add the cached emails to state
                EmailState.addEmails(data.emails, true);
                
                // Show the email list and details
                this._showEmailComponents();
                
                // Set appropriate completion message
                let message = `✓ Loaded ${data.emails.length} cached emails`;
                if (shouldReplace && data.filtered_count > 0) {
                    message = `✓ Updated: removed ${data.filtered_count} deleted emails`;
                }
                
                // Update loading indicators to show cache load complete and hide after delay
                this._updateLoadingIndicators(
                    100, 
                    message,
                    true // Set to true to hide after delay
                );
            }
        });
        
        // Individual email
        source.addEventListener('email', (event) => {
            const data = JSON.parse(event.data);
            console.log(`Received individual email: ${data.id}`);
            
            // Add new email
            EmailState.addEmails([data], true);
            
            // Show the email list and details
            this._showEmailComponents();
            
            // Get the current email count
            const emailCount = EmailState.emails.length;
            const totalExpected = this.newEmails + this.cachedEmails;
            
            // Calculate progress if we know total emails
            let progress = 85;
            let message = `Emails: ${emailCount} processed`;
            
            if (totalExpected > 0) {
                progress = Math.min(85, 50 + Math.floor((emailCount / totalExpected) * 35));
                message = `Analyzed: ${emailCount}/${totalExpected} (${Math.round(emailCount/totalExpected*100)}%)`;
            }
            
            // Update loading indicator to show progress
            this._updateLoadingIndicators(progress, message);
        });
        
        // Batch of emails
        source.addEventListener('batch', (event) => {
            const data = JSON.parse(event.data);
            if (data.emails && data.emails.length > 0) {
                console.log(`Received batch of ${data.emails.length} analyzed emails`);
                
                // Add new emails
                EmailState.addEmails(data.emails, true);
                
                // Show the email list and details
                this._showEmailComponents();
                
                // Get the current email count and any progress info from the data
                const emailCount = EmailState.emails.length;
                const totalExpected = this.newEmails + this.cachedEmails;
                
                let progressMessage;
                let progressPercent;
                
                if (totalExpected > 0) {
                    // We know the total, so we can calculate a percentage
                    progressPercent = Math.min(90, 50 + Math.floor((emailCount / totalExpected) * 40));
                    progressMessage = `Analyzed: ${emailCount}/${totalExpected} (${Math.round(emailCount/totalExpected*100)}%)`;
                } else {
                    // Fallback if we don't know the total
                    progressPercent = 85;
                    progressMessage = `Analyzed: ${emailCount} processed`;
                }
                
                // Update loading indicator to show batch progress
                this._updateLoadingIndicators(progressPercent, progressMessage);
            }
        });
        
        // Stats event - this is sent when processing is complete
        source.addEventListener('stats', (event) => {
            const data = JSON.parse(event.data);
            console.log('Email stats received:', data);
            
            emailsLoadedSuccessfully = true;
            console.log('Processing complete (stats event), emailsLoadedSuccessfully =', emailsLoadedSuccessfully);
            
            // Display final processing stats
            const processed = data.processed || data.new_emails || 0;
            const cached = data.cached || 0;
            const total = data.total || data.total_fetched || processed + cached;
            
            // Update completion message with clear success indication
            const message = `✓ Complete. ${total} emails (${cached} cached, ${processed} new)`;
            
            // Use the updateLoadingIndicators method with hideAfterDelay set to true
            this._updateLoadingIndicators(100, message, true);
        });
        
        // Close event - server sends this after 'stats' and when closing the connection
        source.addEventListener('close', (event) => {
            const data = JSON.parse(event.data);
            console.log('Stream closing:', data.message);
            
            // If we haven't already set success from stats event
            if (!emailsLoadedSuccessfully) {
                emailsLoadedSuccessfully = true;
                console.log('Processing complete (close event), emailsLoadedSuccessfully =', emailsLoadedSuccessfully);
                
                // Show completion message if not already shown by stats event
                this._updateLoadingIndicators(100, `✓ Complete`, true);
            }
            
            // Close the EventSource connection
            setTimeout(() => {
                if (source && source.readyState !== 2) { // 2 is CLOSED
                    console.log('Closing SSE connection after receiving close event');
                    source.close();
                    this.eventSource = null;
                }
            }, 500);
        });
        
        // Complete event (for backward compatibility, though server doesn't send this anymore)
        source.addEventListener('complete', (event) => {
            const data = JSON.parse(event.data);
            console.log('Email processing complete event:', data);
            
            emailsLoadedSuccessfully = true;
            console.log('Processing complete (complete event), emailsLoadedSuccessfully =', emailsLoadedSuccessfully);
            
            // Display final processing stats
            const processed = data.processed || 0;
            const cached = data.cached || 0;
            const total = data.total || cached + processed;
            
            // Update completion message with clear success indication
            const message = `✓ Complete. ${total} emails (${cached} cached, ${processed} new)`;
            
            // Use the updateLoadingIndicators method with hideAfterDelay set to true
            this._updateLoadingIndicators(100, message, true);
            
            // Close the EventSource connection as we don't need it anymore
            setTimeout(() => {
                if (source && source.readyState !== 2) { // 2 is CLOSED
                    console.log('Closing SSE connection after complete event');
                    source.close();
                    this.eventSource = null;
                }
            }, 500);
        });
    },
    
    /**
     * Shows email components when emails are ready to be displayed.
     * Fades in the email list and details sections.
     * 
     * @private
     * @return {void}
     */
    _showEmailComponents() {
        const emailList = document.querySelector('.email-list');
        const emailDetails = document.getElementById('email-details');
        
        // Import EmailUI and render email list
        import('./EmailUI.js').then(module => {
            const { EmailUI } = module;
            EmailUI.renderEmailList();
        }).catch(error => {
            console.error('Error importing EmailUI module:', error);
        });
    },
    
    /**
     * Loads the first email in the list if available.
     * Called after emails have been successfully loaded.
     * 
     * @private
     * @return {void}
     */
    _loadFirstEmail() {
        const emails = EmailState.emails;
        if (emails.length > 0) {
            const firstEmail = emails[0];
            EmailState.setSelectedEmailId(firstEmail.id);
            // Call the global function through window for now
            // This would be replaced with a direct module call in the future
            window.loadEmailDetails(firstEmail.id);
        }
    },
    
    /**
     * Initializes loading indicators to provide visual feedback during email processing.
     * Sets up the loading bar and text elements with initial values.
     * 
     * @private
     * @return {void}
     */
    _initializeLoadingIndicators() {
        const loadingBar = document.getElementById('loading-bar');
        const loadingText = document.getElementById('loading-text');
        
        if (loadingBar) {
            loadingBar.style.width = '0';
            loadingBar.style.display = 'block'; // Make it visible from the start
            
            // Use a small delay to ensure CSS transitions work properly
            setTimeout(() => {
                loadingBar.style.width = '10%'; // Start with 10% progress
            }, 50);
        }
        
        if (loadingText) {
            loadingText.textContent = 'Preparing to load emails...';
            loadingText.style.display = 'block'; // Make it visible from the start
            
            // Use a small delay to ensure CSS transitions work properly
            setTimeout(() => {
                loadingText.style.opacity = '1';
            }, 50);
        }
    },
    
    /**
     * Updates loading indicators with progress and message information.
     * Controls the visibility, width, and text content of loading elements.
     * Can automatically hide the indicators after a delay if specified.
     * 
     * @param {number} progress - Percentage of completion (0-100)
     * @param {string} message - Message to display in the loading indicator
     * @param {boolean} hideAfterDelay - Whether to hide indicators after a delay
     * @private
     * @return {void}
     */
    _updateLoadingIndicators(progress, message, hideAfterDelay = false) {
        const loadingBar = document.getElementById('loading-bar');
        const loadingText = document.getElementById('loading-text');
        
        // Update progress bar
        if (loadingBar) {
            // Make sure it's visible before animation
            loadingBar.style.display = 'block';
            
            // Use RAF to ensure display change has taken effect
            requestAnimationFrame(() => {
                loadingBar.style.width = `${progress}%`;
            });
        }
        
        // Update text
        if (loadingText && message) {
            loadingText.textContent = message;
            loadingText.style.display = 'block';
            
            requestAnimationFrame(() => {
                loadingText.style.opacity = '1';
            });
        }
        
        // Hide after delay if requested
        if (hideAfterDelay) {
            console.log('Will hide loading indicators after delay');
            setTimeout(() => {
                if (loadingBar) {
                    loadingBar.style.width = '0';
                    console.log('Setting loading bar width to 0');
                    
                    // Use both transition event and timeout as backup
                    const barTimeout = setTimeout(() => {
                        loadingBar.style.display = 'none';
                        console.log('Hiding loading bar via timeout');
                    }, 400); // Slightly longer than the transition
                    
                    loadingBar.addEventListener('transitionend', function hideLoader() {
                        clearTimeout(barTimeout);
                        loadingBar.style.display = 'none';
                        console.log('Hiding loading bar via transition');
                        loadingBar.removeEventListener('transitionend', hideLoader);
                    });
                }
                
                if (loadingText) {
                    loadingText.style.opacity = '0';
                    console.log('Setting loading text opacity to 0');
                    
                    // Use both transition event and timeout as backup
                    const textTimeout = setTimeout(() => {
                        loadingText.style.display = 'none';
                        console.log('Hiding loading text via timeout');
                    }, 400); // Slightly longer than the transition
                    
                    loadingText.addEventListener('transitionend', function hideText() {
                        clearTimeout(textTimeout);
                        loadingText.style.display = 'none';
                        console.log('Hiding loading text via transition');
                        loadingText.removeEventListener('transitionend', hideText);
                    });
                }
            }, 3000);
        }
    }
}; 