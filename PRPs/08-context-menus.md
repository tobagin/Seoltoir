# PRP-08: Context Menus

## Overview
Implement right-click context menus for various web elements with appropriate actions for links, images, text, and general page areas.

## Scope
- Link context menu (open in new tab, copy link, etc.)
- Image context menu (save image, copy image, etc.)
- Text selection menu (copy, search, etc.)
- Page context menu (back, forward, reload, etc.)
- Media context menu (play/pause, save video, etc.)

## Implementation Tasks
1. Override WebKit default context menu
2. Create context menu builder based on hit test results
3. Implement link actions (open, new tab, copy URL)
4. Implement image actions (save, copy, open in new tab)
5. Implement text selection actions (copy, search web)
6. Implement page actions (back, forward, save page)
7. Add media controls for audio/video elements
8. Implement "Inspect Element" for developer mode
9. Add keyboard navigation for context menus
10. Style menus with Libadwaita theme

## Dependencies
- WebKit context menu APIs
- WebKit hit test results
- Clipboard integration
- Download manager for save actions

## Testing
- Context menus appear at cursor position
- All menu items trigger correct actions
- Keyboard navigation works
- Menu items enable/disable appropriately
- Save image/video works correctly
- Copy operations work with clipboard