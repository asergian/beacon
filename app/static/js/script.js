// Global state for theme handling and common functionality
const config = {};

// Function to show/hide loading bar
function showLoadingBar(text) {
    const loadingBar = document.getElementById('loading-bar');
    const loadingText = document.getElementById('loading-text');
    
    if (!loadingBar || !loadingText) return;
    
    // Force a reflow to restart animation
    loadingBar.classList.remove('visible');
    void loadingBar.offsetWidth;
    
    loadingBar.classList.add('visible');
    loadingText.textContent = text || 'Loading...';
    loadingText.classList.add('visible');
}

function hideLoadingBar() {
    const loadingBar = document.getElementById('loading-bar');
    const loadingText = document.getElementById('loading-text');
    
    if (!loadingBar || !loadingText) return;
    
    loadingBar.classList.remove('visible');
    loadingText.classList.remove('visible');
}

function showError(message) {
    hideLoadingBar();
    const errorDiv = document.getElementById('error-message');
    const errorText = document.getElementById('error-text');
    if (!errorDiv || !errorText) return;
    
    errorText.textContent = message;
    errorDiv.style.display = 'flex';
    
    // Auto-hide error after 5 seconds
    setTimeout(() => {
        errorDiv.style.display = 'none';
    }, 5000);
}

function hideError() {
    const errorDiv = document.getElementById('error-message');
    if (errorDiv) {
        errorDiv.style.display = 'none';
    }
}

// Export common functions for use in other scripts
window.showLoadingBar = showLoadingBar;
window.hideLoadingBar = hideLoadingBar;
window.showError = showError;
window.hideError = hideError;

