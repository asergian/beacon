# JavaScript Cleanup Plan

After verifying that all the updated imports and file references work correctly, follow this plan to complete the cleanup:

## Files to Remove

These files are now duplicates and should be removed after confirming the new structure works:

1. `app/static/js/analytics.js` (moved to pages/)
2. `app/static/js/editor-init.js` (moved to components/)
3. `app/static/js/emailController.js` (moved to modules/)
4. `app/static/js/logout.js` (moved to components/)
5. `app/static/js/script.js` (moved to core/app.js)
6. `app/static/js/settings.js` (moved to pages/)
7. `app/static/js/support.js` (moved to pages/)
8. `app/static/js/backup/` (entire backup directory)

## Cleanup Command

After testing, you can use the following command to remove the duplicate files:

```bash
rm -v app/static/js/analytics.js app/static/js/editor-init.js app/static/js/emailController.js \
   app/static/js/logout.js app/static/js/script.js app/static/js/settings.js app/static/js/support.js
```

Or remove backup directory:

```bash
rm -rf app/static/js/backup
```

## Verification

Before removing files:

1. Test all pages in the application
2. Check the browser console for any JavaScript errors
3. Verify all functionality works as expected
4. Run the `check_imports.js` script in your browser console

This restructuring preserves all functionality while providing a cleaner, more maintainable JavaScript organization. 