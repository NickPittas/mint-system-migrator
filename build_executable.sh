#!/bin/bash
# Build single executable file

echo "Building single executable for Linux Mint System Migration Tool..."

# Check if we're in the virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Install pyinstaller if not present
pip install pyinstaller

# Clean previous builds
rm -rf build dist

echo "Building executable..."

# Build the executable
pyinstaller \
    --onefile \
    --name mint-migrator \
    --windowed \
    --add-data "src:src" \
    --hidden-import PyQt6 \
    --hidden-import PyQt6.QtCore \
    --hidden-import PyQt6.QtGui \
    --hidden-import PyQt6.QtWidgets \
    src/gui.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Build successful!"
    echo ""
    echo "Executable created: dist/mint-migrator"
    echo ""
    echo "To run:"
    echo "  ./dist/mint-migrator"
    echo ""
    echo "Or copy to /usr/local/bin:"
    echo "  sudo cp dist/mint-migrator /usr/local/bin/"
    echo "  sudo chmod +x /usr/local/bin/mint-migrator"
    echo ""
    echo "Then run from anywhere:"
    echo "  mint-migrator"
else
    echo "✗ Build failed"
    exit 1
fi
