function filterEmails() {
    const priorityFilter = document.getElementById('priority-filter').value;
    const categoryFilter = document.getElementById('category-filter').value;
    const actionFilter = document.getElementById('action-filter').value;
    
    const emailItems = document.querySelectorAll('.email-item');
    let hasVisibleEmail = false;
    
    emailItems.forEach(item => {
        const priority = item.getAttribute('data-priority');
        const category = item.getAttribute('data-category');
        const needsAction = item.getAttribute('data-needs-action') === 'true';
        
        let showByPriority = priorityFilter === 'all';
        if (priority >= 75 && priorityFilter === 'high') showByPriority = true;
        else if (priority >= 25 && priority < 75 && priorityFilter === 'medium') showByPriority = true;
        else if (priority < 25 && priorityFilter === 'low') showByPriority = true;
        
        let showByCategory = categoryFilter === 'all' || category === categoryFilter;
        let showByAction = actionFilter === 'all' || 
                          (actionFilter === 'required' && needsAction) || 
                          (actionFilter === 'none' && !needsAction);
        
        const shouldShow = showByPriority && showByCategory && showByAction;
        item.style.display = shouldShow ? 'block' : 'none';
        
        if (shouldShow && !hasVisibleEmail) {
            hasVisibleEmail = true;
            item.click();  // Select the first visible email
        }
    });
    
    // If no emails are visible after filtering, clear the email display
    if (!hasVisibleEmail) {
        const emailDisplay = document.getElementById('email-display');
        if (emailDisplay) {
            emailDisplay.innerHTML = '<div class="no-email-selected">No emails match the current filters</div>';
        }
    }
}

function displayEmail(emailData) {
    const emailDisplay = document.getElementById('email-display');
    if (!emailData) {
        emailDisplay.innerHTML = '<div class="no-email-selected">No email selected</div>';
        return;
    }
    
    // Format the action items
    let actionItemsHtml = '';
    if (emailData.action_items && emailData.action_items.length > 0) {
        actionItemsHtml = '<div class="action-items"><h3>Action Items:</h3><ul>' +
            emailData.action_items.map(item => {
                if (typeof item === 'string') {
                    return `<li>${item}</li>`;
                } else {
                    return `<li>${item.description}${item.due_date ? ` (Due: ${item.due_date})` : ''}</li>`;
                }
            }).join('') + '</ul></div>';
    }
    
    // Add tags in consistent order
    const tags = [];
    
    // Priority tag first
    const priority = parseInt(emailData.priority) || 50;
    if (priority >= 75) {
        tags.push('<span class="tag high-priority">High Priority</span>');
    } else if (priority >= 25) {
        tags.push('<span class="tag medium-priority">Medium Priority</span>');
    } else {
        tags.push('<span class="tag low-priority">Low Priority</span>');
    }
    
    // Category tag second (if not action required)
    if (!emailData.needs_action && emailData.category) {
        tags.push(`<span class="tag category">${emailData.category}</span>`);
    }
    
    // Action Required tag last (if needed)
    if (emailData.needs_action) {
        tags.push('<span class="tag action-required">Action Required</span>');
    }
    
    // Format the email content
    emailDisplay.innerHTML = `
        <div class="email-header">
            <div class="tags-container">${tags.join('')}</div>
            <h2>${emailData.subject}</h2>
            <div class="email-meta">
                <span class="from">From: ${emailData.from}</span>
                <span class="date">Date: ${new Date(emailData.date).toLocaleString()}</span>
            </div>
        </div>
        <div class="email-body">
            ${emailData.body}
        </div>
        ${actionItemsHtml}
        <div class="email-summary">
            <h3>Summary:</h3>
            <p>${emailData.summary || 'No summary available.'}</p>
        </div>
    `;
}

function displayEmailInList(email) {
    const listItem = document.createElement('li');
    listItem.classList.add('email-item');
    listItem.setAttribute('data-email-id', email.id);
    listItem.setAttribute('data-priority', email.priority || '50');
    listItem.setAttribute('data-category', email.category || 'Informational');
    listItem.setAttribute('data-needs-action', email.needs_action || false);
    
    if (email.needs_action) {
        listItem.classList.add('needs-action');
    }
    
    // Add tags in consistent order
    const tags = [];
    
    // Priority tag first
    const priority = parseInt(email.priority) || 50;
    if (priority >= 75) {
        tags.push('<span class="tag high-priority">High Priority</span>');
    } else if (priority >= 25) {
        tags.push('<span class="tag medium-priority">Medium Priority</span>');
    } else {
        tags.push('<span class="tag low-priority">Low Priority</span>');
    }
    
    // Category tag second (if not action required)
    if (!email.needs_action && email.category) {
        tags.push(`<span class="tag category">${email.category}</span>`);
    }
    
    // Action Required tag last (if needed)
    if (email.needs_action) {
        tags.push('<span class="tag action-required">Action Required</span>');
    }
    
    const date = new Date(email.date).toLocaleString();
    
    listItem.innerHTML = `
        <div class="email-list-item">
            <div class="email-header">
                <div class="email-subject">${email.subject}</div>
                <div class="email-meta">
                    <span class="email-sender">${email.from}</span>
                    <span class="email-date">${date}</span>
                </div>
            </div>
            <div class="email-tags">${tags.join('')}</div>
        </div>
    `;
    
    listItem.addEventListener('click', () => selectEmail(email.id));
    return listItem;
}

function updateEmailList(emails) {
    const emailList = document.querySelector('.email-list');
    emailList.innerHTML = '';
    
    // Sort emails by needs_action (true first), then priority_level (high to low), then date (newest first)
    const sortedEmails = emails.sort((a, b) => {
        if (a.needs_action !== b.needs_action) {
            return b.needs_action ? 1 : -1;  // true values first
        }
        const aPriority = parseInt(a.priority_level) || 50;
        const bPriority = parseInt(b.priority_level) || 50;
        if (aPriority !== bPriority) {
            return bPriority - aPriority;  // higher priority first
        }
        return new Date(b.date) - new Date(a.date);  // newer dates first
    });
    
    sortedEmails.forEach(email => {
        const listItem = displayEmailInList(email);
        emailList.appendChild(listItem);
    });
    
    // Select the first email by default (which will be the highest priority action-required email)
    if (sortedEmails.length > 0) {
        const firstEmail = emailList.querySelector('.email-item');
        if (firstEmail) {
            firstEmail.click();
        }
    }
}

// Update the cache handling
function loadCachedEmails() {
    const userId = '{{ user_id }}';
    const cacheKey = `emailCache_${userId}`;
    const cachedData = localStorage.getItem(cacheKey);
    
    if (cachedData) {
        try {
            const parsed = JSON.parse(cachedData);
            if (parsed.timestamp > Date.now() - (30 * 60 * 1000)) { // 30 minutes cache
                window.emails = parsed.emails;
                parsed.emails.forEach(email => window.emailMap.set(email.id, email));
                console.log('Loaded cached emails for user:', userId);
                
                // Update the email list with cached data
                updateEmailList(window.emails);
                return true;
            }
        } catch (e) {
            console.warn('Failed to load cached emails:', e);
            localStorage.removeItem(cacheKey); // Clear invalid cache
        }
    }
    return false;
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