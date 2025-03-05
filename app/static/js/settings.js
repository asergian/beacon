document.addEventListener('DOMContentLoaded', function() {
    // Add click handlers for value buttons
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
    
    // Add change handler for toggle switches
    document.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
        checkbox.addEventListener('change', async (e) => {
            const setting = e.target.name;
            const value = e.target.checked ? 'dark' : 'light';
            
            if (setting === 'theme') {
                // Update theme immediately
                document.documentElement.setAttribute('data-theme', value);
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
    const addCategoryButton = document.getElementById('add-category');
    if (addCategoryButton) {
        addCategoryButton.addEventListener('click', () => {
            addNewCategory();
        });
    }
    
    // Handle remove category clicks
    document.addEventListener('click', (e) => {
        if (e.target.closest('.remove-category')) {
            const categoryItem = e.target.closest('.custom-category-item');
            categoryItem.remove();
            debouncedUpdateCategories();
        }
    });
    
    // API function to update settings
    async function updateSetting(setting, value) {
        try {
            // Create a payload object with the setting as the key
            const payload = {};
            payload[setting] = value;
            
            const response = await fetch('/user/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload)
            });
            
            if (!response.ok) {
                throw new Error('Failed to update setting');
            }
            
            showToast('Settings updated successfully');
        } catch (error) {
            console.error('Error updating setting:', error);
        }
    }
    
    // Function to show toast notification
    function showToast(message) {
        // Remove any existing toasts
        const existingToast = document.querySelector('.toast');
        if (existingToast) {
            existingToast.remove();
        }
        
        // Create and add toast
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        document.body.appendChild(toast);
        
        // Remove toast after animation completes
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
    
    // Function to add a new category
    function addNewCategory() {
        const categoriesContainer = document.querySelector('.custom-categories');
        const categoryCount = categoriesContainer.querySelectorAll('.custom-category-item').length;
        
        // Generate random color
        const randomColor = '#' + Math.floor(Math.random()*16777215).toString(16).padStart(6, '0');
        
        // Create new category element
        const categoryItem = document.createElement('div');
        categoryItem.className = 'custom-category-item';
        categoryItem.innerHTML = `
            <input type="color" class="category-color" value="${randomColor}">
            <input type="text" class="category-name" placeholder="Category name" value="New Category ${categoryCount + 1}">
            <button type="button" class="remove-category">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        `;
        
        categoriesContainer.appendChild(categoryItem);
        debouncedUpdateCategories();
    }
    
    // Create debounced version of updateCategories
    const debouncedUpdateCategories = debounce(updateCategories, 500);
    
    // Function to update custom categories
    async function updateCategories() {
        const categories = [];
        const categoryItems = document.querySelectorAll('.custom-category-item');
        
        categoryItems.forEach(item => {
            const color = item.querySelector('.category-color').value;
            const name = item.querySelector('.category-name').value.trim();
            
            if (name) {
                categories.push({ name, color });
            }
        });
        
        try {
            const response = await fetch('/user/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    setting: 'custom_categories',
                    value: categories
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
    
    // Debounce function to limit API calls
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