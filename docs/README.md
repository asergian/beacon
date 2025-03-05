# JavaScript Structure

This directory contains all the JavaScript code for the Beacon application, organized as follows:

## Structure

- **core/** - Core application logic and initialization
  - Contains main app initialization, global state, and shared event handling

- **modules/** - Feature-specific modules
  - Contains self-contained feature modules like email (EmailState, EmailUI, EmailEvents, etc.)
  
- **components/** - Reusable UI components
  - Contains modular UI elements and their related functionality
  
- **services/** - Data services and API integrations
  - Contains code for fetching data, interacting with backends, and processing
  
- **utils/** - Utility functions and helpers
  - Contains reusable utility functions, formatters, etc.
  
- **pages/** - Page-specific JavaScript
  - Contains code specific to individual pages
  
- **lib/** - Third-party libraries
  - Contains external libraries and dependencies

## Email Module

The email module is a cohesive unit that handles all email-related functionality:

- **EmailState.js** - Manages the state and data of emails
- **EmailUI.js** - Handles UI rendering and updates for emails
- **EmailService.js** - Manages API calls and data fetching for emails 
- **EmailEvents.js** - Handles event setup and SSE connections
- **EmailUtils.js** - Provides utility functions for email processing
- **emailController.js** - Entry point that coordinates the email module

## Best Practices

1. Import dependencies using ES6 import/export
2. Keep files focused on a single responsibility
3. Place new code in the appropriate directory based on its purpose
4. Use consistent naming conventions
