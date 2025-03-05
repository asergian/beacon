# JavaScript Reorganization Plan

This document outlines the specific steps to reorganize the JavaScript files according to the structure defined in README.md.

## Current Issues

- Duplicate files exist in multiple directories
- Some files are in the root directory that should be in specific folders
- The organization is inconsistent

## File Movements

### Email Module (Keep in modules/)
- Keep all files in `/modules/` directory as they are:
  - `/modules/EmailState.js`
  - `/modules/EmailUI.js`
  - `/modules/EmailService.js`
  - `/modules/EmailEvents.js`
  - `/modules/EmailUtils.js`
- Move `/emailController.js` into `/modules/` as it's part of the email module

### Page-Specific JavaScript (pages/)
- Keep the following files in `/pages/`:
  - `/pages/analytics.js`
  - `/pages/settings.js`
  - `/pages/support.js`
- Ensure no duplicate exists in the root directory

### Core App Logic (core/)
- Keep `/core/app.js` (renamed from script.js)
- Remove duplicate files:
  - Remove `/core/EmailEvents.js`
  - Remove `/core/EmailState.js`

### Components (components/)
- Keep `/components/editor.js`
- Keep `/components/logout.js`
- Remove duplicate:
  - Remove `/components/EmailUI.js`

### Services (services/)
- Remove duplicate:
  - Remove `/services/EmailService.js`

### Utils (utils/)
- Remove duplicate:
  - Remove `/utils/EmailUtils.js`

### Root Directory Cleanup
- Remove or move the following files from the root directory:
  - Move `/analytics.js` to `/pages/analytics.js` if not already there
  - Move `/settings.js` to `/pages/settings.js` if not already there
  - Move `/support.js` to `/pages/support.js` if not already there
  - Move `/script.js` to `/core/app.js` if not already there
  - Move `/editor-init.js` to `/components/editor.js` if not already there
  - Move `/logout.js` to `/components/logout.js` if not already there
  - Move `/emailController.js` to `/modules/emailController.js`

## Update Import Paths

After moving files, update import paths in the moved files to reflect their new locations.

## Next Steps

1. Check for any broken imports after reorganization
2. Consider bundling or using a module loader to simplify imports
3. Begin new development following the established structure 