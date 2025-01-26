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
    // Update right pane details
    console.log(email);
    document.getElementById('details-sender').textContent = email.sender;
    document.getElementById('details-subject').textContent = email.subject;
    document.getElementById('details-priority').textContent = email.priority;
    document.getElementById('details-category').textContent = email.category;  // Updated for category
    document.getElementById('details-summary').textContent = email.summary;

    // Populate Key Dates
    const keyDatesList = document.getElementById('key-dates-list');
    keyDatesList.innerHTML = '';  // Clear previous dates
    if (email.key_dates_info) {
        email.key_dates_info.forEach(date => {
            const li = document.createElement('li');
            li.textContent = `${date.date}: ${date.info}`;  // Adjusted to match date-info format
            keyDatesList.appendChild(li);
        });
    }

    // Populate Action Items
    const actionItemsList = document.getElementById('action-items-list');
    actionItemsList.innerHTML = '';  // Clear previous actions
    if (email.key_action_items) {
        email.key_action_items.forEach(action => {
            const li = document.createElement('li');
            li.textContent = `${action.action} (Responsible: ${action.responsible_party})`;  // Updated to match action and responsible party
            actionItemsList.appendChild(li);
        });
    }

    // Populate Email Body
    document.getElementById('email-body').textContent = email.body;

    // Clear and focus the response draft area
    const responseDraft = document.getElementById('response-draft');
    responseDraft.value = '';
    //responseDraft.focus();  // Focus the textarea after clearing
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