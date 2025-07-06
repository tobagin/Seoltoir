# PRP-03: Address Bar (Omnibox) Enhancement

## Overview
Transform the current URL entry into a full-featured omnibox with search suggestions, autocomplete, and security indicators.

## Scope
- URL entry with validation
- Search query detection and handling
- Autocomplete from history and bookmarks
- Search engine suggestions
- Security status indicators (HTTPS padlock)
- Progress bar integration
- URL formatting and display

## Implementation Tasks
1. Create OmniboxEntry widget extending AdwEntryRow
2. Implement URL vs search query detection
3. Add autocomplete popup with suggestions
4. Integrate with history_manager for URL suggestions
5. Integrate with bookmark_manager for bookmark suggestions
6. Add search engine API integration for suggestions
7. Implement security status icons (padlock, warning)
8. Add progress bar overlay during page load
9. Implement smart URL formatting (hide https://, show full on focus)
10. Add keyboard navigation for suggestions

## Dependencies
- history_manager.py for URL history
- bookmark_manager.py for bookmarks
- Search engine configuration in settings
- WebKit load progress signals

## Testing
- URL autocomplete from history
- Search suggestions appear correctly
- Security indicators match page security
- Progress bar tracks page load
- Keyboard navigation through suggestions
- Search query handling with default engine