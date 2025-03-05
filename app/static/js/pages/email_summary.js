/**
 * @fileoverview Email summary page-specific functionality.
 * Includes navigation controls for long emails and response sections.
 * @author Beacon Team
 * @license Copyright 2025 Beacon
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize navigation buttons
    initNavButtons();
});

/**
 * Initializes the navigation buttons for jumping between email content and response sections.
 * Handles button click functionality for navigation.
 */
function initNavButtons() {
    const toResponseBtn = document.getElementById('to-response-fab');
    const toTopBtn = document.getElementById('to-top-fab');
    const responseSection = document.getElementById('email-response');
    const emailDetails = document.getElementById('email-details');
    const emailMeta = document.querySelector('.email-meta');
    
    if (!toResponseBtn || !toTopBtn) {
        console.error('Navigation buttons not found');
        return;
    }
    
    // Buttons are now permanently visible with CSS, no need to toggle visibility
    
    // Scroll to response section
    toResponseBtn.addEventListener('click', function() {
        if (responseSection) {
            console.log('Scrolling to response section');
            responseSection.scrollIntoView({ behavior: 'smooth' });
        }
    });
    
    // Scroll to email meta section
    toTopBtn.addEventListener('click', function() {
        if (emailMeta) {
            console.log('Scrolling to email meta section');
            emailMeta.scrollIntoView({ behavior: 'smooth' });
        } else if (emailDetails) {
            console.log('Email meta not found, scrolling to email details');
            emailDetails.scrollIntoView({ behavior: 'smooth' });
        } else {
            console.log('Neither email meta nor details found, scrolling to top');
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    });
} 