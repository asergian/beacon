/**
 * @fileoverview Email summary page-specific functionality.
 * Includes navigation controls for long emails and response sections.
 * @author Beacon Team
 * @license Copyright 2025 Beacon
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize mobile view toggle
    initMobileToggle();
    
    // Initialize filter toggle
    initFilterToggle();
    
    // Initialize pull to refresh (for mobile)
    initPullToRefresh();
    
    // Check screen size and set initial mobile view state
    checkScreenSize();
    
    // Listen for window resize to adjust the view accordingly
    window.addEventListener('resize', checkScreenSize);
});

/**
 * Initializes the toggle button for returning to email list on mobile.
 */
function initMobileToggle() {
    const toggleBtn = document.getElementById('mobile-toggle-btn');
    const emailListColumn = document.querySelector('.email-list-column');
    const emailDetailsColumn = document.querySelector('.email-details-column');
    
    if (!toggleBtn || !emailListColumn || !emailDetailsColumn) {
        console.error('Mobile toggle elements not found');
        return;
    }
    
    // Simple click handler - return to list view
    toggleBtn.addEventListener('click', function() {
        // Hide details, show list
        emailDetailsColumn.style.display = 'none';
        emailListColumn.style.display = 'block';
        
        // Reset height constraints to ensure proper fit on mobile
        // Remove explicit height settings to allow CSS to control it
        emailListColumn.style.maxHeight = '';
        
        // On mobile, hide mobile toggle when viewing email list
        if (window.innerWidth <= 768) {
            toggleBtn.classList.remove('visible');
        }
    });
}

/**
 * Initialize the filter toggle button functionality
 */
function initFilterToggle() {
    // Get filter toggle button from header
    const filterToggleBtn = document.getElementById('filter-toggle');
    const filtersRow = document.querySelector('.filters-row');
    
    if (!filterToggleBtn || !filtersRow) {
        console.error('Filter toggle elements not found');
        return;
    }
    
    // Initially collapse filters on mobile
    if (window.innerWidth <= 768) {
        filtersRow.classList.add('collapsed');
    }
    
    // Add click handler to filter toggle
    filterToggleBtn.addEventListener('click', function() {
        filtersRow.classList.toggle('collapsed');
        
        // Update aria-expanded attribute for accessibility
        const isExpanded = !filtersRow.classList.contains('collapsed');
        filterToggleBtn.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
    });
}

/**
 * Checks the screen size and adjusts the UI components accordingly.
 */
function checkScreenSize() {
    const toggleBtn = document.getElementById('mobile-toggle-btn');
    const emailListColumn = document.querySelector('.email-list-column');
    const emailDetailsColumn = document.querySelector('.email-details-column');
    const filtersRow = document.querySelector('.filters-row');
    
    if (!toggleBtn || !emailListColumn || !emailDetailsColumn) {
        console.error('Mobile toggle elements not found');
        return;
    }
    
    const isMobile = window.innerWidth <= 768;
    //console.log("Screen width:", window.innerWidth, "Mobile:", isMobile);
    
    if (isMobile) {
        // Mobile: Start with email list view
        emailListColumn.style.display = 'block';
        emailDetailsColumn.style.display = 'none';
        
        // Mobile: Let CSS handle height and padding to prevent content riding up into header
        // Remove inline styles that might override our CSS fix
        emailListColumn.style.maxHeight = '';
        emailDetailsColumn.style.maxHeight = '';
        document.body.style.overflow = 'hidden';
        
        // Mobile: Hide mobile toggle button on list view
        toggleBtn.classList.remove('visible');
        
        // Mobile: Collapse filters
        if (filtersRow) {
            filtersRow.classList.add('collapsed');
        }
        
        // Initialize pull-to-refresh for mobile
        initPullToRefresh();
    } else {
        // Desktop: Show both columns
        emailListColumn.style.display = 'block';
        emailDetailsColumn.style.display = 'block';
        
        // Desktop: Reset to use standard viewport height units
        emailListColumn.style.height = '';
        emailListColumn.style.maxHeight = '';
        emailDetailsColumn.style.height = '';
        emailDetailsColumn.style.maxHeight = '';
        
        // Only hide the mobile toggle button on desktop
        toggleBtn.classList.remove('visible');
        
        // Desktop: Show filters
        if (filtersRow) {
            filtersRow.classList.remove('collapsed');
        }
        
        // Reset pull-to-refresh indicator if present
        const pullToRefreshEl = document.querySelector('.pull-to-refresh');
        if (pullToRefreshEl) {
            pullToRefreshEl.style.transform = 'translateY(0)';
            pullToRefreshEl.classList.remove('pulling', 'refreshing');
        }
    }
}

/**
 * Initializes the pull-to-refresh functionality for mobile devices.
 * This allows users to pull down the email list to refresh the page.
 */
function initPullToRefresh() {
    // Only initialize on mobile devices
    if (window.innerWidth > 768) {
        return; // Skip on desktop
    }
    
    const emailListColumn = document.querySelector('.email-list-column');
    const pullToRefreshEl = document.querySelector('.pull-to-refresh');
    
    if (!emailListColumn || !pullToRefreshEl) {
        console.error('Pull to refresh elements not found');
        return;
    }
    
    // Track touch
    let touchStartY = 0;
    let touchEndY = 0;
    let pullDistance = 0;
    const THRESHOLD = 80; // Minimum pull distance to trigger refresh
    const MAX_PULL = 120; // Maximum pull distance
    let isPulling = false;
    let isRefreshing = false;
    
    // Update pull indicator position based on pull distance
    function updatePullPosition(distance) {
        // Update the pull indicator position and state
        const transformY = Math.min(distance, MAX_PULL);
        pullToRefreshEl.style.transform = `translateY(${transformY}px)`;
        
        // Update indicator state
        if (distance >= THRESHOLD && !isRefreshing) {
            pullToRefreshEl.classList.add('pulling');
            pullToRefreshEl.querySelector('.refresh-text').textContent = 'Release to refresh';
        } else if (!isRefreshing) {
            pullToRefreshEl.classList.remove('pulling');
            pullToRefreshEl.querySelector('.refresh-text').textContent = 'Pull down to refresh';
        }
    }
    
    // Start refreshing action
    function startRefresh() {
        isRefreshing = true;
        isPulling = false;
        pullToRefreshEl.classList.remove('pulling');
        pullToRefreshEl.classList.add('refreshing');
        pullToRefreshEl.querySelector('.refresh-text').textContent = 'Refreshing...';
        
        // Keep the indicator visible
        pullToRefreshEl.style.transform = 'translateY(60px)';
        
        // Simulate a brief delay before reloading (optional)
        setTimeout(() => {
            // Reload the page
            window.location.reload();
            
            // If for some reason the reload doesn't happen, reset the UI after 5 seconds
            setTimeout(() => {
                resetPullUI();
            }, 5000);
        }, 500);
    }
    
    // Reset the pull UI
    function resetPullUI() {
        pullToRefreshEl.style.transform = 'translateY(0)';
        pullToRefreshEl.classList.remove('pulling', 'refreshing');
        isRefreshing = false;
        isPulling = false;
    }
    
    // Touch start event
    emailListColumn.addEventListener('touchstart', function(e) {
        // Only allow pull to refresh when at the top of the list
        if (emailListColumn.scrollTop <= 0) {
            touchStartY = e.touches[0].clientY;
            isPulling = true;
        }
    }, { passive: true });
    
    // Touch move event
    emailListColumn.addEventListener('touchmove', function(e) {
        if (!isPulling || isRefreshing) return;
        
        touchEndY = e.touches[0].clientY;
        pullDistance = touchEndY - touchStartY;
        
        // Only handle downward pulling motion
        if (pullDistance > 0 && emailListColumn.scrollTop <= 0) {
            // Reduce the pull distance slightly to create resistance
            const displayDistance = Math.pow(pullDistance, 0.8);
            updatePullPosition(displayDistance);
            
            // Prevent default scrolling if we're pulling
            if (pullDistance > 20) {
                e.preventDefault();
            }
        }
    }, { passive: false });
    
    // Touch end event
    emailListColumn.addEventListener('touchend', function() {
        if (!isPulling || isRefreshing) return;
        
        if (pullDistance >= THRESHOLD) {
            startRefresh();
        } else {
            resetPullUI();
        }
        
        // Reset
        pullDistance = 0;
        touchStartY = 0;
        touchEndY = 0;
    });
} 