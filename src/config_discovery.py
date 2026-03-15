#!/usr/bin/env python3
"""
App Config Discovery - Discovers where apps store their configs
Uses app-specific commands to find actual config file locations
"""

import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class ConfigDiscovery:
    """Discovers config file locations for applications"""

    # Commands to discover configs for specific apps
    DISCOVERY_COMMANDS = {
        "git": [
            ("git config --list --show-origin", r"file:(.+?)\s"),
            ("git config --global --list --show-origin", r"file:(.+?)\s"),
        ],
        "docker": [
            (
                "docker info --format '{{.DockerRootDir}}'",
                None,
            ),  # Just to check if docker is configured
        ],
    }

    # Known config patterns (validated before backup)
    # Format: app_name: [(path_glob, is_file), ...]
    CONFIG_PATTERNS = {
        # Shells
        "bash": [
            ("~/.bashrc", True),
            ("~/.bash_profile", True),
            ("~/.bash_aliases", True),
            ("~/.profile", True),
        ],
        "zsh": [
            ("~/.zshrc", True),
            ("~/.zprofile", True),
            ("~/.zshenv", True),
            ("~/.p10k.zsh", True),  # Powerlevel10k config
        ],
        # Editors
        "vim": [
            ("~/.vimrc", True),
        ],
        "neovim": [
            ("~/.config/nvim/init.vim", True),
            ("~/.config/nvim/init.lua", True),
            ("~/.config/nvim/lua/**", False),  # Lua configs
        ],
        "code": [
            ("~/.config/Code/User/settings.json", True),
            ("~/.config/Code/User/keybindings.json", True),
            ("~/.config/Code/User/snippets/**", False),
            ("~/.vscode/extensions/*/package.json", True),  # Extension list only
        ],
        # Terminals
        "alacritty": [
            ("~/.config/alacritty/alacritty.yml", True),
            ("~/.config/alacritty/alacritty.toml", True),
        ],
        "kitty": [
            ("~/.config/kitty/kitty.conf", True),
            ("~/.config/kitty/*.conf", True),
        ],
        "terminator": [
            ("~/.config/terminator/config", True),
        ],
        # Dev tools
        "git": [
            ("~/.gitconfig", True),
            ("~/.gitignore_global", True),
            ("~/.config/git/ignore", True),
        ],
        "docker": [
            ("~/.docker/config.json", True),
            ("~/.docker/daemon.json", True),
        ],
        "npm": [
            ("~/.npmrc", True),
        ],
        # Browsers - ONLY essential config, not full profiles
        "firefox": [
            ("~/.mozilla/firefox/*/prefs.js", True),
            ("~/.mozilla/firefox/*/user.js", True),
            ("~/.mozilla/firefox/*/extensions.json", True),  # Extension list
        ],
        "chromium": [
            ("~/.config/chromium/*/Preferences", True),
            ("~/.config/chromium/*/Bookmarks", True),
        ],
        "google-chrome": [
            ("~/.config/google-chrome/*/Preferences", True),
            ("~/.config/google-chrome/*/Bookmarks", True),
        ],
        "vivaldi": [
            ("~/.config/vivaldi/*/Preferences", True),
            ("~/.config/vivaldi/*/Bookmarks", True),
        ],
        # Media
        "vlc": [
            ("~/.config/vlc/vlcrc", True),
        ],
        "mpv": [
            ("~/.config/mpv/mpv.conf", True),
            ("~/.config/mpv/input.conf", True),
        ],
        # Communication - only configs
        "thunderbird": [
            ("~/.thunderbird/*/prefs.js", True),
        ],
        "signal": [
            ("~/.config/Signal/config.json", True),
        ],
        # Gaming - ONLY configs, NEVER game files
        "steam": [
            # Steam stores configs in various places but also has huge game libraries
            # We only backup specific config files, not the entire Steam directory
            ("~/.steam/registry.vdf", True),  # Steam settings
            ("~/.local/share/Steam/userdata/*/config/localconfig.vdf", True),
        ],
        "lutris": [
            ("~/.config/lutris/lutris.conf", True),
            ("~/.config/lutris/system.yml", True),
            ("~/.local/share/lutris/pga.db", True),  # Game database
        ],
        # System tools
        "conky": [
            ("~/.conkyrc", True),
            ("~/.config/conky/**", False),
        ],
        "neofetch": [
            ("~/.config/neofetch/config.conf", True),
        ],
    }

    # Global/user configs
    GLOBAL_PATTERNS = [
        ("~/.themes/**", False),
        ("~/.icons/**", False),
        ("~/.fonts/**", False),
        ("~/.fonts.conf", True),
        ("~/.local/share/applications/*.desktop", True),
    ]

    @staticmethod
    def discover_configs(app_name: str) -> List[Tuple[str, bool]]:
        """
        Discover config locations for an app
        Returns list of (path, is_file) tuples
        """
        configs = []

        # First check if we have predefined patterns
        if app_name in ConfigDiscovery.CONFIG_PATTERNS:
            patterns = ConfigDiscovery.CONFIG_PATTERNS[app_name]
            for pattern, is_file in patterns:
                expanded = Path(pattern).expanduser()
                if expanded.exists():
                    if is_file and expanded.is_file():
                        configs.append((str(expanded), True))
                    elif not is_file and expanded.is_dir():
                        # For directories, only include files, not subdirs
                        for item in expanded.rglob("*"):
                            if item.is_file():
                                configs.append((str(item), True))

        # Try to run discovery commands
        if app_name in ConfigDiscovery.DISCOVERY_COMMANDS:
            for cmd, pattern in ConfigDiscovery.DISCOVERY_COMMANDS[app_name]:
                try:
                    result = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0 and result.stdout:
                        # Parse output to find config files
                        if pattern:
                            import re

                            matches = re.findall(pattern, result.stdout)
                            for match in matches:
                                path = Path(match.strip())
                                if path.exists() and path.is_file():
                                    configs.append((str(path), True))
                        else:
                            # Just log that the app is configured
                            pass
                except:
                    pass

        return configs

    @staticmethod
    def get_app_config_summary(app_name: str) -> Dict:
        """Get a summary of configs for an app"""
        configs = ConfigDiscovery.discover_configs(app_name)
        total_size = 0

        for path_str, is_file in configs:
            path = Path(path_str)
            if path.exists():
                try:
                    if path.is_file():
                        total_size += path.stat().st_size
                    # Don't count directory sizes - we only backup files
                except:
                    pass

        return {
            "app": app_name,
            "config_count": len(configs),
            "config_paths": [c[0] for c in configs],
            "total_size_bytes": total_size,
            "total_size_human": ConfigDiscovery._format_size(total_size),
        }

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes to human readable"""
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @classmethod
    def scan_all_apps(cls, app_names: List[str]) -> Dict[str, List[Tuple[str, bool]]]:
        """Scan multiple apps and return their configs"""
        results = {}
        for app_name in app_names:
            configs = cls.discover_configs(app_name)
            if configs:
                results[app_name] = configs
        return results


if __name__ == "__main__":
    # Test discovery
    print("Testing Config Discovery")
    print("=" * 60)

    test_apps = ["git", "bash", "vim", "code"]

    for app in test_apps:
        print(f"\n{app}:")
        summary = ConfigDiscovery.get_app_config_summary(app)
        print(f"  Found {summary['config_count']} config files")
        print(f"  Total size: {summary['total_size_human']}")
        for path in summary["config_paths"][:5]:  # Show first 5
            print(f"    - {path}")
