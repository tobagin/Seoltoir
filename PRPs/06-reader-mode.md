# PRP-06: Reader Mode

## Overview
Implement a reader mode that strips away distractions and presents articles in a clean, readable format with customizable typography.

## Scope
- Article detection and extraction
- Reader mode UI with clean typography
- Font size and theme controls
- Reading time estimation
- Print-optimized view
- Save reader mode preference per-site

## Implementation Tasks
1. Implement article extraction algorithm (or use Readability.js)
2. Create reader mode WebView with custom CSS
3. Add reader mode toggle button in address bar
4. Create reader preferences popover (font, size, theme)
5. Implement reading time calculation
6. Add sepia, dark, and light themes
7. Store reader preferences in GSettings
8. Add keyboard shortcut (Alt+R)
9. Implement smooth transition to reader mode
10. Add "Save as PDF" option for reader view

## Dependencies
- JavaScript injection for article extraction
- Custom CSS for reader themes
- WebView for reader display
- GSettings for preferences

## Testing
- Article detection works on major sites
- Theme switching works correctly
- Font size adjustment persists
- Reading time calculation accurate
- Print view formats correctly
- Images and videos preserved appropriately