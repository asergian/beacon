// Global state for email handling
let emails = [];
let emailMap = new Map();
let isLoadingAnalysis = false;
let hasInitialized = false;
let selectedEmailId = null;
let updateEmailListTimeout = null;
let userSettings = null;
let eventSource = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 3;
const RECONNECT_DELAY = 2000; // 2 seconds
const MAX_CACHED_EMAILS = 500; // Maximum number of emails to keep in memory

// Update config with email-specific defaults
config.days_back = 1;  // Increased default to show more emails
config.batch_size = 50;  // Batch size for UI updates

// Function to fetch user settings
async function fetchUserSettings() {
    try {
        const response = await fetch('/email/api/user/settings');
        if (response.ok) {
            const data = await response.json();
            if (data.status === 'success' && data.settings) {
                userSettings = data.settings;
                // For demo mode, keep the larger days_back value
                if (!window.location.pathname.includes('demo')) {
                    config.days_back = userSettings.email_preferences.days_to_analyze;
                }
                console.log('Updated user settings:', userSettings);
            }
        }
    } catch (error) {
        console.warn('Failed to fetch user settings:', error);
    }
}

// Function to cleanup old emails
function cleanupOldEmails() {
    if (emailMap.size <= MAX_CACHED_EMAILS) return;
    
    console.log(`Cleaning up old emails (current size: ${emailMap.size})`);
    
    // Convert to array for sorting
    const emailArray = Array.from(emailMap.values());
    
    // Sort by date, newest first
    emailArray.sort((a, b) => new Date(b.date) - new Date(a.date));
    
    // Keep only the newest MAX_CACHED_EMAILS
    const emailsToKeep = emailArray.slice(0, MAX_CACHED_EMAILS);
    
    // Clear the map and add back only the emails we want to keep
    emailMap.clear();
    emailsToKeep.forEach(email => emailMap.set(email.id, email));
    
    // Clear references to removed emails
    emails = emailsToKeep;
    
    console.log(`Cleanup complete (new size: ${emailMap.size})`);
    
    // Force garbage collection if available
    if (window.gc) window.gc();
}

// Function to clear all email state
function clearEmailState() {
    console.log('Clearing email state');
    
    // Clear email data
    emails.length = 0;
    emailMap.clear();
    selectedEmailId = null;
    hasInitialized = false;
    
    // Clear UI
    clearEmailList();
    clearEmailDetails();
    
    // Force garbage collection if available
    if (window.gc) window.gc();
}

// Function to clear email details
function clearEmailDetails() {
    const detailsElements = {
        subject: document.getElementById('details-subject'),
        sender: document.getElementById('details-sender'),
        date: document.getElementById('details-date'),
        priority: document.getElementById('details-priority'),
        category: document.getElementById('details-category'),
        actionRequired: document.getElementById('details-action-required'),
        summary: document.getElementById('details-summary'),
        keyDates: document.getElementById('key-dates-list'),
        emailBody: document.getElementById('email-body')
    };
    
    Object.values(detailsElements).forEach(element => {
        if (element) {
            if (element.textContent !== undefined) element.textContent = '';
            if (element.style.display !== undefined) element.style.display = 'none';
        }
    });
    
    // Cleanup any existing iframe
    if (currentIframe) {
        currentIframe.cleanup?.();
        currentIframe.remove();
        currentIframe = null;
    }
}

// Expose the clear function globally for logout
window.clearEmailState = clearEmailState;

// Function to clear the email list in the UI
function clearEmailList() {
    const emailList = document.querySelector('.email-list');
    if (emailList) {
        emailList.innerHTML = '';
    }
}

// Function to initialize the email page
async function initializePage() {
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
    
    if (hasInitialized) {
        console.log('Page already initialized, skipping');
        return;
    }
    
    console.log('Starting fresh initialization...');
    hasInitialized = true;
    
    clearEmailState();
    await fetchUserSettings();
    
    try {
        await setupSSEConnection();
    } catch (error) {
        console.error('Error loading emails:', error);
        showError('Failed to load emails. Please try again.');
        hasInitialized = false;
    }
}

async function setupSSEConnection() {
    // Close existing connection if any
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    
    // Add connection cooldown
    const now = Date.now();
    if (window.lastSSEConnection && (now - window.lastSSEConnection) < 5000) {
        console.log('Connection attempt too soon, waiting...');
        await new Promise(resolve => setTimeout(resolve, 5000));
    }
    window.lastSSEConnection = now;
    
    try {
        // Create new EventSource with credentials
        eventSource = new EventSource('/email/api/emails/stream', {
            withCredentials: true  // Include cookies for auth
        });
        
        // Set up event handlers
        eventSource.addEventListener('connected', (event) => {
            console.log('SSE connection established');
            showLoadingBar('Loading emails...');
            reconnectAttempts = 0; // Reset reconnect counter on successful connection
        });
        
        eventSource.addEventListener('status', (event) => {
            const data = JSON.parse(event.data);
            console.log('Status update:', data.message);
            
            // Show all relevant status messages
            if (data.message.includes('Loading') || 
                data.message.includes('Found') || 
                data.message.includes('Processing') || 
                data.message.includes('Processed') || 
                data.message.includes('Analysis complete')) {
                showLoadingBar(data.message);
            }
        });
        
        eventSource.addEventListener('cached', (event) => {
            const data = JSON.parse(event.data);
            if (data.emails && data.emails.length > 0) {
                console.log(`Received ${data.emails.length} cached emails from server`);
                emailMap.clear();
                data.emails.forEach(email => emailMap.set(email.id, { ...email, isAnalyzed: true }));
                console.log(`Added ${emailMap.size} emails to email map`);
                updateEmailList();
                loadFirstEmail();
                
                const emailList = document.querySelector('.email-list');
                const emailDetails = document.getElementById('email-details');
                if (emailList) emailList.style.display = 'block';
                if (emailDetails) emailDetails.style.display = 'block';
            }
        });
        
        // Add listener for individual email events
        eventSource.addEventListener('email', (event) => {
            const data = JSON.parse(event.data);
            console.log(`Received individual email: ${data.id}`);
            
            // Add new email to map
            emailMap.set(data.id, { ...data, isAnalyzed: true });
            
            // Cleanup old emails if needed
            cleanupOldEmails();
            
            // Update UI
            updateEmailList();
            
            // Load first email if none selected yet
            if (!selectedEmailId) {
                loadFirstEmail();
            }
            
            const emailList = document.querySelector('.email-list');
            if (emailList) {
                emailList.style.display = 'block';
            }
            
            const emailDetails = document.getElementById('email-details');
            if (emailDetails) {
                emailDetails.style.display = 'block';
            }
        });
        
        eventSource.addEventListener('batch', (event) => {
            const data = JSON.parse(event.data);
            if (data.emails && data.emails.length > 0) {
                console.log(`Received batch of ${data.emails.length} analyzed emails`);
                
                // Add new emails to map
                data.emails.forEach(email => emailMap.set(email.id, { ...email, isAnalyzed: true }));
                
                // Cleanup old emails if needed
                cleanupOldEmails();
                
                // Update UI
                updateEmailList();
                
                // Load first email if none selected yet
                if (!selectedEmailId) {
                    loadFirstEmail();
                }
                
                const emailList = document.querySelector('.email-list');
                if (emailList) {
                    emailList.style.display = 'block';
                }
                
                const emailDetails = document.getElementById('email-details');
                if (emailDetails) {
                    emailDetails.style.display = 'block';
                }
            }
        });
        
        // Add listener for complete event
        eventSource.addEventListener('complete', (event) => {
            const data = JSON.parse(event.data);
            console.log('Processing complete:', data);
            
            // Display final processing stats
            const processed = data.processed || 0;
            const cached = data.cached || 0;
            const total = data.total || 0;
            
            // Show the completion message
            showLoadingBar(`Processing complete. Total emails: ${total} (${cached} cached, ${processed} new)`);
            setTimeout(() => {
                hideLoadingBar();
            }, 3000);
            
            // Ensure email list is visible
            const emailList = document.querySelector('.email-list');
            if (emailList) {
                emailList.style.display = 'block';
            }
            
            // Mark initialization as complete
            hasInitialized = true;
            
            // Close SSE connection
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
        });
        
        eventSource.addEventListener('stats', (event) => {
            const stats = JSON.parse(event.data);
            console.log('Processing complete:', stats);
            hideLoadingBar();
            
            // Ensure email list is visible
            const emailList = document.querySelector('.email-list');
            if (emailList) {
                emailList.style.display = 'block';
            }
            
            // Mark initialization as complete before closing
            hasInitialized = true;
            
            // Close SSE connection
            eventSource.close();
            eventSource = null;
        });
        
        eventSource.addEventListener('close', (event) => {
            console.log('Server closed connection (no more emails to process)');
            hasInitialized = true;
            hideLoadingBar();  // Hide loading bar when connection closes

            eventSource.close();
            eventSource = null;
        });
        
        eventSource.addEventListener('error', async (event) => {
            console.error('SSE error:', event);
            const target = event.target;
            
            // If we're already initialized, don't attempt to reconnect
            if (hasInitialized) {
                console.log('Connection closed after successful initialization');
                return;
            }
            
            // Check if we never connected or if the connection was closed
            if (target.readyState === EventSource.CONNECTING) {
                console.log('Connection attempting to establish...');
                return; // Still trying to connect, let it try
            }
            
            if (target.readyState === EventSource.CLOSED) {
                console.log('SSE connection closed');
                
                // If we never got a successful connection, check SSL
                if (!hasInitialized && window.location.protocol === 'https:') {
                    hideLoadingBar();
                    showError('Security certificate issue detected. Please accept the certificate warning if shown, then refresh the page.');
                    return;
                }
                
                // Attempt to reconnect if under max attempts
                if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                    reconnectAttempts++;
                    console.log(`Attempting to reconnect (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`);
                    
                    // Wait before reconnecting
                    await new Promise(resolve => setTimeout(resolve, RECONNECT_DELAY));
                    
                    try {
                        await setupSSEConnection();
                    } catch (error) {
                        console.error('Reconnection failed:', error);
                        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
                            hideLoadingBar();
                            showError('Connection lost. Please refresh the page to try again.');
                            hasInitialized = false;
                        }
                    }
                } else {
                    hideLoadingBar();
                    showError('Connection lost. Please refresh the page to try again.');
                    hasInitialized = false;
                }
            }
        });
        
        // Return a promise that resolves when connected or rejects on error
        return new Promise((resolve, reject) => {
            let hasResolved = false;
            
            // Set up multiple timeouts for different stages
            const timeouts = [
                { time: 5000, message: 'Initial connection timeout' },
                { time: 15000, message: 'Cache check timeout' },
                { time: 45000, message: 'Analysis timeout' }
            ];
            
            let currentTimeout = null;
            
            function setupNextTimeout(index) {
                if (index >= timeouts.length) return;
                
                currentTimeout = setTimeout(() => {
                    // Only timeout if we haven't received any data
                    if (!hasResolved) {
                        if (eventSource) {
                            eventSource.close();
                        }
                        reject(new Error(timeouts[index].message));
                    }
                }, timeouts[index].time);
            }
            
            // Start the first timeout
            setupNextTimeout(0);
            
            // Listen for successful connection
            eventSource.addEventListener('connected', () => {
                console.log('Connected to SSE');
                clearTimeout(currentTimeout);
                setupNextTimeout(1);
            });
            
            // Listen for cache status
            eventSource.addEventListener('status', (event) => {
                const data = JSON.parse(event.data);
                console.log('Status:', data.message);
                
                if (data.message.includes('Starting email analysis')) {
                    clearTimeout(currentTimeout);
                    setupNextTimeout(2);
                }
            });
            
            // Listen for successful data
            const successEvents = ['cached', 'batch', 'stats'];
            successEvents.forEach(eventName => {
                eventSource.addEventListener(eventName, () => {
                    if (!hasResolved) {
                        hasResolved = true;
                        clearTimeout(currentTimeout);
                        resolve();
                    }
                });
            });
            
            // Listen for errors
            eventSource.addEventListener('error', (event) => {
                if (!hasResolved && event.target.readyState === EventSource.CLOSED) {
                    hasResolved = true;
                    clearTimeout(currentTimeout);
                    reject(new Error('Connection failed'));
                }
            });
        });
        
    } catch (error) {
        console.error('Connection setup failed:', error);
        hideLoadingBar();
        showError('Failed to connect. Please refresh the page to try again.');
        throw error;
    }
}

// Load email analysis results
async function loadEmailAnalysis() {
    if (isLoadingAnalysis) return;
    isLoadingAnalysis = true;
    
    showLoadingBar('Analyzing emails...');
    
    try {
        const response = await fetch(`/email/api/emails/analysis?days_back=${config.days_back}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success' && data.emails) {
            emailMap.clear();
            data.emails.forEach(email => {
                emailMap.set(email.id, {
                    ...email,
                    isAnalyzed: true
                });
            });
        } else {
            throw new Error(data.message || 'Failed to load email analysis');
        }
    } catch (error) {
        console.error('Error loading email analysis:', error);
        showError('Failed to analyze emails. ' + error.message);
    } finally {
        isLoadingAnalysis = false;
        hideLoadingBar();
    }
}

// Batch update helper
function batchUpdate(updates, batchSize = 50) {
    let batch = [];
    return new Promise((resolve) => {
        updates.forEach((update, index) => {
            batch.push(update);
            if (batch.length === batchSize || index === updates.length - 1) {
                setTimeout(() => {
                    batch.forEach(fn => fn());
                    batch = [];
                    if (index === updates.length - 1) resolve();
                }, 0);
            }
        });
    });
}

// Optimized email list update
function updateEmailList() {
    if (updateEmailListTimeout) {
        clearTimeout(updateEmailListTimeout);
    }

    updateEmailListTimeout = setTimeout(() => {
        console.log('Updating email list...');
        const emailList = document.querySelector('.email-list');
        if (!emailList) return;
        
        // Clear existing content
        emailList.innerHTML = '';
        
        const fragment = document.createDocumentFragment();
        const uniqueEmails = new Map(Array.from(emailMap.entries()));
        console.log(`Total emails in map before filtering: ${uniqueEmails.size}`);
        
        const sortedEmails = Array.from(uniqueEmails.values())
            .filter(email => {
                // Special handling for demo mode - show all emails
                const isDemo = emailMap.get(email.id)?.id?.startsWith('demo');
                // if (isDemo) {
                //     return true;
                // }
                const emailDate = new Date(email.date);
                const now = new Date();
                const daysDiff = Math.floor((now - emailDate) / (1000 * 60 * 60 * 24));
                return daysDiff <= config.days_back;
            })
            .sort((a, b) => {
                if (a.needs_action !== b.needs_action) {
                    return a.needs_action ? -1 : 1;
                }
                const priorityOrder = { 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1 };
                const aPriority = priorityOrder[a.priority_level] || 0;
                const bPriority = priorityOrder[b.priority_level] || 0;
                if (aPriority !== bPriority) {
                    return bPriority - aPriority;
                }
                return new Date(b.date) - new Date(a.date);
            });
        
        console.log(`Emails after filtering and sorting: ${sortedEmails.length}`);
        
        // Log the first few emails for debugging
        console.log('First few emails:', sortedEmails.slice(0, 3).map(e => ({
            id: e.id,
            subject: e.subject,
            date: e.date,
            needs_action: e.needs_action,
            priority_level: e.priority_level
        })));

        sortedEmails.forEach(email => {
            const li = document.createElement('li');
            li.className = `email-item ${!email.isAnalyzed ? 'analyzing' : ''}`;
            li.dataset.emailId = email.id;
            
            // Add click handler
            li.addEventListener('click', () => {
                document.querySelectorAll('.email-item').forEach(item => item.classList.remove('active'));
                li.classList.add('active');
                selectedEmailId = email.id;
                loadEmailDetails(email.id);
            });

            if (email.needs_action) {
                li.classList.add('needs-action');
            }
            
            if (email.id === selectedEmailId) {
                li.classList.add('active');
            }
            
            const formatTagText = (text) => {
                if (text === null || text === undefined) return '';
                // Convert to string and ensure proper case
                text = String(text);
                return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
            };
            
            // Get custom category colors from user settings
            const customCategoriesConfig = userSettings?.ai_features?.custom_categories || [];
            const customCategoriesHtml = email.custom_categories ? 
                Object.entries(email.custom_categories)
                    .filter(([name, value]) => value !== null)
                    .map(([name, value]) => {
                        const categoryConfig = customCategoriesConfig.find(c => c.name === name);
                        const color = categoryConfig?.color || '#8B5CF6';
                        return `<span class="tag custom-category" data-category="${name}" style="background-color: ${color}">${formatTagText(value)}</span>`;
                    }).join('') : '';
    
            li.innerHTML = `
                <div class="email-header">
                    <span class="email-subject">${email.subject || 'No Subject'}</span>
                    <div class="tags-container">
                        <span class="tag priority-${(email.priority_level || 'pending').toLowerCase()}">${formatTagText(email.priority_level) || 'Pending'}</span>
                        <span class="tag category" data-category="${email.category || 'Informational'}">${formatTagText(email.category) || 'Pending'}</span>
                        ${email.needs_action ? '<span class="tag action-required">Action Required</span>' : ''}
                        ${customCategoriesHtml}
                    </div>
                </div>
                <span class="sender-name">${(email.sender || '').split('<')[0].trim() || 'Unknown Sender'}</span>
                <p class="email-summary-preview">${email.summary || 'Analysis in progress...'}</p>
            `;
            
            fragment.appendChild(li);
        });

        emailList.appendChild(fragment);
        console.log(`Added ${sortedEmails.length} emails to the UI`);
        
        // If we have emails but none selected, select the first one
        if (sortedEmails.length > 0 && !selectedEmailId) {
            selectedEmailId = sortedEmails[0].id;
            loadEmailDetails(sortedEmails[0].id);
            const firstItem = emailList.querySelector('.email-item');
            if (firstItem) {
                firstItem.classList.add('active');
            }
        }
    }, 100);
}

// Optimized email details loading with debounced resize observer
let currentIframe = null;
let resizeTimeout = null;

function loadEmailDetails(emailId) {
    const email = emailMap.get(emailId);
    if (!email) return;
    
    const detailsElements = {
        subject: document.getElementById('details-subject'),
        sender: document.getElementById('details-sender'),
        date: document.getElementById('details-date'),
        priority: document.getElementById('details-priority'),
        category: document.getElementById('details-category'),
        actionRequired: document.getElementById('details-action-required'),
        customCategories: document.getElementById('details-custom-categories'),
        summary: document.getElementById('details-summary'),
        keyDates: document.getElementById('key-dates-list'),
        emailBody: document.getElementById('email-body')
    };
    
    // Show all detail elements
    Object.values(detailsElements).forEach(element => {
        if (element) {
            element.style.display = 'block';
        }
    });
    
    const formatTagText = (text) => {
        if (text === null || text === undefined) return '';
        // Convert to string and ensure proper case
        text = String(text);
        return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
    };
    
    requestAnimationFrame(() => {
        detailsElements.subject.textContent = email.subject || 'No Subject';
        detailsElements.sender.textContent = email.sender || 'Unknown Sender';
        detailsElements.date.textContent = email.date ? new Date(email.date).toLocaleString() : 'Unknown Date';
        
        const priorityLevel = (email.priority_level || 'pending').toLowerCase();
        detailsElements.priority.textContent = formatTagText(email.priority_level || 'pending');
        detailsElements.priority.className = `tag priority-${priorityLevel}`;
        
        detailsElements.category.textContent = formatTagText(email.category || 'uncategorized');
        detailsElements.category.setAttribute('data-category', email.category || 'Informational');
        
        if (email.needs_action) {
            detailsElements.actionRequired.textContent = 'Action Required';
            detailsElements.actionRequired.style.display = 'inline-flex';
        } else {
            detailsElements.actionRequired.style.display = 'none';
        }
        
        // Handle custom categories with colors from user settings
        if (email.custom_categories && Object.keys(email.custom_categories).length > 0) {
            const customCategoriesConfig = userSettings?.ai_features?.custom_categories || [];
            detailsElements.customCategories.innerHTML = Object.entries(email.custom_categories)
                .filter(([name, value]) => value !== null)
                .map(([name, value]) => {
                    const categoryConfig = customCategoriesConfig.find(c => c.name === name);
                    const color = categoryConfig?.color || '#8B5CF6';  // Default to purple if no color set
                    return `<span class="tag custom-category" data-category="${name}" style="background-color: ${color}">${formatTagText(value)}</span>`;
                })
                .join('');
            detailsElements.customCategories.style.display = 'inline-flex';
        } else {
            detailsElements.customCategories.style.display = 'none';
        }
        
        detailsElements.summary.textContent = email.summary || 'No summary available';
        
        if (email.action_items && Array.isArray(email.action_items)) {
            const fragment = document.createDocumentFragment();
            email.action_items.forEach(item => {
                if (item && item.description) {
                    const li = document.createElement('li');
                    if (item.due_date && item.due_date.toLowerCase() !== 'null') {
                        li.innerHTML = `${item.description}<span class="due-date">Due: ${item.due_date}</span>`;
                    } else {
                        li.textContent = item.description;
                    }
                    fragment.appendChild(li);
                }
            });
            detailsElements.keyDates.innerHTML = '';
            detailsElements.keyDates.appendChild(fragment);
            detailsElements.keyDates.style.display = 'block';
        } else {
            detailsElements.keyDates.innerHTML = '';
            detailsElements.keyDates.style.display = 'none';
        }
    });
    
    if (email.body) {
        detailsElements.emailBody.style.display = 'block';
        if (currentIframe) {
            currentIframe.cleanup?.();
            currentIframe.remove();
        }
        
        const iframe = document.createElement('iframe');
        iframe.className = 'email-body-frame';
        iframe.style.width = '100%';
        iframe.style.border = 'none';
        iframe.style.overflow = 'hidden';
        iframe.scrolling = 'no'; // Disable scrolling
        iframe.height = '500px'; // Initial height, will be adjusted
        
        // Replace the old iframe if it exists
        const oldIframe = detailsElements.emailBody.querySelector('iframe');
        if (oldIframe) {
            if (oldIframe.cleanup) {
                oldIframe.cleanup();
            }
            detailsElements.emailBody.removeChild(oldIframe);
        }
        
        // Append the new iframe
        detailsElements.emailBody.appendChild(iframe);
        
        // Get the document inside the iframe
        const doc = iframe.contentWindow.document;
        
        // Create more secure body content by replacing http:// with https://
        // This ensures all resources are loaded securely to prevent mixed content warnings
        let secureBody = email.body.replace(/http:\/\//g, 'https://');
        
        // Write the HTML template to the iframe
        // We use a complete HTML document with proper meta tags and styles
        // to ensure consistent rendering and proper security policies
        doc.open();
        doc.write(`
            <!DOCTYPE html>
            <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <base target="_blank">
                    <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
                    <style>
                        body {
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                            line-height: 1.5;
                            background-color: white;
                        }
                        pre, code {
                            white-space: pre-wrap;
                            overflow-wrap: break-word;
                        }
                    </style>
                </head>
                <body>${secureBody}</body>
            </html>
        `);
        doc.close();
        
        // Keep track of whether we've finalized height
        let heightFinalized = false;
        
        // Function to set iframe height once
        const setFinalHeight = () => {
            if (heightFinalized) return;
            
            const bodyEl = iframe.contentWindow.document.body;
            const docEl = iframe.contentWindow.document.documentElement;
            
            // Get the maximum height considering all content
            const finalHeight = Math.max(
                bodyEl.scrollHeight,
                bodyEl.offsetHeight,
                docEl.clientHeight,
                docEl.scrollHeight,
                docEl.offsetHeight
            );
            
            // Only set height if it's reasonable
            if (finalHeight > 100) {
                iframe.style.height = (finalHeight + 50) + 'px'; // Add more padding to prevent scrollbars
                heightFinalized = true;
            }
        };
        
        // Initial height setting
        setTimeout(setFinalHeight, 100);
        
        // Setup for handling images
        iframe.onload = () => {
            const images = iframe.contentWindow.document.querySelectorAll('img');
            
            if (images.length > 0) {
                let loadedImages = 0;
                const totalImages = images.length;
                
                // Function to check if all images are loaded
                const checkAllImagesLoaded = () => {
                    loadedImages++;
                    if (loadedImages >= totalImages) {
                        // All images loaded, set final height
                        setTimeout(setFinalHeight, 200);
                    }
                };
                
                // Set up load handlers for each image
                images.forEach(img => {
                    if (img.complete) {
                        checkAllImagesLoaded();
                    } else {
                        img.onload = checkAllImagesLoaded;
                        img.onerror = checkAllImagesLoaded;
                    }
                });
                
                // Safety timeout in case some images never load
                setTimeout(setFinalHeight, 2000);
            } else {
                // No images, set height immediately
                setTimeout(setFinalHeight, 100);
            }
        };
        
        // Keep a reference to the current iframe for cleanup
        currentIframe = iframe;
        currentIframe.cleanup = () => {
            // Clear any event listeners if needed
            if (iframe.contentWindow) {
                const images = iframe.contentWindow.document.querySelectorAll('img');
                images.forEach(img => {
                    img.onload = null;
                    img.onerror = null;
                });
            }
        };
    }
}

// Filter emails
function filterEmails() {
    const priorityFilter = document.getElementById('priority-filter').value;
    const categoryFilter = document.getElementById('category-filter').value;
    const actionFilter = document.getElementById('action-filter').value;
    
    document.querySelectorAll('.email-item').forEach(item => {
        const email = emailMap.get(item.dataset.emailId);
        if (!email) return;
        
        const matchesPriority = priorityFilter === 'all' || 
                              email.priority_level.toLowerCase() === priorityFilter.toLowerCase();
        const matchesCategory = categoryFilter === 'all' || 
                              email.category.toLowerCase() === categoryFilter.toLowerCase();
        const matchesAction = actionFilter === 'all' || 
                            (actionFilter === 'required' && email.needs_action) ||
                            (actionFilter === 'none' && !email.needs_action);
        
        item.style.display = matchesPriority && matchesCategory && matchesAction ? 'block' : 'none';
    });
}

function updateLoadingText(stage) {
    const loadingText = document.getElementById('loading-text');
    if (!loadingText) return;
    
    let message = '';
    
    // If stage is a pre-defined key, use mapped message
    switch(stage) {
        case 'fetch':
            message = 'Fetching emails...';
            break;
        case 'parse':
            message = 'Parsing email content...';
            break;
        case 'analyze':
            message = 'Analyzing emails...';
            break;
        case 'cache':
            message = 'Loading cached emails...';
            break;
        default:
            // If it's not a pre-defined stage, use the text directly
            message = 'Loading...';
    }
    
    loadingText.classList.add('stage-change');
    loadingText.textContent = message;
    
    setTimeout(() => {
        loadingText.classList.remove('stage-change');
    }, 300);
}

function loadFirstEmail() {
    const firstEmail = Array.from(emailMap.values())[0];
    if (firstEmail) {
        selectedEmailId = firstEmail.id;
        loadEmailDetails(firstEmail.id);
        
        // Ensure the first email is marked as selected in the list
        const firstEmailElement = document.querySelector(`.email-item[data-email-id="${firstEmail.id}"]`);
        if (firstEmailElement) {
            document.querySelectorAll('.email-item').forEach(item => item.classList.remove('active'));
            firstEmailElement.classList.add('active');
        }
        
        // Ensure email details are visible
        const emailDetails = document.getElementById('email-details');
        if (emailDetails) {
            emailDetails.style.display = 'block';
        }
    }
}

// Initialize the page when DOM is loaded
document.addEventListener('DOMContentLoaded', initializePage); 