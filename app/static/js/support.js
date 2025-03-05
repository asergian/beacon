/**
 * Support Page JavaScript
 * Handles form submission and toast notifications
 */

document.addEventListener('DOMContentLoaded', function() {
    const supportForm = document.getElementById('supportForm');
    const toastContainer = document.querySelector('.toast-container') || createToastContainer();
    
    if (supportForm) {
        supportForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Get form data
            const formData = {
                name: document.getElementById('name').value.trim(),
                email: document.getElementById('email').value.trim(),
                subject: document.getElementById('subject').value.trim(),
                message: document.getElementById('message').value.trim()
            };
            
            // Client-side validation
            const errors = validateForm(formData);
            if (errors.length > 0) {
                showToast('error', errors[0]);
                return;
            }
            
            // Disable submit button and show loading state
            const submitBtn = supportForm.querySelector('button[type="submit"]');
            const originalBtnText = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner"></span> Sending...';
            
            // Send form data to server
            fetch('/api/support-message', {
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
     * Validate form data
     * @param {Object} formData - The form data to validate
     * @returns {Array} - Array of error messages
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
     * Validate email format
     * @param {string} email - The email to validate
     * @returns {boolean} - Whether the email is valid
     */
    function isValidEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
    
    /**
     * Create toast container if it doesn't exist
     * @returns {HTMLElement} - The toast container
     */
    function createToastContainer() {
        const container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
        return container;
    }
    
    /**
     * Show a toast notification
     * @param {string} type - The type of toast (success, error, info, warning)
     * @param {string} message - The message to display
     */
    function showToast(type, message) {
        const toastId = 'toast-' + Date.now();
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