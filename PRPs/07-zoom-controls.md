# PRP-07: Zoom Controls and Per-Site Settings

## Overview
Implement zoom controls with per-site zoom level persistence and easy access controls.

## Scope
- Zoom in/out functionality
- Per-site zoom level storage
- Zoom reset to 100%
- Zoom indicator in UI
- Keyboard shortcuts
- Touch gesture support (pinch zoom)

## Implementation Tasks
1. Add zoom controls to hamburger menu
2. Implement zoom level indicator in address bar
3. Create zoom level database table
4. Implement per-site zoom persistence
5. Add keyboard shortcuts (Ctrl+Plus, Ctrl+Minus, Ctrl+0)
6. Add touch gesture handling for pinch zoom
7. Implement smooth zoom animations
8. Add zoom presets (50%, 75%, 100%, 125%, 150%, 200%)
9. Store default zoom level in GSettings
10. Add zoom level to site information popover

## Dependencies
- WebKit zoom level API
- database.py for per-site storage
- Touch gesture recognition
- UI updates for zoom indicator

## Testing
- Zoom levels persist per domain
- Keyboard shortcuts work correctly
- Zoom reset returns to 100%
- Touch gestures work on touchscreen
- Zoom indicator updates in real-time
- Text remains readable at all zoom levels