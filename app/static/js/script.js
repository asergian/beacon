// Global state
let emails = window.emails || [];
let emailMap = window.emailMap || new Map();
let isLoadingMetadata = false;
let isLoadingAnalysis = false;

// Configuration
const config = {
    days_back: 0,  // Number of days to fetch emails for
    cache_duration_ms: 3600000,  // Cache duration in milliseconds (1 hour)
    batch_size: 50  // Batch size for UI updates
};

// Track currently selected email
let selectedEmailId = null;

// Add this at the top with other global variables
let updateEmailListTimeout = null;

// Function to clear the email list in the UI
function clearEmailList() {
    console.log('Number of emails before clearing:', document.querySelectorAll('.email-list .email-item').length); // Log the number of items
    const emailList = document.querySelector('.email-list');
    emailList.innerHTML = ''; // Clear the existing email list
}

// Initialize the page and start loading data
async function initializePage() {
    console.log('Initializing page...');
    clearEmailList();
    
    // Show loading states initially
    document.getElementById('email-list-loading').style.display = 'flex';
    document.getElementById('details-loading').style.display = 'flex';
    
    updateLoadingText('fetch');
    const hasCachedData = await loadCache();

    if (hasCachedData) {
        console.log('Displaying cached data...');
        updateEmailList();
        loadFirstEmail(); // Add this to load initial email details
        document.getElementById('email-list-loading').style.display = 'none';
        document.getElementById('details-loading').style.display = 'none';
    }

    try {
        // Sequential loading stages with proper text updates
        updateLoadingText('fetch');
        await loadEmailMetadata();
        
        updateLoadingText('parse');
        await new Promise(resolve => setTimeout(resolve, 1000)); // Add delay between stages
        
        updateLoadingText('analyze');
        await loadEmailAnalysis();
        
        // Update both email list and details after fresh data
        updateEmailList();
        loadFirstEmail(); // Add this to load initial email details
        
    } catch (error) {
        console.error('Error loading emails:', error);
        if (!hasCachedData) {
            showError('Failed to load emails. Please try again.');
        }
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
    if (isLoadingMetadata || isLoadingAnalysis) {
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

async function loadCache() {
    try {
        // Try to get the most recent user ID from metadata response
        const response = await fetch('/email/api/user');
        if (!response.ok) {
            console.log('Could not verify current user, skipping cache');
            return false;
        }

        const data = await response.json();
        const userId = data.user_id;
        
        if (!userId) {
            console.log('No user ID available, skipping cache');
            return false;
        }

        const cacheKey = `emailCache_${userId}`;
        const cached = localStorage.getItem(cacheKey);
        
        if (cached) {
            const { timestamp, emails } = JSON.parse(cached);
            // Only use cache if it's less than 1 hour old
            if (Date.now() - timestamp < config.cache_duration_ms) {
                emailMap.clear();
                emails.forEach(email => emailMap.set(email.id, email));
                console.log(`Loaded ${emails.length} emails from cache for user ${userId}`);
                return true;
            }
        }
    } catch (e) {
        console.warn('Failed to load cache:', e);
    }
    return false;
}
// Load basic email metadata
async function loadEmailMetadata() {
    if (isLoadingMetadata) return;
    isLoadingMetadata = true;
    
    showLoadingBar('Loading email metadata...');
    updateLoadingText('parse');
    console.log('Loading email metadata with days_back:', config.days_back);
    
    try {
        const response = await fetch(`/email/api/emails/metadata?days_back=${config.days_back}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        if (data.status === 'success') {
            console.log('Received metadata for', data.emails.length, 'emails');
            console.log('Current emailMap size before clearing:', emailMap.size);
            
            // Clear existing emails before adding new ones
            emailMap.clear();
            console.log('EmailMap size after clearing:', emailMap.size);
            
            // Add new emails
            data.emails.forEach(email => {
                const emailDate = new Date(email.date);
                const now = new Date();
                const daysDiff = Math.floor((now - emailDate) / (1000 * 60 * 60 * 24));
                console.log(`Email ${email.id} date: ${emailDate}, days old: ${daysDiff}`);
                
                if (daysDiff <= config.days_back) {
                    emailMap.set(email.id, {
                        ...email,
                        isAnalyzed: false,
                        priority_level: 'pending',
                        category: 'pending',
                        summary: 'Analysis in progress...'
                    });
                } else {
                    console.log(`Skipping email ${email.id} as it's older than ${config.days_back} days`);
                }
            });
            
            console.log('EmailMap size after adding new emails:', emailMap.size);
            
            // Update UI and cache
            updateEmailList();
            updateCache();
            
            document.getElementById('email-list-loading').style.display = 'none';
        } else {
            throw new Error(data.message || 'Failed to load email metadata');
        }
    } catch (error) {
        console.error('Error loading email metadata:', error);
        showError('Failed to load email metadata. ' + error.message);
    } finally {
        isLoadingMetadata = false;
        hideLoadingBar();
    }
}

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
            
            // Update emails with analysis results
            data.emails.forEach(analyzedEmail => {
                const existingEmail = emailMap.get(analyzedEmail.id);
                if (existingEmail) {
                    emailMap.set(analyzedEmail.id, {
                        ...existingEmail,
                        ...analyzedEmail,
                        isAnalyzed: true
                    });
                    console.log('Updated email:', analyzedEmail.id);
                } else {
                    console.log('Skipping analyzed email not in metadata:', analyzedEmail.id);
                }
            });
            
            console.log('EmailMap size after analysis:', emailMap.size);
            
            // Update UI and cache
            updateEmailList();
            updateCache();
        }
    } catch (error) {
        console.error('Error loading email analysis:', error);
        // Don't show error to user since this is background loading
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
    const email = emailMap.get(emailId);
    if (!email) return;
    
    selectedEmailId = emailId; // Update selected email
    
    // Cache DOM queries
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
    
    // Update active state efficiently
    document.querySelector('.email-item.active')?.classList.remove('active');
    document.querySelector(`[data-email-id="${emailId}"]`)?.classList.add('active');
    
    // Show/hide loading state
    detailsElements.loading.style.display = !email.isAnalyzed ? 'flex' : 'none';

    // Helper function to format tag text
    const formatTagText = (text) => {
        if (!text) return '';
        return text.toLowerCase().split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
    };
    
    // Batch DOM updates
    requestAnimationFrame(() => {
        detailsElements.subject.textContent = email.subject;
        detailsElements.sender.textContent = email.sender;
        detailsElements.date.textContent = new Date(email.date).toLocaleString();
        detailsElements.priority.textContent = formatTagText(email.priority_level);
        detailsElements.priority.className = `tag priority-${(email.priority_level || 'pending').toLowerCase()}`;
        detailsElements.category.textContent = formatTagText(email.category);
        
        // Only show action required tag if needed
        if (email.needs_action) {
            detailsElements.actionRequired.textContent = 'Action Required';
            detailsElements.actionRequired.style.display = 'inline-flex';
        } else {
            detailsElements.actionRequired.style.display = 'none';
        }
        
        detailsElements.summary.textContent = email.summary;
        
        // Optimize action items update
        if (email.action_items) {
            const fragment = document.createDocumentFragment();
            email.action_items.forEach(item => {
                if (item.description) {
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
        }
    });
    
    // Optimize iframe handling with debounced resize observer
    if (email.body) {
        if (currentIframe) {
            currentIframe.cleanup?.();
            currentIframe.remove();
        }
        
        const iframe = document.createElement('iframe');
        iframe.style.cssText = 'width: 100%; border: none; min-height: 100px;'; // Add min-height
        detailsElements.emailBody.appendChild(iframe);
        
        const doc = iframe.contentWindow.document;
        doc.open();
        doc.write(`
            <html>
                <head>
                    <base target="_blank">
                    <style>
                        body {
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                            margin: 0;
                            padding: 16px;
                            color: #333;
                            overflow: hidden;
                        }
                        img { max-width: 100%; height: auto; }
                    </style>
                </head>
                <body>${email.body}</body>
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
    if (document.querySelector('.email-list')) {
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

function updateCache() {
    try {
        const userId = '{{ user_id }}';
        const cacheKey = `emailCache_${userId}`;
        const cacheData = {
            timestamp: Date.now(),
            emails: Array.from(emailMap.values())
        };
        localStorage.setItem(cacheKey, JSON.stringify(cacheData));
        console.log('Cache updated with', emailMap.size, 'emails');
    } catch (e) {
        console.warn('Failed to update cache:', e);
    }
}

// Add this new helper function
function loadFirstEmail() {
    const firstEmail = Array.from(emailMap.values())[0];
    if (firstEmail) {
        selectedEmailId = firstEmail.id;
        loadEmailDetails(firstEmail.id);
    }
}

