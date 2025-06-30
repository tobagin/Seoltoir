# Getting Started with Seoltóir

This guide will help you install Seoltóir and begin your privacy-focused browsing journey.

## Installation

### A. Using Flatpak (Recommended)

The easiest way to install and run Seoltóir is via Flatpak, which provides a sandboxed environment for enhanced security and cross-distribution compatibility.

1.  **Ensure Flatpak is installed on your system.** If not, follow the setup guide for your Linux distribution: [https://flatpak.org/setup/](https://flatpak.org/setup/)

2.  **Add the Flathub repository (if you haven't already):**
    ```bash
    flatpak remote-add --if-not-exists flathub [https://flathub.org/repo/flathub.flatpakrepo](https://flathub.org/repo/flathub.flatpakrepo)
    ```

3.  **Install Seoltóir:**
    *(Currently, Seoltóir is not on Flathub. You will build and install it locally.)*

    **To build and install from source (for local Flatpak development):**

    a.  **Clone the repository:**
        ```bash
        git clone [https://github.com/tobagin/seoltoir.git](https://github.com/tobagin/seoltoir.git) # Replace with actual repo URL if different
        cd seoltoir
        ```
    b.  **Build the Flatpak:**
        ```bash
        flatpak-builder --force-clean build-dir io.github.tobagin.seoltoir.yaml
        ```
        This command will download all necessary dependencies and build the Flatpak application. This might take some time on the first run.

    c.  **Install the built Flatpak to your local user repository:**
        ```bash
        flatpak-builder --user --install build-dir io.github.tobagin.seoltoir.yaml
        ```

4.  **Run Seoltóir:**
    ```bash
    flatpak run io.github.tobagin.seoltoir
    ```
    You should now see Seoltóir appear in your application launcher.

### B. Building from Source

If you prefer to run Seoltóir directly from source (without Flatpak), follow these steps:

1.  **Prerequisites:**
    Make sure you have the following installed on your system:
    * Python 3.10+
    * GTK 4 development libraries (e.g., `libgtk-4-dev` on Debian/Ubuntu, `gtk4-devel` on Fedora)
    * Libadwaita development libraries (e.g., `libadwaita-1-dev` on Debian/Ubuntu, `libadwaita-devel` on Fedora)
    * WebKitGTK 6.0 development libraries (e.g., `libwebkitgtk-6.0-dev` on Debian/Ubuntu, `webkitgtk6.0-devel` on Fedora)
    * Meson build system (`pip install meson`)
    * Ninja build system (`pip install ninja`)
    * Python libraries: `requests`, `python-abp` (`pip install requests python-abp`)

2.  **Clone the repository:**
    ```bash
    git clone [https://github.com/tobagin/seoltoir.git](https://github.com/tobagin/seoltoir.git) # Replace with actual repo URL if different
    cd seoltoir
    ```

3.  **Install Python dependencies:**
    ```bash
    pip install requests python-abp
    ```

4.  **Configure the Meson build:**
    ```bash
    meson setup build --prefix=/usr
    ```

5.  **Compile the project:**
    ```bash
    meson compile -C build
    ```

6.  **Install GSettings schema (important for settings to appear):**
    ```bash
    sudo meson install -C build
    glib-compile-schemas ~/.local/share/glib-2.0/schemas/ # If installed to user local
    # If you installed with a different prefix, adjust the path accordingly.
    ```

7.  **Run the application:**
    ```bash
    meson run -C build seoltoir
    ```

## First Steps

Once Seoltóir launches, you'll see a clean browser window.

* **Address Bar:** Type a URL or a search query here.
* **New Tab:** Click the `+` button in the tab bar to open a new tab.
* **Navigation:** Use the back, forward, and reload buttons.
* **Menu:** Click the "hamburger" menu icon (`≡`) in the header bar to access settings, history, bookmarks, and other features.

Explore the [Privacy Features](privacy-features.md) and [Customization](customization.md) sections to learn how to tailor Seoltóir to your needs.

