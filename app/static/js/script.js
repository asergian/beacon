// Initialize the page with the first (highest-priority) email
function initializePage() {
    console.log('initializing page...');

    if (emails.length > 0) {
        const sortedEmails = [...emails].sort((a, b) => {
            const priorities = { high: 1, medium: 2, low: 3 };
            return priorities[a.priority] - priorities[b.priority];
        });
        loadEmailDetails(sortedEmails[0]);
    }
}

// Load email details into the right column
function loadEmailDetails(email) {
    console.log('loading email on right pane...');
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
    iframe.style.minHeight = '300px'; // Set a minimum height
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
                        font-family: Arial, sans-serif;
                        margin: 0;
                        padding: 16px;
                        color: #333;
                    }
                </style>
            </head>
            <body>${email.body}</body>
        </html>
    `);
    doc.close();
    
    // Adjust iframe height to content
    iframe.onload = () => {
        iframe.style.height = iframe.contentWindow.document.body.scrollHeight + 'px';
    };
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

// Filter emails by priority
function filterEmails() {
    const priority = document.getElementById('priority-filter').value;
    const emails = document.querySelectorAll('.email-item');
    const filteredEmails = [];

    emails.forEach(emailElement => {
        if (priority === 'all' || emailElement.dataset.priority === priority) {
            emailElement.style.display = '';
            // Store the email data from the data-email attribute (already in JSON format)
            filteredEmails.push(JSON.parse(emailElement.dataset.email)); // Now this works because the data-email attribute is present
        } else {
            emailElement.style.display = 'none';
        }
    });

    // If there are any visible emails, load the highest-ranked one in the filtered list
    if (filteredEmails.length > 0) {
        loadEmailDetails(filteredEmails[0]);
        console.log("Updating right pane with filtered email...");
    }
}

// Helper function to capitalize strings
String.prototype.capitalize = function() {
    return this.charAt(0).toUpperCase() + this.slice(1);
};

document.addEventListener("DOMContentLoaded", function () {
    initializePage();
});