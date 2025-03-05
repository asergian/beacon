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
                editorElement.style.backgroundColor = '#2d2d2d';
                editorElement.style.color = '#f5f5f5';
                editorElement.style.borderColor = '#444';
            } else {
                editorElement.style.backgroundColor = '#ffffff';
                editorElement.style.color = '#333333';
                editorElement.style.borderColor = '#c4c4c4';
            }
        }
        
        // Also style the toolbar in dark mode
        const toolbar = document.querySelector('.ck-toolbar');
        if (toolbar && isDark) {
            toolbar.style.backgroundColor = '#333';
            toolbar.style.borderColor = '#444';
        }
    }
}); 