# Linux Mint System Migration Tool

A PyQt6 GUI application to scan, backup, and restore Linux Mint system configurations and applications.

## Features

- **Scan System**: Detects user-installed applications (not system packages)
- **Whitelist Approach**: Only includes known user apps (browsers, IDEs, media apps, etc.)
- **Config Backup**: Backs up ONLY configuration files, never binaries or application data
- **Restore**: Install apps and restore configs on a new system
- **Dry Run Mode**: Preview changes without making them

## Installation

### Option 1: Install .deb Package (Recommended)

```bash
# Download the .deb from releases
cd ~/Downloads
sudo apt install ./mint-system-migrator_1.0.5_all.deb

# Or install from GitHub release
wget https://github.com/NickPittas/mint-system-migrator/releases/download/v1.0.5/mint-system-migrator_1.0.5_all.deb
sudo apt install ./mint-system-migrator_1.0.5_all.deb
```

The app will appear in your applications menu under **System Tools**.

### Option 2: Run from Source

```bash
cd ~/MintSystemMigrator
python3 -m venv venv
source venv/bin/activate
pip install PyQt6
python3 src/gui.py
```

### Option 3: Single Executable

```bash
# Build it yourself
cd ~/MintSystemMigrator
chmod +x build_executable.sh
./build_executable.sh

# Copy to system
cp dist/mint-migrator /usr/local/bin/
chmod +x /usr/local/bin/mint-migrator

# Run from anywhere
mint-migrator
```

## Usage

### Run the GUI

```bash
# If installed via .deb
mint-migrator

# Or find it in your applications menu
```

### Backup Mode

1. Click "📦 Backup Mode"
2. Click "1️⃣ Scan System" to detect your apps
3. Select applications to backup
4. Check "Include config files" (recommended)
5. Click "3️⃣ Create Package"
6. Save the JSON package + config archive

### Restore Mode

1. Click "🔄 Restore Mode"
2. Click "1️⃣ Load Package" to select your migration JSON
3. Select apps to restore
4. (Optional) Check "Dry run" to preview
5. (Optional) Check "Safe staged restore to folder" to restore into a preview folder instead of your real home
6. Click "3️⃣ Restore Selected"

## What Gets Backed Up

**Config files only:**
- Shell configs (.bashrc, .zshrc)
- Editor configs (VS Code settings, vimrc)
- Git config
- Browser preferences
- Themes and fonts

**Never backed up:**
- Binaries or executables
- Steam games
- Cargo/rust binaries
- Application data
- Large files (>50MB)

## Project Structure

```
MintSystemMigrator/
├── src/
│   ├── gui.py                 # PyQt6 GUI
│   ├── scanner_whitelist.py   # App scanner
│   ├── config_discovery.py    # Config file discovery
│   ├── config_backup.py       # Config backup (files only)
│   └── restore.py             # Restore functionality
├── build_deb.sh               # Build .deb package
├── build_executable.sh        # Build single executable
├── deb/                       # Debian package files
├── venv/                      # Python virtual environment
└── README.md
```

## Building from Source

### Build .deb Package

```bash
cd ~/MintSystemMigrator
./build_deb.sh
# Creates: mint-system-migrator_1.0.0_all.deb
```

### Build Single Executable

```bash
cd ~/MintSystemMigrator
./build_executable.sh
# Creates: dist/mint-migrator (single file)
```

## Requirements

- Linux Mint (or Ubuntu-based distro)
- Python 3.8+
- PyQt6

## Uninstall

```bash
sudo apt remove mint-system-migrator
```

## License

MIT
