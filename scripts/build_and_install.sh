#!/bin/bash

# Script to build and install Seoltóir browser

# --- Configuration ---
# Use BASH_SOURCE to get the script's own directory, robust across shells
PROJECT_ROOT="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
BUILD_DIR="$PROJECT_ROOT/build"
INSTALL_PREFIX="/usr" # Or "~/.local" if you prefer user-local install
GSCHEMAS_DIR="$INSTALL_PREFIX/share/glib-2.0/schemas" # Adjust if INSTALL_PREFIX is ~/.local
APP_ID="io.github.tobagin.Seoltoir"

# --- Functions ---
log_info() {
    echo -e "\n\033[1;34mINFO:\033[0m $1"
}

log_success() {
    echo -e "\n\033[1;32mSUCCESS:\033[0m $1"
}

log_error() {
    echo -e "\n\033[1;31mERROR:\033[0m $1"
    exit 1 # Exit the subshell, which will exit the main script
}

# --- Main Script ---
log_info "Starting Seoltóir build and install process..."

# 1. Navigate to project root
if [ ! -d "$PROJECT_ROOT" ]; then
    log_error "Project root directory not found: $PROJECT_ROOT"
fi
cd "$PROJECT_ROOT" || log_error "Failed to change to project directory."

# 3. Clean build directory
log_info "Cleaning old build directory..."
rm -rf "$BUILD_DIR"
log_success "Build directory cleaned."

# 4. Meson Setup
log_info "Running Meson setup..."
meson setup "$BUILD_DIR" . --prefix="$INSTALL_PREFIX" || log_error "Meson setup failed."
log_success "Meson setup completed."

# 5. Meson Compile
log_info "Running Meson compile..."
meson compile -C "$BUILD_DIR" || log_error "Meson compile failed."
log_success "Meson compile completed."

# 6. Meson Install
log_info "Running Meson install (requires sudo for /usr/)..."
if [ "$INSTALL_PREFIX" = "/usr" ]; then
    sudo meson install -C "$BUILD_DIR" || log_error "Meson install failed."
else
    meson install -C "$BUILD_DIR" || log_error "Meson install failed."
fi
log_success "Meson install completed."

# 7. Compile GSettings Schemas
log_info "Compiling GSettings schemas..."
# Determine the correct GSchemas directory for compilation
if [ "$INSTALL_PREFIX" = "/usr" ]; then
    # For /usr install, use the system-wide schemas directory
    sudo glib-compile-schemas "$GSCHEMAS_DIR" || log_error "GSettings schema compilation failed."
else
    # For user-local install, use the user's schemas directory
    glib-compile-schemas "$HOME/.local/share/glib-2.0/schemas" || log_error "GSettings schema compilation failed."
fi
log_success "GSettings schemas compiled."

sudo chmod +x "$INSTALL_PREFIX/bin/seoltoir" || log_error "Failed to make Seoltóir executable."

log_info "Build and installation process finished successfully!"
log_info "You can now run Seoltóir from your application launcher or by typing 'seoltoir'."