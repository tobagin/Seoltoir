Seoltóir Browser

Seoltóir (Irish for "Navigator" or "Sailor") is a privacy-focused web browser built with Python, GTK4, Libadwaita, and WebKit6. Our mission is to provide a fast, secure, and user-controlled browsing experience, completely free from telemetry, invasive ads, and hidden trackers.
✨ Features

Seoltóir has evolved significantly through multiple development tiers to offer a robust and privacy-respeciting browsing experience:
🛡️ Privacy & Security First

    Zero Telemetry & Data Collection: Absolutely no usage statistics, crash reports, or personal data are sent to any third party or to the browser developers. All data is stored locally.

    Advanced Ad & Tracker Blocking: Utilizes a custom parser for Adblock Plus-compatible filter lists (like EasyList and EasyPrivacy) to block ads, tracking scripts, and malicious domains. Supports online updates of filter lists.

    Enhanced Fingerprinting Resistance:

        User-Agent Spoofing: Configurable generic User-Agent strings.

        Canvas Fingerprinting Defense: Injects noise into canvas rendering to make unique fingerprinting harder.

        Font Enumeration Spoofing: Spoofs the list of fonts reported to websites.

        Hardware Concurrency Spoofing: Spoofs reported CPU core count and device memory.

        WebRTC Control: Option to disable WebRTC to prevent IP leaks.

        Referrer Policy Control: Configurable referrer header policy to limit information leakage.

        Granular Toggles: Independent controls in settings to enable/disable specific fingerprinting resistance measures.

    Comprehensive Cookie Management:

        Default to blocking third-party cookies.

        "Delete non-bookmarked cookies on close" option to automatically clear data from sites you don't explicitly trust.

        Per-site settings to view and delete cookies and other site storage (Local Storage, IndexedDB, WebSQL).

    Encrypted DNS (DoH/DoT): Supports both DNS over HTTPS (DoH) and DNS over TLS (DoT) with configurable providers for encrypted DNS queries, protecting your browsing from DNS-based snooping.

    HTTPS Everywhere: Automatically upgrades insecure HTTP connections to HTTPS based on HSTS and a rule-based enforcement mechanism for broader coverage.

    JavaScript Control: Global toggle to enable/disable JavaScript, with per-site exceptions for fine-grained control.

    Content Isolation (Containers - Initial Phase): Introduces "Container Tabs" where each container operates with a completely isolated browsing context (separate cookies, cache, local storage), preventing cross-site tracking between different containerized activities.

🌐 Core Browsing & Usability

    Tabbed Browsing: Standard tabbed interface with basic management (new, close, switch).

    Session Restore: Remembers and restores all open tabs from your last browsing session.

    Navigation: Intuitive back, forward, refresh, and home buttons with dynamic sensitivity.

    Address Bar: Integrated address bar with search functionality using configurable search engines.

    Download Manager: Basic UI to monitor download progress, open downloaded files, or open their containing folders.

    Find-in-Page: Quickly search for text within the current webpage.

    Print Functionality: Print the current webpage using system print dialogs.
    
    Zoom Controls: Zoom in/out/reset functionality with visual indicator and keyboard shortcuts (Ctrl+Plus, Ctrl+Minus, Ctrl+0).

⚙️ Customization & Management

    Preferences Window: A comprehensive Libadwaita-designed settings dialog for all privacy, security, and general configurations.

    Per-Site Settings Dialog: A dedicated dialog to manage JavaScript policy and site data for the currently viewed website.

    History Management: View and clear your local browsing history.

    Bookmark Management: Add, view, and remove local bookmarks.

    Search Engine Management: Full UI in preferences to add, edit, delete, and set default custom search engines with OpenSearch support and real-time search suggestions.

    Appearance Customization: Control default font family and size for web content, and override system theme with light/dark mode.

    Data Import/Export: Export and import your bookmarks, history, and browser settings (to/from JSON/CSV/HTML formats).

    In-App Notifications: Subtle toast notifications for privacy events like blocked ads/trackers.

📸 Screenshots

Here are some glimpses of Seoltóir in action:

Main Browsing Window

A clean and modern interface for everyday browsing.

Preferences Window

Take control of your privacy with extensive configuration options.

Site Settings Dialog

Manage JavaScript and site data for individual websites.

Downloads Manager

Track your downloads and access your files easily.
🛠️ Build & Run

Seoltóir is built with the Meson build system and designed for Flatpak distribution.
Prerequisites

    Python 3.10+

    GTK 4 development libraries

    Libadwaita development libraries

    WebKitGTK 6.0 development libraries

    Meson build system

    Ninja build system

    python-abp library (install via pip install python-abp)

    requests library (install via pip install requests)

Building from Source

    Clone the repository:

    git clone https://github.com/tobagin/seoltoir.git # (Assuming this is your repo URL)
    cd seoltoir

    Install Python dependencies:

    pip install requests python-abp

    (Note: For Flatpak builds, these dependencies will be handled by the Flatpak manifest.)

    Configure the Meson build:

    meson setup build --prefix=/usr

    Compile the project:

    meson compile -C build

    Install GSettings schema (important for settings to appear):

    sudo meson install -C build
    glib-compile-schemas ~/.local/share/glib-2.0/schemas/ # Or the system path if installed globally

    Run the application:

    meson run -C build seoltoir

Flatpak Distribution

Seoltóir is packaged as a Flatpak for easy distribution and sandboxing.

    Build the Flatpak:

    flatpak-builder --force-clean build-dir packaging/io.github.tobagin.seoltoir-local.yml

    Install the Flatpak to your local user repository:

    flatpak-builder --user --install build-dir packaging/io.github.tobagin.seoltoir-local.yml

    Run the Flatpak application:

    flatpak run io.github.tobagin.seoltoir

🤝 Contributing

We welcome contributions! If you'd like to improve Seoltóir, please:

    Fork the repository.

    Create a new branch for your features or bug fixes.

    Submit a pull request.

📜 License

Seoltóir is licensed under the GNU General Public License v3.0 or later. See the LICENSE file for more details.

## Flatpak Manifest Naming

Flatpak manifests now use the `.yml` extension (not `.yaml`) for consistency and clarity. Please use `packaging/io.github.tobagin.seoltoir-local.yml` for local builds and `packaging/io.github.tobagin.seoltoir.yml` for release builds.

## App ID and Icon Naming

The application ID and all icon/file references have been standardized to lowercase: `io.github.tobagin.seoltoir`. All files and references previously using `Seoltoir` have been renamed to `seoltoir` for consistency.

## Meson for Flatpak

Flatpak manifests are configured to use Meson as the build system. The app and all icons are installed via Meson, ensuring correct installation paths and integration.

## Summary of Recent Changes

- All app icon sizes (1024x1024, 512x512, 256x256, 64x64, 48x48, 32x32, 24x24, 16x16) are now generated and installed.
- The app ID and all file references are now lowercase (`io.github.tobagin.seoltoir`).
- Flatpak manifests use `.yml` extension and GNOME runtime 48.
- Meson build updated to install all icon sizes.
- All relevant files and manifests updated for new app ID and icon naming.
- Documentation updated to reflect these changes.