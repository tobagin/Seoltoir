# PRP-04: Enhanced Privacy Features

## Overview
Expand the existing privacy features with advanced cookie management, permission controls, and JavaScript blocking.

## Scope
- Per-site cookie settings
- Granular permission management UI
- JavaScript toggle (global and per-site)
- Enhanced private browsing mode
- Do Not Track header
- Automatic cookie deletion options

## Implementation Tasks
1. Create site permissions database schema
2. Implement per-site settings manager
3. Create permissions dialog UI (AdwPreferencesWindow)
4. Add site-specific cookie controls
5. Implement JavaScript blocking toggle
6. Add permission prompts for camera/microphone/location
7. Enhance private browsing to use separate WebKit context
8. Add "Clear on exit" options for cookies/cache/history
9. Implement Do Not Track header injection
10. Create site information popover (click padlock)

## Dependencies
- database.py for permissions storage
- WebKit permission request APIs
- Update container_manager.py for private mode
- GSettings schema for privacy defaults

## Testing
- Per-site settings persist correctly
- JavaScript blocking works per-site
- Permission prompts appear and save choices
- Private mode uses isolated storage
- Cookie deletion on exit works
- DNT header present in requests