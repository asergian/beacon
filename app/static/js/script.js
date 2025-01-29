// Initialize the page with the first (highest-priority) email
function initializePage() {
    console.log('initializing page...');
    const emailItems = Array.from(document.querySelectorAll('.email-item'));
    
    if (emailItems.length > 0) {
        // Sort emails by priority and date
        const sortedItems = emailItems.sort((a, b) => {
            const emailA = JSON.parse(a.dataset.email);
            const emailB = JSON.parse(b.dataset.email);
            
            // Priority comparison (high: 1, medium: 2, low: 3)
            const priorities = { high: 1, medium: 2, low: 3 };
            const priorityDiff = priorities[emailA.priority_level.toLowerCase()] - 
                               priorities[emailB.priority_level.toLowerCase()];
            
            if (priorityDiff !== 0) return priorityDiff;
            
            // If same priority, sort by date (most recent first)
            return new Date(emailB.date) - new Date(emailA.date);
        });
        
        // Reorder DOM elements according to sort
        const emailList = document.querySelector('.email-list');
        sortedItems.forEach(item => emailList.appendChild(item));
        
        // Load the first email
        const firstEmailData = JSON.parse(sortedItems[0].dataset.email);
        
        // Load email details for the first email without an event
        loadEmailDetails(firstEmailData, sortedItems[0], null);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initializePage();
});

// Load email details into the right column
function loadEmailDetails(email, email_item = null, event = null) {
    console.log('loading email on right pane...');
    
    // Remove active class from all email items
    document.querySelectorAll('.email-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // If a clicked item is provided via event, add the active class to it
    const clicked_item = event ? event.currentTarget : null;
    if (clicked_item) {
        clicked_item.classList.add('active');
    } 
    else if (email_item) {
        email_item.classList.add('active');
    }
    
    // Update details
    document.getElementById('details-subject').textContent = email.subject;
    document.getElementById('details-sender').textContent = email.sender;
    
    // Format and set date
    const date = new Date(email.date);
    document.getElementById('details-date').textContent = date.toLocaleString();
    
    // Set priority tag with appropriate class
    const priorityTag = document.getElementById('details-priority');
    priorityTag.textContent = email.priority_level;
    priorityTag.className = `tag priority-${email.priority_level.toLowerCase()}`;
    
    // Set category
    document.getElementById('details-category').textContent = email.category;
    
    document.getElementById('details-summary').textContent = email.summary;

    // Populate Action Items
    const keyDatesList = document.getElementById('key-dates-list');
    keyDatesList.innerHTML = '';  // Clear previous dates
    if (email.action_items) {
        email.action_items.forEach(item => {
            if (item.description) {
                const li = document.createElement('li');
                let itemText = item.description;
                if (item.due_date && item.due_date.toLowerCase() !== 'null') {
                    const dueDate = document.createElement('span');
                    dueDate.className = 'due-date';
                    dueDate.textContent = `Due: ${item.due_date}`;
                    li.textContent = itemText;
                    li.appendChild(dueDate);
                } else {
                    li.textContent = itemText;
                }
                keyDatesList.appendChild(li);
            }
        });
    }

    // Populate Email Body
    const emailBody = document.getElementById('email-body');
    emailBody.innerHTML = ''; // Clear previous content
    
    // Create an iframe to sandbox the email content
    const iframe = document.createElement('iframe');
    iframe.style.width = '100%';
    iframe.style.border = 'none';
    emailBody.appendChild(iframe);
    
    // Write the email content to the iframe
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
                    img {
                        max-width: 100%;
                        height: auto;
                    }
                </style>
            </head>
            <body>${email.body}</body>
        </html>
    `);
    doc.close();
    
    // Adjust iframe height handling
    iframe.onload = () => {
        const updateIframeHeight = () => {
            const height = iframe.contentWindow.document.body.scrollHeight;
            iframe.style.height = height + 'px';
        };
        
        updateIframeHeight();
        
        // Add resize observer to handle dynamic content
        let resizeTimeout;
        const resizeObserver = new ResizeObserver(() => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                updateIframeHeight();
            }, 100); // Adjust the timeout as needed
        });
        
        resizeObserver.observe(iframe.contentWindow.document.body);
        
        // Cleanup function to disconnect observer when content changes
        const cleanup = () => {
            resizeObserver.disconnect();
            window.removeEventListener('resize', updateIframeHeight);
        };
        
        // Add cleanup to iframe
        iframe.cleanup = cleanup;
        
        // Also update on window resize
        window.addEventListener('resize', updateIframeHeight);
    };
    
    // Cleanup previous iframe if it exists
    if (emailBody.previousIframe && emailBody.previousIframe.cleanup) {
        emailBody.previousIframe.cleanup();
    }
    emailBody.previousIframe = iframe;
}

// Send an email response
function sendEmailResponse() {
    const response = document.getElementById('response-draft').value;
    if (response.trim() === '') {
        alert("Response is empty. Please draft a response before sending.");
        return;
    }
    console.log("Sending email response:", response);
    alert("Email response sent!");
}

// Filter emails by priority or category
function filterEmails() {
    const priority = document.getElementById('priority-filter').value;
    const category = document.getElementById('category-filter').value;
    const emails = document.querySelectorAll('.email-item');
    const filteredEmails = [];

    emails.forEach(emailElement => {
        const emailData = JSON.parse(emailElement.dataset.email);
        const matchesPriority = priority === 'all' || emailData.priority_level.toLowerCase() === priority.toLowerCase();
        const matchesCategory = category === 'all' || emailData.category.toLowerCase() === category.toLowerCase();
        
        if (matchesPriority && matchesCategory) {
            emailElement.style.display = '';
            filteredEmails.push(emailData);
        } else {
            emailElement.style.display = 'none';
        }
    });

    // Sort filtered emails by priority and date
    filteredEmails.sort((a, b) => {
        const priorities = { high: 1, medium: 2, low: 3 };
        const priorityDiff = priorities[a.priority_level.toLowerCase()] - 
                           priorities[b.priority_level.toLowerCase()];
        
        if (priorityDiff !== 0) return priorityDiff;
        return new Date(b.date) - new Date(a.date);
    });

    // If there are any visible emails, load the highest-ranked one
    if (filteredEmails.length > 0) {
        loadEmailDetails(filteredEmails[0]);
        
        // Update active state
        document.querySelectorAll('.email-item').forEach(item => {
            item.classList.remove('active');
            if (JSON.parse(item.dataset.email).id === filteredEmails[0].id) {
                item.classList.add('active');
            }
        });
    }
}

// Helper function to capitalize strings
String.prototype.capitalize = function() {
    return this.charAt(0).toUpperCase() + this.slice(1);
};

// Attach event listeners and pass the event object
document.querySelectorAll('.email-item').forEach(item => {
    item.addEventListener('click', (event) => {
        const emailData = JSON.parse(item.dataset.email);
        loadEmailDetails(emailData, item, event);
    });
});
