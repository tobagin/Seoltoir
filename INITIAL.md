This document outlines the initial vision for the project. Some features described below may already be partially or fully implemented. Before starting any new work, please thoroughly review the current codebase in the repository to understand the existing architecture and identify which tasks have been completed. The goal is to build upon the current implementation, not to start from scratch.

## FEATURE:

The goal is to create a modern, privacy-first web browser for the GNOME desktop environment. The browser will prioritize user privacy and security by default, while offering a clean and intuitive user interface that conforms to the latest GNOME Human Interface Guidelines.
1. Core Browsing & Functionality
    - WebKit-based Rendering: Utilize the WebKitGTK engine for fast, accurate, and secure rendering of modern web standards (HTML5, CSS3, JavaScript/ESNext).
    - Tab Management:
        - Create, close, and switch between tabs.
        - Reorder tabs via drag-and-drop.
        - Pin tabs for frequently used sites.
        - Mute/unmute audio on a per-tab basis.
        - Visual indicators for loading, playing audio, etc.
        - Tab grouping/organization.
    - Navigation:
        - Back, forward, reload, and home buttons.
        - Stop loading button.
    - Address Bar (Omnibox):
        - Enter URLs and search queries.
        - Provide search suggestions from the default search engine.
        - Display security status (e.g., padlock for HTTPS).
        - Autocomplete from history and bookmarks.
    - History:
        - Record visited pages.
        - Searchable history view.
        - Clear history for specific time ranges or all time.
    - Bookmarks:
        - Save, edit, and delete bookmarks.
        - Organize bookmarks into folders.
        - Bookmark manager interface.
        - Import/export bookmarks from/to HTML.
    - Downloads:
        - Download files from the web.
        - Downloads manager to view, pause, resume, cancel, and open - downloaded files.
    - Search Engine Management:
        - Set a default search engine.
        - Allow users to add, edit, and remove search engines.
    - Session Management:
        - Restore previous session (tabs and windows) on startup.
        - Save and restore browsing sessions on demand.
2. User Interface & Experience (GTK4 & Libadwaita)
    - Adaptive UI: Fully responsive design that works on various screen sizes and orientations, adhering to GNOME HIG.
    - Preferences/Settings Window: A comprehensive, well-organized window to manage all browser settings.
    - Find in Page: Search for text within the current web page.
    - Full-Screen Mode: View web content without browser chrome.
    - Zoom Control: Zoom in and out of web pages, remembering per-site zoom levels.
    - Reader Mode: A clutter-free view for articles, stripping away ads, navigation, and other distractions.
    - Context Menus: Right-click menus for links, images, and the page itself (e.g., "Open in New Tab," "Save Image As...").
    - Picture-in-Picture (PiP): Pop out videos from a web page into a floating, resizable window.
    - Desktop Notifications: Support for the Web Notifications API to display notifications from websites.
    - Printing:
        - Print web pages.
        - Print preview and page setup options.
        - Save to PDF.
3. Privacy & Security (Core Tenets)
    - Private Browsing Mode: A mode that leaves no local traces (history, cookies, cache) after the session is closed.
    - Ad & Tracker Blocking:
        - Built-in, enabled-by-default content blocker using filter lists (e.g., EasyList, EasyPrivacy).
        - Allow users to manage filter lists and whitelist sites.
    - Advanced Cookie Management:
        - Block third-party cookies by default.
        - Option to automatically delete all cookies on exit.
        - Per-site cookie settings.
    - Permissions Management:
        - Granular, per-site control over permissions for location, camera, microphone, notifications, etc.
        - Clear and understandable permission prompts.
    - HTTPS Upgrading: Automatically upgrade navigations to HTTPS where available (HTTPS-First mode).
    - Sandboxing: Leverage WebKitGTK's process sandboxing to isolate web content from the system.
    - "Do Not Track" by Default: Send a "Do Not Track" request with all web traffic.
    - JavaScript Control: Allow users to disable JavaScript globally or on a per-site basis.
    - Phishing and Malware Protection: Integrate with a safe browsing service (like Google Safe Browsing) to block malicious websites.
    - Credential Management:
        - Securely save and autofill passwords.
        - Integration with system keyrings (e.g., GNOME Keyring/libsecret).
        - Built-in password generator.
4. Performance & Technology
    - Hardware Acceleration: Utilize GPU acceleration for rendering and video playback to improve performance and battery life.
    - Efficient Resource Management: Proactively manage memory and CPU usage, especially for background tabs, to keep the browser fast and responsive.
    - Modern Web Standards Support: Keep WebKitGTK updated to ensure compatibility with the latest web technologies (WebRTC, WebGL, WebAssembly, etc.).
    - Network & Caching:
        - Advanced network caching to reduce load times.
        - Support for modern network protocols (HTTP/3, QUIC).
5. Content & Media Handling
    - PDF Viewer: Built-in PDF viewer to open and read PDF files directly in the browser.
    - Media Codec Support: Support for common open audio and video formats (e.g., AV1, Opus, VP9).
    - DRM Support (Optional but necessary for many services):
        Support for Encrypted Media Extensions (EME) to play protected content (e.g., Netflix, Spotify). This is a complex and potentially controversial feature for a privacy-focused browser.
6. Productivity & Integration
    - Extensions/Add-ons:
        - A framework for browser extensions to add new features.
        - Compatibility with a standard extension API (e.g., WebExtensions).
        - An add-on manager to install, disable, and remove extensions.
    - Sync:
        - Securely sync bookmarks, history, passwords, and settings across devices.
        - Requires a backend server and user account system, with a strong focus on end-to-end encryption.
    - Developer Tools:
        - A comprehensive suite of tools for web developers, accessible via the WebKitGTK Web Inspector.
        - Elements inspector, JavaScript console, network monitor, storage inspector, performance profiler, etc.

## EXAMPLES:

The following examples can serve as a starting point for development. It is recommended to create an examples/ directory in your project and download the relevant files.

Python GTK4 and Libadwaita Boilerplate:
- File: main.py
- Link: https://raw.githubusercontent.com/Taiko2k/GTK4PythonTutorial/main/main.py
- Usage: This file provides a basic template for a GTK4 application using Libadwaita. It demonstrates how to set up the main application window and is a good starting point for building the browser's UI.

Simple WebKitGTK Browser in Python:
- File: browser.py
- Link: https://gist.github.com/jhenrique/8713193
- Usage: This is a very basic example of a web browser using Python and an older version of WebKitGTK. While not directly using GTK4, it illustrates the fundamental concepts of embedding a WebView and handling basic browser actions. This will need to be adapted to the GTK4 and PyGObject APIs.

Libadwaita Widgets Showcase:
- Repository: https://github.com/Taiko2k/GTK4PythonTutorial
- Usage: This repository contains numerous examples of how to use various Libadwaita widgets in Python. It's an excellent resource for learning how to build a modern and compliant GNOME application interface.

## DOCUMENTATION:

Familiarity with the following documentation is essential for this project:

- Python: https://docs.python.org/3/
- PyGObject (Python Bindings for GObject): https://pygobject.gnome.org/
- PyGObject API docs: https://api.pygobject.gnome.org/
- GTK4: https://docs.gtk.org/gtk4/
- Libadwaita: https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1.7/
- WebKitGTK: https://webkitgtk.org/
- WebKitGTK for GTK4 API Reference: https://webkitgtk.org/reference/webkitgtk/stable/
- GNOME Human Interface Guidelines (HIG): https://developer.gnome.org/hig/

## OTHER CONSIDERATIONS:

- WebKitGTK API Version: It is crucial to use the webkitgtk-6.0 API for compatibility with GTK4. This might require specific build flags or ensuring your development environment has the correct version installed.
- PyGObject Introspection: Python bindings for GTK, Libadwaita, and WebKitGTK are generated dynamically using GObject Introspection. This means that the C API documentation is often the primary source of information, and you'll need to translate C examples and concepts to their Python equivalents (e.g., gtk_widget_show() becomes widget.show()).
- Performance: While Python is excellent for rapid development, care must be taken to ensure the browser remains responsive. Intensive operations should be handled efficiently, possibly in separate threads if necessary, to avoid blocking the UI.

Security Best Practices:
- Always be mindful of the potential for security vulnerabilities when processing web content.
- Keep all dependencies (WebKitGTK, GTK4, Libadwaita) up-to-date to benefit from the latest security patches.
- Thoroughly validate and sanitize any data coming from web content before using it in the browser's UI or other privileged contexts.
- Modern Python Practices: Utilize modern Python features such as type hints and asynchronous programming (asyncio) where appropriate to improve code quality and maintainability.
