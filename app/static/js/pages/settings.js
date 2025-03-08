/**
 * @fileoverview Handles user settings functionality for the settings page.
 * Manages UI interactions, server updates, and state management for user preferences.
 * @author Beacon Team
 * @license Copyright 2025 Beacon
 */

/**
 * Initializes settings page functionality when the DOM is loaded.
 * Sets up event listeners for all interactive elements on the settings page.
 */
document.addEventListener('DOMContentLoaded', function() {
    /**
     * Set up value button click handlers for selecting predefined setting values.
     * These buttons represent discrete options like "1d", "3d", "7d" for days settings.
     */
    document.querySelectorAll('.value-button').forEach(button => {
        button.addEventListener('click', async (e) => {
            const value = e.target.dataset.value;
            const setting = e.target.dataset.setting;
            
            // Update visual state
            e.target.closest('.button-group').querySelectorAll('.value-button').forEach(btn => {
                btn.classList.remove('selected');
            });
            e.target.classList.add('selected');
            
            // Save setting to server
            await updateSetting(setting, value);
        });
    });
    
    /**
     * Set up checkbox toggle handlers for boolean settings.
     * Handles special cases for theme toggle and AI features toggle.
     */
    document.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
        checkbox.addEventListener('change', async (e) => {
            const setting = e.target.name;
            const value = e.target.checked;
            
            // Special handling for theme toggle
            if (setting === 'theme') {
                // Update theme immediately
                document.documentElement.setAttribute('data-theme', value ? 'dark' : 'light');
                // Use correct value format for theme setting
                await updateSetting(setting, value ? 'dark' : 'light');
                return;
            }
            
            // Special handling for AI features toggle
            if (setting === 'ai_features.enabled') {
                const aiDependentSettings = document.querySelector('.ai-dependent-settings');
                if (aiDependentSettings) {
                    if (value) {
                        aiDependentSettings.style.display = 'block';
                    } else {
                        aiDependentSettings.style.display = 'none';
                    }
                }
            }
            
            // Save setting to server
            await updateSetting(setting, value);
        });
    });
    
    // Add change handler for selects
    document.querySelectorAll('select').forEach(select => {
        select.addEventListener('change', async (e) => {
            const setting = e.target.name;
            const value = e.target.value;
            
            // Save setting to server
            await updateSetting(setting, value);
        });
    });
    
    // Add change handler for sliders
    document.querySelectorAll('input[type="range"]').forEach(slider => {
        const valueDisplay = slider.nextElementSibling;
        
        // Update the display on input
        slider.addEventListener('input', (e) => {
            let value = e.target.value;
            let unit = e.target.dataset.unit || '';
            valueDisplay.textContent = value + unit;
        });
        
        // Save the value on change
        slider.addEventListener('change', async (e) => {
            const setting = e.target.name;
            const value = e.target.value;
            
            // Save setting to server
            await updateSetting(setting, value);
        });
    });
    
    // Add category management
    const addCategoryButton = document.getElementById('add-category-btn');
    if (addCategoryButton) {
        addCategoryButton.addEventListener('click', () => {
            addNewCategory();
        });
    }
    
    // Handle remove category clicks
    document.addEventListener('click', (e) => {
        if (e.target.closest('.delete-category-btn')) {
            const categoryItem = e.target.closest('.custom-category-item');
            categoryItem.remove();
            debouncedUpdateCategories();
        }
    });
    
    /**
     * Updates a user setting on the server using the API.
     * Shows success or error toast based on the result.
     * 
     * @param {string} setting - The setting key to update
     * @param {*} value - The new value for the setting
     * @return {Promise<boolean>} Success or failure of the update operation
     */
    async function updateSetting(setting, value) {
        try {
            const response = await fetch('/user/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    setting: setting,
                    value: value
                })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                showToast(`Setting updated successfully`, 'success');
                return true;
            } else {
                showToast(`Error updating setting: ${data.message}`, 'error');
                return false;
            }
        } catch (error) {
            console.error('Failed to update setting:', error);
            showToast(`Failed to update setting: ${error.message}`, 'error');
            return false;
        }
    }
    
    /**
     * Shows a toast notification to the user.
     * Creates toast element with specified message and type.
     * 
     * @param {string} message - Message to display in the toast
     * @param {string} type - Type of toast (success, error, info, warning)
     * @return {void}
     */
    function showToast(message, type = 'success') {
        // Check if toast container exists, create if not
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container';
            document.body.appendChild(toastContainer);
        }
        
        // Create toast element with proper structure
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const toastContent = document.createElement('div');
        toastContent.className = 'toast-content';
        
        const toastBody = document.createElement('div');
        toastBody.className = 'toast-body';
        toastBody.textContent = message;
        
        const closeBtn = document.createElement('button');
        closeBtn.className = 'toast-close';
        closeBtn.innerHTML = '&times;';
        closeBtn.addEventListener('click', () => {
            hideToast(toast);
        });
        
        // Assemble toast components
        toastContent.appendChild(toastBody);
        toastContent.appendChild(closeBtn);
        toast.appendChild(toastContent);
        
        // Add to container
        toastContainer.appendChild(toast);
        
        // Show with animation
        setTimeout(() => {
            toast.classList.add('show');
        }, 10);
        
        // Auto-hide after delay
        setTimeout(() => {
            hideToast(toast);
        }, 3000);
    }
    
    /**
     * Handles hiding a toast notification after display.
     * Removes the toast from DOM after animation completes.
     * 
     * @param {Element} toast - The toast element to hide
     * @return {void}
     */
    function hideToast(toast) {
        toast.classList.add('hiding');
        toast.classList.remove('show');
        
        // Remove from DOM after animation
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }
    
    /**
     * Adds a new custom category to the settings.
     * Creates UI elements for the new category and attaches event handlers.
     * 
     * @return {void}
     */
    function addNewCategory() {
        const categoriesContainer = document.querySelector('.custom-categories-list');
        const categoryCount = categoriesContainer.querySelectorAll('.custom-category-item').length;
        
        // Generate random color
        const randomColor = '#' + Math.floor(Math.random()*16777215).toString(16).padStart(6, '0');
        
        // Create new category element
        const categoryItem = document.createElement('div');
        categoryItem.className = 'custom-category-item';
        categoryItem.innerHTML = `
            <div class="category-header">
                <input type="text" 
                       name="ai_features.custom_categories[${categoryCount}].name" 
                       placeholder="e.g., Project Status"
                       class="form-input category-name">
                <input type="color"
                       name="ai_features.custom_categories[${categoryCount}].color"
                       value="${randomColor}"
                       class="form-input category-color"
                       title="Choose category color">
                <button type="button" class="delete-category-btn" title="Delete category">×</button>
            </div>
            <textarea name="ai_features.custom_categories[${categoryCount}].description" 
                      placeholder="e.g., Track the current state of project-related emails"
                      class="form-textarea category-description"
                      maxlength="100"></textarea>
            <div class="category-values">
                <input type="text" 
                       name="ai_features.custom_categories[${categoryCount}].values" 
                       placeholder="e.g., Active, On Hold, Completed"
                       class="form-input category-values-input">
            </div>
        `;
        
        // Insert before the add button if it exists
        const addButton = document.getElementById('add-category-btn');
        if (addButton) {
            categoriesContainer.insertBefore(categoryItem, addButton);
            
            // Hide add button if we've reached the limit
            if (categoryCount + 1 >= 3) {
                addButton.style.display = 'none';
            } else {
                // Update remaining count
                addButton.innerHTML = `
                    <span class="btn-icon">+</span>
                    Add Category (${3 - (categoryCount + 1)} remaining)
                `;
            }
        } else {
            categoriesContainer.appendChild(categoryItem);
        }
        
        debouncedUpdateCategories();
    }
    
    // Create debounced version of updateCategories
    const debouncedUpdateCategories = debounce(updateCategories, 500);
    
    /**
     * Updates custom categories on the server.
     * Collects and validates category data before sending to the server.
     * 
     * @return {Promise<boolean>} Whether the update was successful
     */
    async function updateCategories() {
        const categories = [];
        const categoryItems = document.querySelectorAll('.custom-category-item');
        
        categoryItems.forEach(item => {
            const name = item.querySelector('.category-name').value.trim();
            const color = item.querySelector('.category-color').value;
            const description = item.querySelector('.category-description').value.trim();
            const valuesInput = item.querySelector('.category-values-input').value.trim();
            const values = valuesInput ? valuesInput.split(',').map(v => v.trim()).filter(v => v) : [];
            
            if (name) {
                categories.push({ name, color, description, values });
            }
        });
        
        try {
            const response = await fetch('/user/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    'ai_features.custom_categories': categories
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to update categories');
            }
            
            showToast('Categories updated successfully');
        } catch (error) {
            console.error('Error updating categories:', error);
        }
    }
    
    /**
     * Creates a debounced function that delays invoking the provided function.
     * Used to prevent excessive API calls during rapid user interaction.
     * 
     * @param {Function} func - The function to debounce
     * @param {number} wait - The delay in milliseconds
     * @return {Function} The debounced function
     */
    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), wait);
        };
    }
    
    // Add input handlers for category fields
    document.addEventListener('input', (e) => {
        if (e.target.closest('.custom-category-item')) {
            debouncedUpdateCategories();
        }
    });

    // Add specific handler for color changes
    document.addEventListener('change', function(e) {
        if (e.target.classList.contains('category-color')) {
            debouncedUpdateCategories();
        }
    });
}); 