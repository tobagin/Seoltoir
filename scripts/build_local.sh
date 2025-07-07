#!/bin/bash

# Script to build and install Seoltóir browser using local Flatpak manifest
# This script uses the -local.yml manifest for development builds

echo "Building Seoltóir (Local Development Build)..."
echo "==========================================="

# Check if we're in the right directory
if [ ! -f "packaging/io.github.tobagin.seoltoir-local.yml" ]; then
    echo "Error: Must run from project root directory"
    echo "Could not find packaging/io.github.tobagin.seoltoir-local.yml"
    exit 1
fi

# Build and install with Flatpak
echo "Starting Flatpak build and install..."
flatpak-builder --user --install --force-clean build-dir packaging/io.github.tobagin.seoltoir-local.yml

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Build completed successfully!"
    echo "You can now run the application with:"
    echo "   flatpak run io.github.tobagin.seoltoir"
else
    echo ""
    echo "❌ Build failed!"
    exit 1
fi