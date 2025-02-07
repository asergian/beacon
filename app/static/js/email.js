// Global state for email handling
let emails = [];
let emailMap = new Map();
let isLoadingAnalysis = false;
let hasInitialized = false;
let selectedEmailId = null;
let updateEmailListTimeout = null;

// Update config with email-specific defaults
config.days_back = 1;  // Default value, will be updated from user settings
config.batch_size = 50;  // Batch size for UI updates

// Function to fetch user settings
async function fetchUserSettings() {
    try {
        const response = await fetch('/email/api/user/settings');
        if (response.ok) {
            const settings = await response.json();
            if (settings.status === 'success' && settings.settings) {
                config.days_back = settings.settings.email_preferences.days_to_analyze;
                console.log('Updated days_back from user settings:', config.days_back);
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
        updateLoadingText('cache');
        let hasCachedData = false;
        
        try {
            const cacheResponse = await fetch(`/email/api/emails/cached?days_back=${config.days_back}`);
            if (cacheResponse.ok) {
                const cacheData = await cacheResponse.json();
                if (cacheData.status === 'success' && cacheData.emails.length > 0) {
                    emailMap.clear();
                    cacheData.emails.forEach(email => emailMap.set(email.id, { ...email, isAnalyzed: true }));
                    updateEmailList();
                    loadFirstEmail();
                    hasCachedData = true;
                    
                    emailList.style.display = 'block';
                    emailDetails.style.display = 'block';
                }
            }
        } catch (cacheError) {
            console.warn('Failed to load cached emails:', cacheError);
        }
        
        updateLoadingText('analyze');
        await loadEmailAnalysis();
        
        updateEmailList();
        loadFirstEmail();
        
        emailList.style.display = 'block';
        emailDetails.style.display = 'block';
        
    } catch (error) {
        console.error('Error loading emails:', error);
        showError('Failed to load emails. Please try again.');
        hasInitialized = false;
    } finally {
        emailList.style.display = 'block';
        emailDetails.style.display = 'block';
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
        
        const updates = sortedEmails.map(email => () => {
            const li = document.createElement('li');
            li.className = `email-item ${!email.isAnalyzed ? 'analyzing' : ''}`;
            li.dataset.emailId = email.id;
            li.onclick = () => {
                document.querySelectorAll('.email-item').forEach(item => item.classList.remove('active'));
                li.classList.add('active');
                selectedEmailId = email.id;
                loadEmailDetails(email.id);
            };

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
                        <span class="tag category" data-category="${email.category || 'Informational'}">${formatTagText(email.category) || 'Pending'}</span>
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
    const email = emailMap.get(emailId);
    if (!email) return;
    
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
    }
}

// Initialize the page when DOM is loaded
document.addEventListener('DOMContentLoaded', initializePage); 