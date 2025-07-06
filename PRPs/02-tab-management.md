# PRP-02: Tab Management System

## Overview
Implement a full-featured tab management system with support for multiple tabs, tab switching, reordering, and visual indicators.

## Scope
- Tab bar UI with AdwTabView
- Create/close tabs
- Switch between tabs
- Drag-and-drop tab reordering
- Pin/unpin tabs
- Audio indicators and mute controls
- Loading indicators
- Tab tooltips with page titles

## Implementation Tasks
1. Replace single WebView with AdwTabView/AdwTabBar
2. Create TabPage class to manage per-tab WebView instances
3. Implement tab creation/deletion logic
4. Add tab context menu (close, pin, mute, duplicate)
5. Implement tab state indicators (loading, audio, etc.)
6. Add keyboard shortcuts (Ctrl+T, Ctrl+W, Ctrl+Tab, etc.)
7. Implement tab restoration on crash/restart
8. Add middle-click to close tab
9. Implement tab grouping UI (future enhancement)

## Dependencies
- Refactor window.py to support multiple WebViews
- Update browser_view.py to work with tab system
- Session management for tab persistence

## Testing
- Create/close multiple tabs
- Drag tabs to reorder
- Pin/unpin tabs persist across restarts
- Audio indicators appear when media plays
- Memory usage with many tabs
- Tab restoration after crash