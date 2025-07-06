# PRP-14: Media Enhancements

## Overview
Implement advanced media features including Picture-in-Picture mode and enhanced media controls.

## Scope
- Picture-in-Picture (PiP) mode
- Media playback controls
- Volume control per tab
- Media codec support
- Hardware acceleration
- Media session API support

## Implementation Tasks
1. Implement PiP window using GtkWindow
2. Add PiP button overlay on videos
3. Create floating PiP controls
4. Implement per-tab volume control
5. Add media playback keyboard shortcuts
6. Enable hardware video acceleration
7. Implement media session metadata
8. Add codec support detection
9. Create media permissions handling
10. Add fullscreen video support

## Dependencies
- WebKit media APIs
- GTK window management for PiP
- Media codecs (system)
- Hardware acceleration support

## Testing
- PiP window floats above other windows
- PiP controls work correctly
- Volume controls affect only current tab
- Hardware acceleration enabled
- Media shortcuts work globally
- Fullscreen mode works properly