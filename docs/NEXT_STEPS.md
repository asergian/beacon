# Next Steps for JavaScript Reorganization

The files have been reorganized according to our plan, with:

1. All email module files are now in the `/modules/` directory
2. Page-specific files are in the `/pages/` directory
3. Core app logic in the `/core/` directory
4. UI components in the `/components/` directory

## Update Import Paths

The next step is to update import paths in all JavaScript files. This needs to be done carefully to ensure no broken references.

### Email Module (modules/)

The following files may need updated import paths:

- `EmailState.js` - Imports from EmailUI.js, etc.
- `EmailUI.js` - Imports from EmailUtils.js, EmailState.js, etc.
- `EmailService.js` - Imports from EmailUtils.js, etc.
- `EmailEvents.js` - Imports from EmailState.js, EmailService.js, EmailUtils.js, etc.
- `emailController.js` - Imports all email module files

### Original Files in Root Directory

The files remaining in the root directory are now duplicates and should be updated in your HTML templates to reference the new structure:

- Update references to `/static/js/analytics.js` → `/static/js/pages/analytics.js`
- Update references to `/static/js/editor-init.js` → `/static/js/components/editor.js`
- Update references to `/static/js/emailController.js` → `/static/js/modules/emailController.js`
- Update references to `/static/js/logout.js` → `/static/js/components/logout.js`
- Update references to `/static/js/script.js` → `/static/js/core/app.js`
- Update references to `/static/js/settings.js` → `/static/js/pages/settings.js`
- Update references to `/static/js/support.js` → `/static/js/pages/support.js`

## Testing

After updating import paths:

1. Test all pages to ensure JavaScript functionality works correctly
2. Check browser console for any errors related to import paths
3. Fix any issues that arise from the reorganization

## Final Cleanup

Once all tests pass and the app is working correctly with the new structure:

1. Remove the duplicate files from the root directory
2. Update documentation to reflect the new structure
3. Remove the backup directory that was created during the reorganization 