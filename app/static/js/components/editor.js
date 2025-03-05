/**
 * @fileoverview Initializes and configures the CKEditor instance for email responses.
 * Sets up event listeners to handle theme changes and applies custom styling.
 * @author Beacon Team
 * @license Copyright 2025 Beacon
 */

document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing CKEditor...');
    
    /**
     * Create CKEditor instance with custom toolbar configuration.
     * The editor is attached to the #response-editor element.
     */
    ClassicEditor
        .create(document.querySelector('#response-editor'), {
            toolbar: [
                'undo', 'redo',
                '|', 'heading',
                '|', 'bold', 'italic',
                '|', 'link', 'insertTable',
                '|', 'bulletedList', 'numberedList',
                '|', 'indent', 'outdent',
                '|', 'blockQuote'
            ]
        })
        .then(editor => {
            // Store editor instance for later use
            window.editor = editor;
            
            // Get the editing root and apply custom styles
            const editingRoot = editor.editing.view.document.getRoot();
            
            // Set min-height on the editing root's element
            editor.editing.view.change(writer => {
                writer.setStyle('min-height', '300px', editingRoot);
            });
            
            // Update theme initially
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            updateEditorTheme(isDark);
            
            // Watch for theme changes
            const observer = new MutationObserver(mutations => {
                mutations.forEach(mutation => {
                    if (mutation.attributeName === 'data-theme') {
                        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
                        updateEditorTheme(isDark);
                    }
                });
            });
            
            observer.observe(document.documentElement, {
                attributes: true,
                attributeFilter: ['data-theme']
            });
        })
        .catch(error => {
            console.error('Editor initialization failed:', error);
        });

    /**
     * Updates the CKEditor theme based on the current application theme.
     * Adjusts colors and styling for both dark and light modes.
     * 
     * @param {boolean} isDark - Whether dark mode is active
     * @return {void}
     */
    function updateEditorTheme(isDark) {
        const editorElement = document.querySelector('.ck-editor__editable');
        if (editorElement) {
            if (isDark) {
                // Dark mode styles for the editor content area
                editorElement.style.backgroundColor = '#2d2d2d';
                editorElement.style.color = '#f5f5f5';
                editorElement.style.borderColor = '#444';
                
                // Table styling is now handled by CSS
            } else {
                // Light mode styles for the editor content area
                editorElement.style.backgroundColor = '#ffffff';
                editorElement.style.color = '#333333';
                editorElement.style.borderColor = '#c4c4c4';
                
                // Table styling is now handled by CSS
            }
        }
        
        // Style the toolbar in dark mode
        const toolbar = document.querySelector('.ck-toolbar');
        if (toolbar) {
            if (isDark) {
                toolbar.style.backgroundColor = '#333';
                toolbar.style.borderColor = '#444';
                toolbar.style.color = '#E4E6EB';
            } else {
                toolbar.style.backgroundColor = '';
                toolbar.style.borderColor = '';
                toolbar.style.color = '';
            }
        }
        
        // Style dropdown panels and button elements in dark mode
        if (isDark) {
            // Apply styles to all button and dropdown elements
            document.querySelectorAll('.ck-button, .ck-dropdown__button').forEach(element => {
                element.style.color = '#E4E6EB';
                element.style.backgroundColor = '#333';
                
                // Add hover event to create better contrast on hover
                element.addEventListener('mouseover', () => {
                    element.style.backgroundColor = '#444';
                });
                
                element.addEventListener('mouseout', () => {
                    element.style.backgroundColor = '#333';
                });
            });
            
            // Style dropdown panels when they appear
            const observer = new MutationObserver(mutations => {
                // Style all dropdown panels
                document.querySelectorAll('.ck-dropdown__panel').forEach(panel => {
                    panel.style.backgroundColor = '#333';
                    panel.style.borderColor = '#444';
                    
                    // Style items inside the dropdown
                    panel.querySelectorAll('.ck-list__item').forEach(item => {
                        item.style.color = '#E4E6EB';
                        
                        item.addEventListener('mouseover', () => {
                            item.style.backgroundColor = '#444';
                        });
                        
                        item.addEventListener('mouseout', () => {
                            item.style.backgroundColor = '#333';
                        });
                    });
                });
                
                // Specifically target the headings dropdown
                document.querySelectorAll('.ck-heading-dropdown .ck-dropdown__panel').forEach(panel => {
                    panel.style.backgroundColor = '#333';
                    panel.style.borderColor = '#444';
                    
                    // Style heading options in the dropdown
                    panel.querySelectorAll('.ck-list__item').forEach(item => {
                        item.style.color = '#E4E6EB';
                        
                        // Get heading buttons
                        const button = item.querySelector('button');
                        if (button) {
                            button.style.color = '#E4E6EB';
                        }
                        
                        // Add hover styling
                        item.addEventListener('mouseover', () => {
                            item.style.backgroundColor = '#444';
                        });
                        
                        item.addEventListener('mouseout', () => {
                            item.style.backgroundColor = '#333';
                        });
                    });
                });
                
                // Style table dropdown panels
                document.querySelectorAll('.ck-insert-table-dropdown__grid').forEach(grid => {
                    grid.style.backgroundColor = '#333';
                    
                    // Style table size label
                    const label = document.querySelector('.ck-insert-table-dropdown__label');
                    if (label) {
                        label.style.color = '#E4E6EB';
                    }
                });
            });
            
            // Watch for dropdown panels being added to the DOM
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        }
    }
}); 