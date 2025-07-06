# PRP-05: Find in Page Feature

## Overview
Implement a find-in-page feature with a search bar that appears when triggered, supporting case-sensitive search and navigation through results.

## Scope
- Find bar UI (appears on Ctrl+F)
- Search text within current page
- Navigate between matches
- Match count display
- Case sensitivity toggle
- Whole word matching option
- Search highlighting

## Implementation Tasks
1. Create FindBar widget using AdwBin/GtkSearchBar
2. Integrate with WebKit's find controller API
3. Add keyboard shortcuts (Ctrl+F, F3, Shift+F3, Escape)
4. Implement match navigation (next/previous buttons)
5. Add match counter display
6. Add case sensitivity toggle button
7. Add whole word matching toggle
8. Style search highlighting in WebView
9. Auto-hide find bar on Escape or unfocus
10. Preserve search term during session

## Dependencies
- WebKit FindController API
- window.py for UI integration
- Keyboard shortcut handling

## Testing
- Find bar appears/hides correctly
- Search highlights all matches
- Navigation cycles through matches
- Case sensitivity works
- Match count updates correctly
- Escape key closes find bar