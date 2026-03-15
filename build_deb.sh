#!/bin/bash
# Build .deb package

echo "Building .deb package for Mint System Migrator..."

# Make scripts executable
chmod +x deb/DEBIAN/postinst
chmod +x deb/usr/bin/mint-migrator

# Copy source files to package
rm -rf deb/usr/share/mint-migrator/src
cp -r src deb/usr/share/mint-migrator/
cp README.md deb/usr/share/mint-migrator/

# Calculate installed size
INSTALLED_SIZE=$(du -sk deb/usr | cut -f1)

# Update control file with size
sed -i "s/Installed-Size:.*/Installed-Size: $INSTALLED_SIZE/" deb/DEBIAN/control 2>/dev/null || echo "Installed-Size: $INSTALLED_SIZE" >> deb/DEBIAN/control

# Get version from control file
VERSION=$(grep "^Version:" deb/DEBIAN/control | cut -d' ' -f2)
OUTPUT_FILE="mint-system-migrator_${VERSION}_all.deb"

# Remove old packages
rm -f mint-system-migrator_*.deb

# Build the package
cd deb
dpkg-deb --build . "../$OUTPUT_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Package built successfully!"
    echo ""
    echo "File: $OUTPUT_FILE"
    echo ""
    echo "To install:"
    echo "  sudo dpkg -i $OUTPUT_FILE"
    echo ""
    echo "To upgrade (no need to remove first):"
    echo "  sudo dpkg -i $OUTPUT_FILE"
    echo ""
    echo "To uninstall:"
    echo "  sudo apt remove mint-system-migrator"
    echo ""
    echo "The app will appear in your applications menu!"
else
    echo "✗ Package build failed"
    exit 1
fi
