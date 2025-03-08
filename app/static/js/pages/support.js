/**
 * @fileoverview Support page functionality for handling user support requests.
 * Manages form submission, validation, and toast notifications for the support
 * contact form.
 * 
 * @author Beacon Team
 * @license MIT
 */

document.addEventListener('DOMContentLoaded', function() {
    /** @type {HTMLFormElement} Form element for support requests */
    const supportForm = document.getElementById('supportForm');
    
    /** @type {HTMLElement} Container for toast notifications */
    const toastContainer = document.querySelector('.toast-container') || createToastContainer();
    
    if (supportForm) {
        supportForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Get form data
            /** @type {Object} Form data collected from input fields */
            const formData = {
                name: document.getElementById('name').value.trim(),
                email: document.getElementById('email').value.trim(),
                subject: document.getElementById('subject').value.trim(),
                message: document.getElementById('message').value.trim()
            };
            
            // Client-side validation
            /** @type {Array<string>} List of validation error messages */
            const errors = validateForm(formData);
            if (errors.length > 0) {
                showToast('error', errors[0]);
                return;
            }
            
            // Disable submit button and show loading state
            /** @type {HTMLButtonElement} Submit button element */
            const submitBtn = supportForm.querySelector('button[type="submit"]');
            /** @type {string} Original button text before loading state */
            const originalBtnText = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner"></span> Sending...';
            
            // Send form data to server
            fetch('/pages/api/support-message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showToast('success', data.message);
                    supportForm.reset();
                } else {
                    showToast('error', data.message || 'An error occurred. Please try again.');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showToast('error', 'Network error. Please try again later.');
            })
            .finally(() => {
                // Restore button state
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnText;
            });
        });
    }
    
    /**
     * Validates the support form data for required fields and format.
     * 
     * @param {Object} formData - The form data to validate
     * @param {string} formData.name - User's name
     * @param {string} formData.email - User's email address
     * @param {string} formData.subject - Message subject
     * @param {string} formData.message - Support message content
     * @return {Array<string>} Array of error messages, empty if validation passes
     */
    function validateForm(formData) {
        const errors = [];
        
        if (!formData.name) {
            errors.push('Please enter your name');
        }
        
        if (!formData.email) {
            errors.push('Please enter your email address');
        } else if (!isValidEmail(formData.email)) {
            errors.push('Please enter a valid email address');
        }
        
        if (!formData.message) {
            errors.push('Please enter a message');
        } else if (formData.message.length > 5000) {
            errors.push('Message is too long (maximum 5000 characters)');
        }
        
        return errors;
    }
    
    /**
     * Validates an email address format using regex.
     * 
     * @param {string} email - The email address to validate
     * @return {boolean} True if email format is valid, false otherwise
     */
    function isValidEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
    
    /**
     * Creates a toast container element if it doesn't exist in the DOM.
     * 
     * @return {HTMLElement} The toast container element
     */
    function createToastContainer() {
        const container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
        return container;
    }
    
    /**
     * Displays a toast notification with the specified type and message.
     * Toast will automatically disappear after 5 seconds.
     * 
     * @param {string} type - The type of toast ('success', 'error', 'info', 'warning')
     * @param {string} message - The message to display in the toast
     */
    function showToast(type, message) {
        /** @type {string} Unique ID for the toast element */
        const toastId = 'toast-' + Date.now();
        
        /** @type {HTMLElement} The toast element */
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.id = toastId;
        
        toast.innerHTML = `
            <div class="toast-content">
                <div class="toast-body">${message}</div>
            </div>
            <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
        `;
        
        toastContainer.appendChild(toast);
        
        // Show the toast
        setTimeout(() => {
            toast.classList.add('show');
        }, 10);
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            if (document.getElementById(toastId)) {
                toast.classList.add('hiding');
                setTimeout(() => {
                    if (document.getElementById(toastId)) {
                        toast.remove();
                    }
                }, 300);
            }
        }, 5000);
    }
}); 