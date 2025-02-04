// Global state
let emails = [];
let emailMap = new Map();
//let isLoadingMetadata = false;
let isLoadingAnalysis = false;
let hasInitialized = false;  // Add initialization flag

// Configuration
const config = {
    days_back: 0,  // Number of days to fetch emails for
    batch_size: 50  // Batch size for UI updates
};

// Track currently selected email
let selectedEmailId = null;

// Add this at the top with other global variables
let updateEmailListTimeout = null;

// Function to clear all email state
function clearEmailState() {
    console.log('Clearing email state');
    emails = [];
    emailMap.clear();
    selectedEmailId = null;
    hasInitialized = false;  // Reset initialization flag
    clearEmailList();
    
    // Clear any existing email details
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
    
    // Clear details if elements exist
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
    console.log('Number of emails before clearing:', document.querySelectorAll('.email-list .email-item').length); // Log the number of items
    const emailList = document.querySelector('.email-list');
    emailList.innerHTML = ''; // Clear the existing email list
}

// Initialize the page and start loading data
async function initializePage() {
    if (hasInitialized) {
        console.log('Page already initialized, skipping');
        return;
    }
    
    console.log('Initializing page...');
    hasInitialized = true;
    
    // Clear any existing state
    clearEmailState();
    hasInitialized = true;  // Set again after clear
    
    // Show loading states initially
    document.getElementById('email-list-loading').style.display = 'flex';
    document.getElementById('details-loading').style.display = 'flex';
    
    updateLoadingText('fetch');

    try {
        // Load and analyze emails in one step
        updateLoadingText('analyze');
        await loadEmailAnalysis();
        
        // Update both email list and details after fresh data
        updateEmailList();
        loadFirstEmail();
        
    } catch (error) {
        console.error('Error loading emails:', error);
        showError('Failed to load emails. Please try again.');
        hasInitialized = false;  // Reset on error
    } finally {
        document.getElementById('email-list-loading').style.display = 'none';
        document.getElementById('details-loading').style.display = 'none';
    }
}

// Show/hide loading bar
function showLoadingBar(text) {
    const loadingBar = document.getElementById('loading-bar');
    const loadingText = document.getElementById('loading-text');
    
    // Force a reflow to restart animation
    loadingBar.classList.remove('visible');
    void loadingBar.offsetWidth;
    
    loadingBar.classList.add('visible');
    loadingText.textContent = text || 'Loading...';
    loadingText.classList.add('visible');
    
    console.log('Loading indicators shown:', text);
}

function hideLoadingBar() {
    if (isLoadingAnalysis) {
        console.log('Still loading, keeping indicators visible');
        return; // Don't hide if still loading
    }
    
    const loadingBar = document.getElementById('loading-bar');
    const loadingText = document.getElementById('loading-text');
    
    loadingBar.classList.remove('visible');
    loadingText.classList.remove('visible');
    
    console.log('Loading indicators hidden');
}

function showError(message) {
    console.error('Showing error:', message);
    hideLoadingBar();
    const errorDiv = document.getElementById('error-message');
    const errorText = document.getElementById('error-text');
    errorText.textContent = message;
    errorDiv.style.display = 'flex';
    
    // Auto-hide error after 5 seconds
    setTimeout(() => {
        errorDiv.style.display = 'none';
    }, 5000);
}

function hideError() {
    document.getElementById('error-message').style.display = 'none';
}

async function retryLoading() {
    console.log('Retrying loading...');
    hideError();
    await initializePage();
}

// // Load basic email metadata
// async function loadEmailMetadata() {
//     if (isLoadingMetadata) return;
//     isLoadingMetadata = true;
    
//     showLoadingBar('Loading email metadata...');
//     updateLoadingText('parse');
//     console.log('Loading email metadata with days_back:', config.days_back);
    
//     try {
//         const response = await fetch(`/email/api/emails/metadata?days_back=${config.days_back}`);
//         if (!response.ok) {
//             throw new Error(`HTTP error! status: ${response.status}`);
//         }
//         const data = await response.json();
        
//         if (data.status === 'success') {
//             console.log('Received metadata for', data.emails.length, 'emails');
//             console.log('Current emailMap size before clearing:', emailMap.size);
            
//             // Clear existing emails before adding new ones
//             emailMap.clear();
//             console.log('EmailMap size after clearing:', emailMap.size);
            
//             // Add new emails and update UI immediately
//             data.emails.forEach(email => {
//                 const emailDate = new Date(email.date);
//                 const now = new Date();
//                 const daysDiff = Math.floor((now - emailDate) / (1000 * 60 * 60 * 24));
//                 console.log(`Email ${email.id} date: ${emailDate}, days old: ${daysDiff}`);
                
//                 if (daysDiff <= config.days_back) {
//                     emailMap.set(email.id, {
//                         ...email,
//                         isAnalyzed: false,
//                         priority_level: 'pending',
//                         category: 'pending',
//                         summary: 'Analysis in progress...'
//                     });
//                 } else {
//                     console.log(`Skipping email ${email.id} as it's older than ${config.days_back} days`);
//                 }
//             });
            
//             console.log('EmailMap size after adding new emails:', emailMap.size);
            
//             // Update UI immediately with unanalyzed emails
//             clearEmailList();
//             updateEmailList();
//             loadFirstEmail();
            
//             // Keep loading indicator visible for analysis
//             document.getElementById('email-list-loading').style.display = 'flex';
//         } else {
//             throw new Error(data.message || 'Failed to load email metadata');
//         }
//     } catch (error) {
//         console.error('Error loading email metadata:', error);
//         showError('Failed to load email metadata. ' + error.message);
//     } finally {
//         isLoadingMetadata = false;
//         hideLoadingBar();
//     }
// }

// Load email analysis results
async function loadEmailAnalysis() {
    if (isLoadingAnalysis) return;
    isLoadingAnalysis = true;
    
    showLoadingBar('Analyzing emails...');
    console.log('Loading email analysis with days_back:', config.days_back);
    
    try {
        const response = await fetch(`/email/api/emails/analysis?days_back=${config.days_back}`);
        console.log('Analysis response status:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Analysis response error:', errorText);
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Analysis response data:', data);
        
        if (data.status === 'success' && data.emails) {
            console.log('Received analysis for', data.emails.length, 'emails');
            console.log('Current emailMap size before analysis:', emailMap.size);
            
            // Clear existing emails before adding new ones
            emailMap.clear();
            
            // Add analyzed emails to the map
            data.emails.forEach(email => {
                emailMap.set(email.id, {
                    ...email,
                    isAnalyzed: true
                });
            });
            
            console.log('EmailMap size after adding analyzed emails:', emailMap.size);
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
        console.log('Debouncing updateEmailList call');
        clearTimeout(updateEmailListTimeout);
    }

    updateEmailListTimeout = setTimeout(() => {
        console.log('Updating email list UI');
        const emailList = document.querySelector('.email-list');
        emailList.innerHTML = '';
        
        const fragment = document.createDocumentFragment();
        const uniqueEmails = new Map(Array.from(emailMap.entries()));
        console.log('Number of unique emails:', uniqueEmails.size);
        
        const sortedEmails = Array.from(uniqueEmails.values())
            .filter(email => {
                const emailDate = new Date(email.date);
                const now = new Date();
                const daysDiff = Math.floor((now - emailDate) / (1000 * 60 * 60 * 24));
                const isWithinRange = daysDiff <= config.days_back;
                if (!isWithinRange) {
                    console.log(`Filtering out email ${email.id} as it's ${daysDiff} days old`);
                }
                return isWithinRange;
            })
            .sort((a, b) => {
                if (a.needs_action !== b.needs_action) {
                    return b.needs_action ? 1 : -1;
                }
                const aPriority = a.priority || 0;
                const bPriority = b.priority || 0;
                if (aPriority !== bPriority) {
                    return bPriority - aPriority;
                }
                return new Date(b.date) - new Date(a.date);
            });

        console.log(`Rendering ${sortedEmails.length} filtered emails`);
        
        const updates = sortedEmails.map(email => () => {
            const li = document.createElement('li');
            li.className = `email-item ${!email.isAnalyzed ? 'analyzing' : ''}`;
            li.dataset.emailId = email.id;
            li.onclick = () => {
                selectedEmailId = email.id;
                loadEmailDetails(email.id);
            };

            if (email.id === selectedEmailId) {
                li.classList.add('active');
            }

            if (email.needs_action) {
                li.classList.add('needs-action');
            }

            const formatTagText = (text) => {
                if (!text) return '';
                return text.toLowerCase().split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
            };

            li.innerHTML = `
                <div class="email-header">
                    <span class="email-subject">${email.subject || 'No Subject'}</span>
                    <div class="tags-container">
                        <span class="tag priority-${(email.priority_level || 'pending').toLowerCase()}">${formatTagText(email.priority_level) || 'Pending'}</span>
                        <span class="tag category">${formatTagText(email.category) || 'Pending'}</span>
                        ${email.needs_action ? '<span class="tag action-required">Action Required</span>' : ''}
                    </div>
                </div>
                <span class="sender-name">${(email.sender || '').split('<')[0].trim() || 'Unknown Sender'}</span>
                <p class="email-summary-preview">${email.summary || 'Analysis in progress...'}</p>
            `;
            fragment.appendChild(li);
            return li;
        });

        batchUpdate(updates, 50).then(() => {
            emailList.appendChild(fragment);
            if (sortedEmails.length > 0 && !selectedEmailId) {
                selectedEmailId = sortedEmails[0].id;
                loadEmailDetails(sortedEmails[0].id);
            }
        });
    }, 100);
}

// Optimized email details loading with debounced resize observer
let currentIframe = null;
let resizeTimeout = null;

function loadEmailDetails(emailId) {
    console.log('Render email:', emailId);
    const email = emailMap.get(emailId);
    if (!email) {
        console.warn('No email found for ID:', emailId);
        return;
    }
    
    console.log('Email data:', email);
    
    // Cache and verify DOM elements
    const detailsElements = {
        subject: document.getElementById('details-subject'),
        sender: document.getElementById('details-sender'),
        date: document.getElementById('details-date'),
        priority: document.getElementById('details-priority'),
        category: document.getElementById('details-category'),
        actionRequired: document.getElementById('details-action-required'),
        summary: document.getElementById('details-summary'),
        keyDates: document.getElementById('key-dates-list'),
        loading: document.getElementById('details-loading'),
        emailBody: document.getElementById('email-body')
    };
    
    // Debug element existence and visibility
    Object.entries(detailsElements).forEach(([key, element]) => {
        if (!element) {
            console.error(`Missing element: ${key}`);
        } else {
            const styles = window.getComputedStyle(element);
            console.log(`Element ${key}:`, {
                exists: true,
                display: styles.display,
                visibility: styles.visibility,
                opacity: styles.opacity,
                parent: element.parentElement?.id || 'unknown parent'
            });
        }
    });
    
    // Show/hide loading state
    detailsElements.loading.style.display = !email.isAnalyzed ? 'flex' : 'none';
    
    // Show all detail elements if email is analyzed
    if (email.isAnalyzed) {
        Object.entries(detailsElements).forEach(([key, element]) => {
            if (element && key !== 'loading' && key !== 'actionRequired') {
                element.style.display = 'block';
            }
        });
        
        // Special handling for action required tag
        if (detailsElements.actionRequired) {
            detailsElements.actionRequired.style.display = email.needs_action ? 'inline-flex' : 'none';
        }
    }
    
    // Helper function to format tag text
    const formatTagText = (text) => {
        if (!text) return '';
        return text.toLowerCase().split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
    };
    
    // Batch DOM updates
    requestAnimationFrame(() => {
        console.log('Starting DOM updates...');
        
        // Update content
        detailsElements.subject.textContent = email.subject || 'No Subject';
        detailsElements.sender.textContent = email.sender || 'Unknown Sender';
        detailsElements.date.textContent = email.date ? new Date(email.date).toLocaleString() : 'Unknown Date';
        
        // Handle priority level
        const priorityLevel = (email.priority_level || 'pending').toLowerCase();
        detailsElements.priority.textContent = formatTagText(email.priority_level || 'pending');
        detailsElements.priority.className = `tag priority-${priorityLevel}`;
        
        // Handle category
        detailsElements.category.textContent = formatTagText(email.category || 'uncategorized');
        
        // Handle action required
        if (email.needs_action) {
            detailsElements.actionRequired.textContent = 'Action Required';
            detailsElements.actionRequired.style.display = 'inline-flex';
        } else {
            detailsElements.actionRequired.style.display = 'none';
        }
        
        // Update summary and key dates
        detailsElements.summary.textContent = email.summary || 'No summary available';
        
        // Handle action items
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
    
    // Handle email body iframe
    if (email.body) {
        detailsElements.emailBody.style.display = 'block';
        if (currentIframe) {
            currentIframe.cleanup?.();
            currentIframe.remove();
        }
        
        const iframe = document.createElement('iframe');
        iframe.style.cssText = 'width: 100%; border: none; min-height: 100px;';
        detailsElements.emailBody.appendChild(iframe);
        
        // Convert any HTTP URLs to HTTPS in the email body
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
        
        // Debounced resize observer
        const resizeObserver = new ResizeObserver(() => {
            if (resizeTimeout) {
                clearTimeout(resizeTimeout);
            }
            resizeTimeout = setTimeout(() => {
                const newHeight = iframe.contentWindow.document.body.scrollHeight;
                if (newHeight > 100) { // Only update if height is significant
                    iframe.style.height = newHeight + 'px';
                }
            }, 100); // Debounce for 100ms
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

// Initialize the page when DOM is loaded, but only if we're on the email list page
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if we're on the page with the email list
    const emailList = document.querySelector('.email-list');
    if (emailList && !hasInitialized) {
        console.log('DOM loaded, initializing page...');
        initializePage();
    }
});

// Helper function to capitalize strings
String.prototype.capitalize = function() {
    return this.charAt(0).toUpperCase() + this.slice(1);
};

function updateLoadingText(stage) {
    const loadingText = document.getElementById('loading-text');
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
        default:
            message = 'Loading...';
    }
    
    // Add animation class
    loadingText.classList.add('stage-change');
    
    // Update text
    loadingText.textContent = message;
    
    // Remove animation class after animation completes
    setTimeout(() => {
        loadingText.classList.remove('stage-change');
    }, 300);
}

// Add this new helper function
function loadFirstEmail() {
    const firstEmail = Array.from(emailMap.values())[0];
    if (firstEmail) {
        selectedEmailId = firstEmail.id;
        loadEmailDetails(firstEmail.id);
    }
}

