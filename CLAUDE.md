# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Seoltoir is a privacy-focused web browser built with Python, GTK4/Libadwaita, and WebKit6. The application emphasizes user privacy through features like ad blocking, HTTPS enforcement, and isolated browsing containers.

## Essential Commands

### Build and Run (Meson)
```bash
# Configure build
meson setup build --prefix=/usr

# Compile
meson compile -C build

# Run directly from build
meson run -C build seoltoir

# Install system-wide
sudo meson install -C build
glib-compile-schemas /usr/share/glib-2.0/schemas/
```

### Flatpak Development
```bash
# Build and install for testing
flatpak-builder --user --install build-dir packaging/io.github.tobagin.seoltoir-local.yml

# Run
flatpak run io.github.tobagin.seoltoir

# Use convenience script
./scripts/build_and_install.sh
```

### Development Tools
```bash
# Format code (when available)
black src/seoltoir/

# Build documentation
mkdocs serve
```

## Architecture Overview

The application follows a modular Python architecture with clear separation of concerns:

1. **Core Browser Engine** (`src/seoltoir/browser_view.py`): WebKit6-based browser implementation that handles all web content rendering and navigation.

2. **Privacy Layer**: Implements privacy features through:
   - Ad blocking via `adblock_parser.py` using python-abp filters
   - HTTPS enforcement through `https_everywhere_rules.py`
   - Isolated browsing contexts in `container_manager.py`

3. **Data Persistence**: SQLite-based storage managed by `database.py` with dedicated managers for:
   - History (`history_manager.py`)
   - Bookmarks (`bookmark_manager.py`)
   - Downloads (`download_manager.py`)

4. **UI Architecture**: GTK4/Libadwaita-based interface where:
   - UI definitions live in `data/ui/*.ui` files (GTK Builder format)
   - Python classes in `src/seoltoir/` bind to these UI files
   - `ui_loader.py` handles loading UI resources
   - Main window (`window.py`) contains the browser view and navigation controls

5. **Configuration System**: 
   - GSettings schema at `data/io.github.tobagin.seoltoir.gschema.xml` defines all application settings
   - Settings are accessed throughout the codebase via GSettings API
   - User preferences UI in `preferences_window.py`

## Key Development Patterns

1. **Adding New Features**: 
   - Update `src/seoltoir/meson.build` to include new Python files
   - For UI changes, modify or create `.ui` files in `data/ui/`
   - For new settings, update the GSettings schema and increment version

2. **UI Development**:
   - Use GTK Builder for UI definitions
   - Follow Libadwaita design patterns
   - Test with both light and dark themes

3. **Privacy Features**:
   - All privacy features should be opt-in by default
   - Implement features to work with WebKit's security policies
   - Consider Flatpak sandboxing constraints

4. **File Organization**:
   - Keep all Python code in `src/seoltoir/`
   - UI files go in `data/ui/`
   - Icons in `data/icons/hicolor/` following freedesktop standards

## Important Constraints

1. **WebKit6 Security**: WebKit enforces strict security policies. File:// URLs and mixed content require special handling.

2. **Flatpak Sandboxing**: When running as Flatpak, filesystem access is limited. The app has home directory access but system paths are restricted.

3. **Python Version**: Minimum Python 3.10 for system builds, but Flatpak uses Python 3.11.

4. **GTK Version**: Requires GTK 4.18+ and Libadwaita 1.7+. Use only stable API, avoid deprecated functions.

## Testing Approach

Currently minimal testing infrastructure. When implementing tests:
- Place tests in `tests/` directory
- Consider GTK's test harness for UI testing
- Mock WebKit for browser functionality tests