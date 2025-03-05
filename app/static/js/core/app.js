/**
 * @fileoverview Core application functionality and global utilities.
 * This file provides global utility functions and state management that
 * can be used across all pages of the application.
 * @author Beacon Team
 * @license Copyright 2025 Beacon
 */

/**
 * Global configuration object for application-wide settings.
 * @type {Object}
 */
const config = {};

/**
 * Shows the loading bar with optional custom text.
 * Adds the 'visible' class to make the loading bar and text appear.
 * Forces a reflow to restart any animations.
 * 
 * @param {string=} text - Optional text to display in the loading bar
 * @return {void}
 */
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

/**
 * Hides the loading bar and associated text.
 * Removes the 'visible' class from the loading elements.
 * 
 * @return {void}
 */
function hideLoadingBar() {
    const loadingBar = document.getElementById('loading-bar');
    const loadingText = document.getElementById('loading-text');
    
    if (!loadingBar || !loadingText) return;
    
    loadingBar.classList.remove('visible');
    loadingText.classList.remove('visible');
}

/**
 * Shows an error message in the UI.
 * Displays the error message in a designated container and auto-hides after 5 seconds.
 * Also hides any active loading indicators.
 * 
 * @param {string} message - The error message to display
 * @return {void}
 */
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

/**
 * Hides the error message container.
 * 
 * @return {void}
 */
function hideError() {
    const errorDiv = document.getElementById('error-message');
    if (errorDiv) {
        errorDiv.style.display = 'none';
    }
}

/**
 * Export common functions for use in other scripts by attaching them to the window object.
 */
window.showLoadingBar = showLoadingBar;
window.hideLoadingBar = hideLoadingBar;
window.showError = showError;
window.hideError = hideError;

/**
 * Memory monitoring utility that tracks JavaScript heap usage.
 * Logs memory statistics periodically and provides warnings for high memory usage.
 * @namespace
 */
const memoryMonitor = {
    /** @type {number} Time of the last memory log */
    lastLog: Date.now(),
    /** @const {number} Interval between memory logs in milliseconds */
    LOG_INTERVAL: 10000, // Log every 10 seconds
    /** @type {number} The last recorded memory usage value */
    lastUsage: 0,
    
    /**
     * Logs memory usage statistics to the console.
     * Includes information about total heap size, used heap, and memory deltas.
     * Also logs page-specific information when available.
     * 
     * @return {void}
     */
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

/**
 * Start memory monitoring if the Performance API is available.
 * Sets up an interval to periodically log memory statistics.
 */
if (window.performance && window.performance.memory) {
    setInterval(() => memoryMonitor.logMemoryUsage(), 10000);
}

