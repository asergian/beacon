/**
 * @fileoverview Navigation FAB buttons for scrolling up and down the page.
 * Provides floating action buttons that appear/disappear based on scroll position
 * and allow users to quickly navigate to the top or bottom of the page.
 * 
 * @author Beacon Team
 */

document.addEventListener('DOMContentLoaded', function() {
    const topButton = document.getElementById('to-top-fab');
    const bottomButton = document.getElementById('to-bottom-fab');
    
    if (!topButton || !bottomButton) return; // Exit if buttons don't exist
    
    // Show/hide buttons based on scroll position
    function updateButtonVisibility() {
        if (window.scrollY > 300) {
            topButton.classList.add('visible');
        } else {
            topButton.classList.remove('visible');
        }
        
        // If we're close to the bottom, hide the bottom button
        if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 300) {
            bottomButton.classList.remove('visible');
        } else {
            bottomButton.classList.add('visible');
        }
    }
    
    // Add scroll event listener
    window.addEventListener('scroll', updateButtonVisibility);
    
    // Initial check to set visibility
    updateButtonVisibility();
    
    // Handle click events
    topButton.addEventListener('click', function() {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    
    bottomButton.addEventListener('click', function() {
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    });
}); 