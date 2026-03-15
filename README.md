# Linux Mint System Migration Tool

A PyQt6 GUI application to scan, backup, and restore Linux Mint system configurations and applications.

## Features

- **Scan System**: Detects user-installed applications (not system packages)
- **Whitelist Approach**: Only includes known user apps (browsers, IDEs, media apps, etc.)
- **Config Backup**: Backs up ONLY configuration files, never binaries or application data
- **Restore**: Install apps and restore configs on a new system
- **Dry Run Mode**: Preview changes without making them

## Installation

```bash
cd ~/MintSystemMigrator
python3 -m venv venv
source venv/bin/activate
pip install PyQt6
```

## Usage

### Run the GUI

```bash
source venv/bin/activate
python3 src/gui.py
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
5. Click "3️⃣ Restore Selected"

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
├── venv/                      # Python virtual environment
└── README.md
```

## Requirements

- Linux Mint (or Ubuntu-based distro)
- Python 3.8+
- PyQt6

## License

MIT
