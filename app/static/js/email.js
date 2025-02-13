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

// Update config with email-specific defaults
config.days_back = 1;  // Default value, will be updated from user settings
config.batch_size = 50;  // Batch size for UI updates

// Function to fetch user settings
async function fetchUserSettings() {
    try {
        const response = await fetch('/email/api/user/settings');
        if (response.ok) {
            const data = await response.json();
            if (data.status === 'success' && data.settings) {
                userSettings = data.settings;
                config.days_back = userSettings.email_preferences.days_to_analyze;
                console.log('Updated user settings:', userSettings);
            }
        }
    } catch (error) {
        console.warn('Failed to fetch user settings:', error);
    }
}

// Function to clear all email state
function clearEmailState() {
    console.log('Clearing email state');
    emails = [];
    emailMap.clear();
    selectedEmailId = null;
    hasInitialized = false;
    clearEmailList();
    
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
    
    console.log('Initializing email summary page...');
    hasInitialized = true;
    
    clearEmailState();
    
    await fetchUserSettings();
    
    emailList.innerHTML = '';
    emailDetails.style.display = 'none';
    
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
                console.log(`Received ${data.emails.length} cached emails`);
                emailMap.clear();
                data.emails.forEach(email => emailMap.set(email.id, { ...email, isAnalyzed: true }));
                updateEmailList();
                loadFirstEmail();
                
                const emailList = document.querySelector('.email-list');
                const emailDetails = document.getElementById('email-details');
                if (emailList) emailList.style.display = 'block';
                if (emailDetails) emailDetails.style.display = 'block';
            }
        });
        
        eventSource.addEventListener('batch', (event) => {
            const data = JSON.parse(event.data);
            if (data.emails && data.emails.length > 0) {
                console.log(`Received batch of ${data.emails.length} analyzed emails`);
                data.emails.forEach(email => emailMap.set(email.id, { ...email, isAnalyzed: true }));
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
                        eventSource.close();
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
        const emailList = document.querySelector('.email-list');
        if (!emailList) return;
        
        // Clear existing content
        emailList.innerHTML = '';
        
        const fragment = document.createDocumentFragment();
        const uniqueEmails = new Map(Array.from(emailMap.entries()));
        
        const sortedEmails = Array.from(uniqueEmails.values())
            .filter(email => {
                const emailDate = new Date(email.date);
                const now = new Date();
                const daysDiff = Math.floor((now - emailDate) / (1000 * 60 * 60 * 24));
                return daysDiff <= config.days_back;
            })
            .sort((a, b) => {
                if (a.needs_action !== b.needs_action) {
                    return b.needs_action ? 1 : -1;
                }
                const priorityOrder = { 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1 };
                const aPriority = priorityOrder[a.priority_level] || 0;
                const bPriority = priorityOrder[b.priority_level] || 0;
                if (aPriority !== bPriority) {
                    return bPriority - aPriority;
                }
                return new Date(b.date) - new Date(a.date);
            });
        
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
                if (!text) return '';
                return text.toLowerCase().split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
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
        if (!text) return '';
        return text.toLowerCase().split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
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
        iframe.style.cssText = 'width: 100%; border: none; min-height: 100px;';
        detailsElements.emailBody.appendChild(iframe);
        
        const secureBody = email.body.replace(
            /(http:\/\/[^"']*)/gi,
            (match) => match.replace('http://', 'https://')
        );
        
        const doc = iframe.contentWindow.document;
        doc.open();
        doc.write(`
            <html>
                <head>
                    <base target="_blank">
                    <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
                    <style>
                        body {
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                            margin: 0;
                            padding: 16px;
                            color: #333;
                            overflow: hidden;
                        }
                        img { max-width: 100%; height: auto; }
                        a { color: #0366d6; }
                        a:visited { color: #6f42c1; }
                    </style>
                </head>
                <body>${secureBody}</body>
            </html>
        `);
        doc.close();
        
        const resizeObserver = new ResizeObserver(() => {
            if (resizeTimeout) {
                clearTimeout(resizeTimeout);
            }
            resizeTimeout = setTimeout(() => {
                const newHeight = iframe.contentWindow.document.body.scrollHeight;
                if (newHeight > 100) {
                    iframe.style.height = newHeight + 'px';
                }
            }, 100);
        });
        
        resizeObserver.observe(iframe.contentWindow.document.body);
        currentIframe = iframe;
        
        iframe.cleanup = () => {
            resizeObserver.disconnect();
            if (resizeTimeout) {
                clearTimeout(resizeTimeout);
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