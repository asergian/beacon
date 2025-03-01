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

// Memory monitoring
const memoryMonitor = {
    lastLog: Date.now(),
    LOG_INTERVAL: 10000, // Log every 10 seconds
    lastUsage: 0,
    
    logMemoryUsage: function() {
        if (!window.performance || !window.performance.memory) {
            console.log('Memory API not available');
            return;
        }
        
        const now = Date.now();
        if (now - this.lastLog < this.LOG_INTERVAL) return;
        
        const memory = window.performance.memory;
        const memoryUsageMB = Math.round(memory.usedJSHeapSize / (1024 * 1024));
        const totalHeapMB = Math.round(memory.totalJSHeapSize / (1024 * 1024));
        const heapLimitMB = Math.round(memory.jsHeapSizeLimit / (1024 * 1024));
        
        // Calculate memory delta
        const memoryDelta = this.lastUsage ? (memoryUsageMB - this.lastUsage) : 0;
        this.lastUsage = memoryUsageMB;
        
        // Get current page info
        const currentPage = window.location.pathname;
        const pageSpecific = {
            '/email': {
                emailCount: window.emailMap?.size || 0,
                analyzing: window.isLoadingAnalysis || false
            }
        }[currentPage] || {};
        
        console.log(`[Memory Usage] ${new Date().toISOString()}`);
        console.log(`Page: ${currentPage}`);
        console.log(`Used: ${memoryUsageMB}MB / Total: ${totalHeapMB}MB / Limit: ${heapLimitMB}MB`);
        console.log(`Delta: ${memoryDelta > 0 ? '+' : ''}${memoryDelta}MB`);
        
        if (Object.keys(pageSpecific).length > 0) {
            console.log('Page Specific:', pageSpecific);
        }
        
        // Log warning if memory usage is high (over 1.5GB)
        if (memoryUsageMB > 1500) {
            console.warn(`High memory usage detected: ${memoryUsageMB}MB`);
            // Log extra debug info on high memory
            try {
                console.warn('Debug Info:', {
                    documentSize: document.documentElement.innerHTML.length,
                    scripts: document.scripts.length,
                    nodes: document.getElementsByTagName('*').length,
                    url: window.location.href
                });
            } catch (e) {
                console.warn('Failed to collect debug info:', e);
            }
        }
        
        this.lastLog = now;
    }
};

// Start memory monitoring if the API is available
if (window.performance && window.performance.memory) {
    setInterval(() => memoryMonitor.logMemoryUsage(), 10000);
}

