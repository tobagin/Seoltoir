# Pull Request Plan Index

This index provides an overview of all planned pull requests for the Seoltoir browser project. PRPs are ordered by priority and dependencies.

## Phase 1: Core Browser Functionality
Essential features needed for basic browser operation.

- [PRP-01: Core Navigation Features](01-core-navigation.md) - Back/forward, reload, home button
- [PRP-02: Tab Management System](02-tab-management.md) - Multiple tabs, switching, indicators
- [PRP-03: Address Bar (Omnibox) Enhancement](03-address-bar-omnibox.md) - URL entry, search, autocomplete

## Phase 2: Essential Features
Features expected in a modern browser.

- [PRP-05: Find in Page](05-find-in-page.md) - Search within current page
- [PRP-07: Zoom Controls](07-zoom-controls.md) - Per-site zoom levels
- [PRP-08: Context Menus](08-context-menus.md) - Right-click menus for elements
- [PRP-09: Printing Support](09-printing-support.md) - Print and PDF export

## Phase 3: Privacy & Security
Privacy-focused features that differentiate Seoltoir.

- [PRP-04: Enhanced Privacy Features](04-enhanced-privacy-features.md) - Advanced cookie and permission management
- [PRP-12: Password Management](12-password-management.md) - Secure password storage and autofill

## Phase 4: User Experience
Enhanced user experience features.

- [PRP-06: Reader Mode](06-reader-mode.md) - Distraction-free reading
- [PRP-10: Search Engine Management](10-search-engine-management.md) - Custom search engines
- [PRP-11: Desktop Notifications](11-desktop-notifications.md) - Web notifications support

## Phase 5: Advanced Features
Advanced functionality for power users.

- [PRP-13: Developer Tools](13-developer-tools.md) - Web Inspector integration
- [PRP-14: Media Enhancements](14-media-enhancements.md) - PiP mode and media controls
- [PRP-15: Performance Optimization](15-performance-optimization.md) - Memory and resource management

## Implementation Notes

1. **Dependencies**: Each PRP should be implemented in order within its phase, but phases can be worked on in parallel by different developers.

2. **Testing**: Each PRP includes specific testing requirements that must be verified before merging.

3. **Architecture**: PRPs are designed to build upon the existing codebase structure documented in CLAUDE.md.

4. **Privacy First**: All features should be implemented with privacy as the default, following the browser's core philosophy.

5. **GNOME HIG**: All UI elements must conform to GNOME Human Interface Guidelines and use Libadwaita patterns.