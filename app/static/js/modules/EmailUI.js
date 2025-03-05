/**
 * @fileoverview Handles UI-related functionality for displaying and interacting with emails.
 * This module provides methods for rendering emails in the UI, updating email details,
 * and handling various UI interactions related to emails.
 * @author Beacon Team
 * @license Copyright 2025 Beacon
 */

import { formatTagText, formatDate, showToast, extractEmailAddress } from './EmailUtils.js';
import { EmailState } from './EmailState.js';

/**
 * EmailUI - Handles UI-related functionality for the email application.
 * Manages the rendering and interaction with email elements in the DOM.
 * @namespace
 */
export const EmailUI = {
    /**
     * Clears the email list in the UI.
     * Removes all email items from the list container.
     * 
     * @return {void}
     */
    clearEmailList() {
        const emailList = document.querySelector('.email-list');
        if (emailList) {
            emailList.innerHTML = '';
        }
    },
    
    /**
     * Renders the email list from the current state.
     * Sorts emails by date and creates list items for each email.
     * Displays a message if no emails are available.
     * 
     * @return {void}
     */
    renderEmailList() {
        const emailList = document.querySelector('.email-list');
        if (!emailList) return;
        
        // Clear existing list
        this.clearEmailList();
        
        // Get emails from state
        const emails = EmailState.emails;
        if (!emails || emails.length === 0) {
            emailList.innerHTML = '<li class="no-emails">No emails to display</li>';
            return;
        }
        
        // Sort emails by date (newest first)
        const sortedEmails = [...emails].sort((a, b) => 
            new Date(b.date || 0) - new Date(a.date || 0)
        );
        
        // Create email list items
        sortedEmails.forEach(email => {
            const emailItem = document.createElement('li');
            emailItem.className = 'email-item';
            if (email.needs_action) emailItem.classList.add('needs-action');
            emailItem.setAttribute('data-email-id', email.id);
            
            const date = email.date ? new Date(email.date) : new Date();
            const formattedDate = formatDate(date);
            
            // Create the email item HTML with proper structure
            emailItem.innerHTML = `
                <div class="email-header">
                    <div class="subject-date">
                        <div class="email-subject">${email.subject || 'No Subject'}</div>
                        <div class="date">${formattedDate}</div>
                    </div>
                    <div class="sender-name">${email.sender || 'Unknown Sender'}</div>
                </div>
                <div class="tags-container">
                    <span class="tag priority-${(email.priority_level || 'medium').toLowerCase()}">${formatTagText(email.priority_level || 'medium')}</span>
                    <span class="tag category" data-category="${email.category || 'Informational'}">${formatTagText(email.category || 'Informational')}</span>
                    ${email.needs_action ? '<span class="tag action-required">Action Required</span>' : ''}
                    ${email.responded ? '<span class="tag responded-badge">Responded</span>' : ''}
                    ${email.custom_categories && Object.entries(email.custom_categories)
                        .filter(([name, value]) => value !== null)
                        .map(([name, value]) => {
                            const categoryConfig = EmailState.userSettings?.ai_features?.custom_categories?.find(c => c.name === name);
                            const color = categoryConfig?.color || '#8B5CF6';  // Default to purple if no color set
                            return `<span class="tag custom-category" data-category="${name}" style="background-color: ${color}">${formatTagText(value)}</span>`;
                        }).join('') || ''}
                </div>
                <div class="email-summary-preview">${email.summary || 'No summary available'}</div>
            `;
            
            // Add click event listener to load email details
            emailItem.addEventListener('click', () => {
                this.loadEmailDetails(email.id);
            });
            
            emailList.appendChild(emailItem);
        });
        
        // If we have a selected email, mark it as selected
        if (EmailState.selectedEmailId) {
            const selectedItem = emailList.querySelector(`.email-item[data-email-id="${EmailState.selectedEmailId}"]`);
            if (selectedItem) {
                selectedItem.classList.add('active');
            }
        } else if (sortedEmails.length > 0) {
            // If no email is selected, select the first one
            this.loadEmailDetails(sortedEmails[0].id);
        }
    },
    
    /**
     * Clears the email details in the UI
     */
    clearEmailDetails() {
        const detailsElements = {
            subject: document.getElementById('details-subject'),
            sender: document.getElementById('details-sender'),
            date: document.getElementById('details-date'),
            priority: document.getElementById('details-priority'),
            category: document.getElementById('details-category'),
            actionRequired: document.getElementById('details-action-required'),
            summary: document.getElementById('details-summary'),
            keyDates: document.getElementById('key-dates-list'),
            emailBody: document.getElementById('email-body')
        };
        
        Object.values(detailsElements).forEach(element => {
            if (element) {
                if (element.textContent !== undefined) element.textContent = '';
                if (element.style.display !== undefined) element.style.display = 'none';
            }
        });
        
        // Cleanup any existing iframe
        if (window.currentIframe) {
            window.currentIframe.cleanup?.();
            window.currentIframe.remove();
            window.currentIframe = null;
        }
    },

    /**
     * Loads and displays the details of an email
     * @param {string} emailId - ID of the email to load
     */
    loadEmailDetails(emailId) {
        // Clear previous details
        this.clearEmailDetails();
        
        // Get email from state
        const email = EmailState.getEmailById(emailId);
        if (!email) {
            console.error(`Email with ID ${emailId} not found`);
            return;
        }
        
        // Update selected state in UI
        const previousSelected = document.querySelector('.email-item.active');
        if (previousSelected) {
            previousSelected.classList.remove('active');
        }
        
        const emailItem = document.querySelector(`.email-item[data-email-id="${emailId}"]`);
        if (emailItem) {
            emailItem.classList.add('active');
        }
        
        // Store selected email ID
        EmailState.setSelectedEmailId(emailId);
        
        // Define details elements
        const detailsElements = {
            subject: document.getElementById('details-subject'),
            sender: document.getElementById('details-sender'),
            date: document.getElementById('details-date'),
            priority: document.getElementById('details-priority'),
            category: document.getElementById('details-category'),
            actionRequired: document.getElementById('details-action-required'),
            customCategories: document.getElementById('details-custom-categories'),
            summary: document.getElementById('details-summary'),
            keyDates: document.getElementById('key-dates-list'),
            emailBody: document.getElementById('email-body')
        };
        
        requestAnimationFrame(() => {
            // Show all detail elements with appropriate display values
            detailsElements.subject.style.display = 'block';
            detailsElements.sender.style.display = 'block';
            detailsElements.date.style.display = 'block';
            detailsElements.priority.style.display = 'inline-flex';
            detailsElements.category.style.display = 'inline-flex';
            detailsElements.summary.style.display = 'block';
            
            // Update subject with a wrapper to create a flex container
            const subjectEl = detailsElements.subject;
            subjectEl.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span>${email.subject || 'No Subject'}</span>
                    <span style="font-size: 0.8rem; color: var(--text-muted); white-space: nowrap; margin-left: 10px;">
                        ${email.date ? new Date(email.date).toLocaleString() : 'Unknown Date'}
                    </span>
                </div>
            `;
            
            // Set sender info only
            detailsElements.sender.textContent = email.sender || 'Unknown Sender';
            
            // Hide original date element since we're displaying it with the subject
            detailsElements.date.style.display = 'none';
            
            // Populate response fields
            const responseToField = document.getElementById('response-to');
            if (responseToField && email.sender) {
                // Extract email address from sender (which might be in format "Name <email@example.com>")
                const senderEmail = extractEmailAddress(email.sender);
                if (senderEmail) {
                    responseToField.value = senderEmail;
                } else {
                    responseToField.value = email.sender;
                }
            }
            
            const responseSubjectField = document.getElementById('response-subject');
            if (responseSubjectField && email.subject) {
                // Add Re: prefix if not already present
                const subject = email.subject.startsWith('Re:') ? email.subject : `Re: ${email.subject}`;
                responseSubjectField.value = subject;
            }
            
            const priorityLevel = (email.priority_level || 'pending').toLowerCase();
            detailsElements.priority.textContent = formatTagText(email.priority_level || 'pending');
            detailsElements.priority.className = `tag priority-${priorityLevel}`;
            
            detailsElements.category.textContent = formatTagText(email.category || 'uncategorized');
            detailsElements.category.setAttribute('data-category', email.category || 'Informational');
            
            if (email.needs_action) {
                detailsElements.actionRequired.textContent = 'Action Required';
                detailsElements.actionRequired.style.display = 'inline-flex';
            } else {
                detailsElements.actionRequired.style.display = 'none';
            }
            
            // Handle custom categories with colors from user settings
            if (email.custom_categories && Object.keys(email.custom_categories).length > 0) {
                const customCategoriesConfig = EmailState.userSettings?.ai_features?.custom_categories || [];
                detailsElements.customCategories.innerHTML = Object.entries(email.custom_categories)
                    .filter(([name, value]) => value !== null)
                    .map(([name, value]) => {
                        const categoryConfig = customCategoriesConfig.find(c => c.name === name);
                        const color = categoryConfig?.color || '#8B5CF6';  // Default to purple if no color set
                        return `<span class="tag custom-category" data-category="${name}" style="background-color: ${color}">${formatTagText(value)}</span>`;
                    })
                    .join('');
                detailsElements.customCategories.style.display = 'inline-flex';
            } else {
                detailsElements.customCategories.style.display = 'none';
            }
            
            detailsElements.summary.textContent = email.summary || 'No summary available';
            
            // Display email body content
            if (email.body) {
                detailsElements.emailBody.style.display = 'block';
                
                // Add a loading indicator first
                const loadingIndicator = document.createElement('div');
                loadingIndicator.className = 'email-loading';
                loadingIndicator.innerHTML = '<span>Loading email content...</span>';
                detailsElements.emailBody.appendChild(loadingIndicator);
                
                // Create a sandboxed iframe for email content
                const iframe = document.createElement('iframe');
                iframe.style.width = '100%';
                iframe.style.height = '0'; // Start at zero and grow to fit content
                iframe.style.border = 'none';
                iframe.style.backgroundColor = 'transparent';
                
                // Set attributes for proper display
                iframe.setAttribute('scrolling', 'no');
                
                // Allow more features to preserve email functionality
                iframe.setAttribute('sandbox', 'allow-same-origin allow-scripts allow-popups');
                
                // Add iframe to DOM
                detailsElements.emailBody.appendChild(iframe);
                
                // Store reference to current iframe for cleanup
                window.currentIframe = iframe;
                
                // Write content to iframe
                const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                iframeDoc.open();
                iframeDoc.write(`
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <style>
                            /* Minimal reset - only essential styles */
                            html, body {
                                margin: 0;
                                padding: 0;
                                width: 100%;
                            }
                            
                            body {
                                font-family: inherit;
                                line-height: inherit;
                                color: inherit;
                            }
                            
                            /* Only set max-width for images to prevent overflow */
                            img {
                                max-width: 100%;
                            }
                        </style>
                    </head>
                    <body>
                        ${email.body}
                    </body>
                    </html>
                `);
                iframeDoc.close();
                
                // Adjust iframe height based on content
                iframe.onload = () => {
                    // Remove loading indicator when content is ready
                    const loadingEl = detailsElements.emailBody.querySelector('.email-loading');
                    if (loadingEl) {
                        loadingEl.remove();
                    }
                    
                    // Function to recalculate height
                    const adjustHeight = () => {
                        try {
                            // Get just the scrollHeight - simplest approach
                            const body = iframe.contentWindow.document.body;
                            const docHeight = body.scrollHeight;
                            
                            // Set iframe height with minimal buffer
                            iframe.style.height = `${docHeight + 5}px`;
                        } catch (e) {
                            console.error('Error adjusting iframe height:', e);
                        }
                    };
                    
                    // Initial adjustment
                    adjustHeight();
                    
                    // Also check after images load which can change height
                    const images = iframe.contentWindow.document.images;
                    let imagesLoaded = 0;
                    const totalImages = images.length;
                    
                    if (totalImages > 0) {
                        for (let i = 0; i < totalImages; i++) {
                            if (images[i].complete) {
                                imagesLoaded++;
                            } else {
                                images[i].onload = () => {
                                    imagesLoaded++;
                                    if (imagesLoaded === totalImages) {
                                        // Recalculate height after all images load
                                        adjustHeight();
                                    }
                                };
                            }
                        }
                        
                        // If all images already loaded, recalculate immediately
                        if (imagesLoaded === totalImages) {
                            adjustHeight();
                        }
                    }
                };
            } else {
                detailsElements.emailBody.innerHTML = '<p class="no-content">No email content available</p>';
                detailsElements.emailBody.style.display = 'block';
            }
            
            // Render key dates if available
            if (email.key_dates && email.key_dates.length > 0) {
                const keyDatesList = detailsElements.keyDates;
                keyDatesList.innerHTML = '';
                
                email.key_dates.forEach(date => {
                    const li = document.createElement('li');
                    if (date.important) li.classList.add('important');
                    li.textContent = date.description;
                    keyDatesList.appendChild(li);
                });
                
                keyDatesList.style.display = 'block';
            } else {
                detailsElements.keyDates.style.display = 'none';
            }
            
            // Add action items section after the summary section if they exist
            if (email.action_items && email.action_items.length > 0) {
                // Check if action items section already exists, if not create it
                let actionItemsSection = document.querySelector('.action-items-section');
                if (!actionItemsSection) {
                    actionItemsSection = document.createElement('div');
                    actionItemsSection.className = 'summary-section action-items-section';
                    actionItemsSection.style.borderTop = '1px dashed var(--border-color)';
                    actionItemsSection.style.marginTop = '15px';
                    actionItemsSection.style.paddingTop = '15px';
                    
                    // Create heading
                    const heading = document.createElement('h3');
                    heading.textContent = 'Action Items';
                    actionItemsSection.appendChild(heading);
                    
                    // Create list
                    const actionItemsList = document.createElement('ul');
                    actionItemsList.id = 'action-items-list';
                    actionItemsList.className = 'action-items-list';
                    // Remove the border-top from the list since we added it to the section
                    actionItemsList.style.borderTop = 'none';
                    actionItemsList.style.paddingTop = '0';
                    actionItemsSection.appendChild(actionItemsList);
                    
                    // Add to DOM after summary section
                    const summarySection = document.querySelector('.summary-section');
                    if (summarySection && summarySection.parentNode) {
                        summarySection.parentNode.insertBefore(actionItemsSection, summarySection.nextSibling);
                    } else {
                        // Fallback if summary section not found
                        const detailsMeta = document.querySelector('.email-meta');
                        if (detailsMeta) {
                            detailsMeta.appendChild(actionItemsSection);
                        }
                    }
                }
                
                // Populate action items
                const actionItemsList = document.getElementById('action-items-list');
                if (actionItemsList) {
                    actionItemsList.innerHTML = '';
                    
                    email.action_items.forEach(item => {
                        const li = document.createElement('li');
                        li.className = 'action-item';
                        
                        // Handle different item formats
                        if (typeof item === 'string') {
                            li.textContent = item;
                        } else if (typeof item === 'object') {
                            if (item.text) {
                                li.textContent = item.text;
                            } else if (item.description) {
                                li.textContent = item.description;
                            } else if (item.action) {
                                li.textContent = item.action;
                            } else if (item.item) {
                                li.textContent = item.item;
                            } else {
                                // Try to stringify the object in a readable way
                                try {
                                    // Filter out null/undefined values and internal properties
                                    const filtered = Object.entries(item)
                                        .filter(([key, val]) => val != null && !key.startsWith('_'))
                                        .reduce((obj, [key, val]) => {
                                            obj[key] = val;
                                            return obj;
                                        }, {});
                                    
                                    if (Object.keys(filtered).length > 0) {
                                        li.textContent = Object.values(filtered)[0]; // Use first non-null value
                                    } else {
                                        li.textContent = "Action required";
                                    }
                                } catch (error) {
                                    li.textContent = "Action required";
                                    console.error("Error processing action item:", error);
                                }
                            }
                            
                            // Add due date if available
                            if (item.due_date || item.due) {
                                const dueDateSpan = document.createElement('span');
                                dueDateSpan.className = 'action-item-due';
                                dueDateSpan.textContent = item.due_date || item.due;
                                
                                // Create a header div to hold the action and due date
                                const headerDiv = document.createElement('div');
                                headerDiv.className = 'action-item-header';
                                
                                // Set the title in a span
                                const titleSpan = document.createElement('span');
                                titleSpan.className = 'action-item-title';
                                titleSpan.textContent = li.textContent;
                                
                                // Clear the li and append the structured content
                                li.textContent = '';
                                headerDiv.appendChild(titleSpan);
                                headerDiv.appendChild(dueDateSpan);
                                li.appendChild(headerDiv);
                            }
                        }
                        
                        // Add important class if needed
                        if ((typeof item === 'object' && 
                            (item.important || 
                             item.priority === 'high' || 
                             item.urgent))) {
                            li.classList.add('important');
                        }
                        
                        actionItemsList.appendChild(li);
                    });
                }
            } else {
                // Remove action items section if it exists but there are no items
                const actionItemsSection = document.querySelector('.action-items-section');
                if (actionItemsSection) {
                    actionItemsSection.remove();
                }
            }
        });
    },
    
    /**
     * Filters emails based on filter criteria
     */
    filterEmails() {
        const priorityFilter = document.getElementById('priority-filter');
        const categoryFilter = document.getElementById('category-filter');
        const actionFilter = document.getElementById('action-filter');
        
        if (!priorityFilter && !categoryFilter && !actionFilter) return;
        
        const priority = priorityFilter ? priorityFilter.value : 'all';
        const category = categoryFilter ? categoryFilter.value : 'all';
        const action = actionFilter ? actionFilter.value : 'all';
        
        const items = document.querySelectorAll('.email-item');
        
        items.forEach(item => {
            // Get the email from state to check all properties
            const emailId = item.getAttribute('data-email-id');
            if (!emailId) return;
            
            const email = EmailState.getEmailById(emailId);
            if (!email) return;
            
            // Check priority
            const priorityMatch = priority === 'all' || 
                                 (email.priority_level && email.priority_level.toLowerCase() === priority.toLowerCase());
            
            // Check category
            const categoryMatch = category === 'all' || 
                                 (email.category && email.category.toLowerCase() === category.toLowerCase());
            
            // Check action required
            const actionMatch = action === 'all' || 
                               (action === 'required' && email.needs_action) || 
                               (action === 'none' && !email.needs_action);
            
            // Show or hide based on all filters
            item.style.display = priorityMatch && categoryMatch && actionMatch ? 'flex' : 'none';
        });
    },
    
    /**
     * Updates the email item UI after sending a response
     * @param {string} emailId - ID of the email to update
     */
    updateEmailItemUI(emailId) {
        const emailItem = document.querySelector(`.email-item[data-email-id="${emailId}"]`);
        if (!emailItem) return;

        // Add responded badge to email header if not already present
        const emailHeader = emailItem.querySelector('.tags-container');
        if (emailHeader && !emailHeader.querySelector('.responded-badge')) {
            const badge = document.createElement('span');
            badge.className = 'tag responded-badge';
            badge.textContent = 'Responded';
            emailHeader.appendChild(badge);
        }

        // Update the needs-action class
        emailItem.classList.remove('needs-action');
    }
}; 