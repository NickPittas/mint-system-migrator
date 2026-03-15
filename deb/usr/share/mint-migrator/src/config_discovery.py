#!/usr/bin/env python3
"""
Smart Config Discovery - Discovers ONLY config files, never application data
Scans specific locations known to contain configs
"""

import os
import subprocess
from pathlib import Path
from typing import List, Dict, Set, Tuple
import fnmatch


class SmartConfigDiscovery:
    """Discovers config files intelligently, avoiding data directories"""

    def __init__(self):
        self.home = Path.home()
        self.xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", self.home / ".config"))
        self.xdg_data = Path(
            os.environ.get("XDG_DATA_HOME", self.home / ".local" / "share")
        )

    def discover_configs(self, app_name: str) -> List[Tuple[str, int]]:
        """
        Discover config files for an application
        Returns list of (path, size_bytes) - ONLY actual config files
        """
        configs = []
        found_paths: Set[str] = set()

        app_lower = app_name.lower()

        # Strategy 1: Check home directory dotfiles
        configs.extend(self._scan_dotfiles(app_lower, found_paths))

        # Strategy 2: Check ~/.config/
        configs.extend(self._scan_config_dir(app_lower, found_paths))

        # Strategy 3: Check ~/.local/share/ for specific config files
        configs.extend(self._scan_local_share(app_lower, found_paths))

        # Strategy 4: App-specific logic
        configs.extend(self._app_specific_scan(app_lower, found_paths))

        return configs

    def _scan_dotfiles(
        self, app_name: str, found_paths: Set[str]
    ) -> List[Tuple[str, int]]:
        """Scan home directory for dotfiles - ONLY specific patterns, not recursive"""
        configs = []

        # Specific dotfile patterns to check
        dotfile_patterns = [
            f".{app_name}rc",
            f".{app_name}.conf",
            f".{app_name}.config",
            f".{app_name}.toml",
            f".{app_name}.yaml",
            f".{app_name}.yml",
            f".{app_name}.json",
            f".{app_name}.ini",
            f".{app_name}",
        ]

        # Also check common variations
        if app_name == "zsh":
            dotfile_patterns.extend(
                [".zshrc", ".zprofile", ".zshenv", ".zlogin", ".zlogout", ".p10k.zsh"]
            )
        elif app_name == "bash":
            dotfile_patterns.extend(
                [
                    ".bashrc",
                    ".bash_profile",
                    ".bash_aliases",
                    ".profile",
                    ".bash_logout",
                ]
            )
        elif app_name == "vim":
            dotfile_patterns.extend([".vimrc", ".viminfo"])
        elif app_name == "git":
            dotfile_patterns.extend([".gitconfig", ".gitignore_global"])
        elif app_name == "ssh":
            dotfile_patterns.extend([".ssh/config"])
        elif app_name == "fzf":
            dotfile_patterns.extend([".fzf.bash", ".fzf.zsh"])
        elif app_name == "zoxide":
            dotfile_patterns.extend([".zoxide.toml"])
        elif app_name == "cargo":
            dotfile_patterns.extend([".cargo/config", ".cargo/config.toml"])
        elif app_name == "rustup":
            dotfile_patterns.extend([".rustup/settings.toml"])

        for pattern in dotfile_patterns:
            path = self.home / pattern
            if path.exists() and path.is_file():
                path_str = str(path)
                if path_str not in found_paths:
                    size = path.stat().st_size
                    if size < 10 * 1024 * 1024:  # Skip if > 10MB
                        configs.append((path_str, size))
                        found_paths.add(path_str)

        return configs

    def _scan_config_dir(
        self, app_name: str, found_paths: Set[str]
    ) -> List[Tuple[str, int]]:
        """Scan ~/.config/ for app configs - specific files only"""
        configs = []

        if not self.xdg_config.exists():
            return configs

        # Look for app directory in ~/.config/
        app_dir = self.xdg_config / app_name

        # Also check capitalized version
        app_dir_cap = self.xdg_config / app_name.capitalize()

        for directory in [app_dir, app_dir_cap]:
            if directory.exists() and directory.is_dir():
                # Only look for specific config files, NOT recursively
                config_files = [
                    "config",
                    "config.toml",
                    "config.yaml",
                    "config.yml",
                    "config.json",
                    "settings.json",
                    "settings.toml",
                    "settings.yaml",
                    "init.lua",
                    "init.vim",
                    "init.el",
                    "kitty.conf",
                    "alacritty.yml",
                    "alacritty.toml",
                ]

                for config_name in config_files:
                    config_path = directory / config_name
                    if config_path.exists() and config_path.is_file():
                        path_str = str(config_path)
                        if path_str not in found_paths:
                            size = config_path.stat().st_size
                            if size < 10 * 1024 * 1024:
                                configs.append((path_str, size))
                                found_paths.add(path_str)

                # For some apps, also check subdirectories but limit depth
                if app_name in [
                    "nvim",
                    "neovim",
                    "vim",
                    "kitty",
                    "alacritty",
                    "code",
                    "vscode",
                ]:
                    for subitem in directory.iterdir():
                        if subitem.is_file() and subitem.suffix in [
                            ".lua",
                            ".vim",
                            ".json",
                            ".toml",
                            ".yml",
                            ".yaml",
                            ".conf",
                        ]:
                            path_str = str(subitem)
                            if path_str not in found_paths:
                                size = subitem.stat().st_size
                                if size < 10 * 1024 * 1024:
                                    configs.append((path_str, size))
                                    found_paths.add(path_str)
                        elif subitem.is_dir() and subitem.name.lower() in [
                            "lua",
                            "plugin",
                            "colors",
                            "syntax",
                            "ftplugin",
                            "snippets",
                        ]:
                            # One level deep only for specific directories
                            for subfile in subitem.iterdir():
                                if subfile.is_file():
                                    path_str = str(subfile)
                                    if path_str not in found_paths:
                                        size = subfile.stat().st_size
                                        if size < 10 * 1024 * 1024:
                                            configs.append((path_str, size))
                                            found_paths.add(path_str)

        return configs

    def _scan_local_share(
        self, app_name: str, found_paths: Set[str]
    ) -> List[Tuple[str, int]]:
        """Scan ~/.local/share/ for specific config files"""
        configs = []

        if not self.xdg_data.exists():
            return configs

        app_dir = self.xdg_data / app_name

        if app_dir.exists() and app_dir.is_dir():
            # Only look for specific config files, not the whole directory
            config_names = ["settings.json", "config.json", "prefs.js", "settings.toml"]

            for config_name in config_names:
                config_path = app_dir / config_name
                if config_path.exists() and config_path.is_file():
                    path_str = str(config_path)
                    if path_str not in found_paths:
                        size = config_path.stat().st_size
                        if size < 10 * 1024 * 1024:
                            configs.append((path_str, size))
                            found_paths.add(path_str)

        return configs

    def _app_specific_scan(
        self, app_name: str, found_paths: Set[str]
    ) -> List[Tuple[str, int]]:
        """App-specific config locations"""
        configs = []

        # Define app-specific config paths
        app_configs = {
            "zsh": [
                self.home / ".zshrc",
                self.home / ".zprofile",
                self.home / ".zshenv",
                self.home / ".zlogin",
                self.home / ".zlogout",
                self.home / ".p10k.zsh",
                self.home / ".oh-my-zsh" / "custom" / "custom.zsh",
            ],
            "bash": [
                self.home / ".bashrc",
                self.home / ".bash_profile",
                self.home / ".bash_aliases",
                self.home / ".profile",
                self.home / ".bash_logout",
            ],
            "kitty": [
                self.xdg_config / "kitty" / "kitty.conf",
                self.xdg_config / "kitty" / "current-theme.conf",
            ],
            "alacritty": [
                self.xdg_config / "alacritty" / "alacritty.yml",
                self.xdg_config / "alacritty" / "alacritty.toml",
            ],
            "fzf": [
                self.home / ".fzf.bash",
                self.home / ".fzf.zsh",
            ],
            "zoxide": [
                self.home / ".zoxide.toml",
            ],
            "nvim": [
                self.xdg_config / "nvim" / "init.lua",
                self.xdg_config / "nvim" / "init.vim",
            ],
            "neovim": [
                self.xdg_config / "nvim" / "init.lua",
                self.xdg_config / "nvim" / "init.vim",
            ],
            "vim": [
                self.home / ".vimrc",
                self.home / ".viminfo",
            ],
            "git": [
                self.home / ".gitconfig",
                self.home / ".gitignore_global",
            ],
            "ssh": [
                self.home / ".ssh" / "config",
            ],
            "cargo": [
                self.home / ".cargo" / "config",
                self.home / ".cargo" / "config.toml",
            ],
            "rustup": [
                self.home / ".rustup" / "settings.toml",
            ],
            "docker": [
                self.home / ".docker" / "config.json",
            ],
            "npm": [
                self.home / ".npmrc",
            ],
            "code": [
                self.xdg_config / "Code" / "User" / "settings.json",
                self.xdg_config / "Code" / "User" / "keybindings.json",
            ],
            "vscode": [
                self.xdg_config / "Code" / "User" / "settings.json",
                self.xdg_config / "Code" / "User" / "keybindings.json",
            ],
            "opencode": [
                self.xdg_config / "opencode" / "settings.json",
            ],
        }

        if app_name in app_configs:
            for path in app_configs[app_name]:
                if path.exists() and path.is_file():
                    path_str = str(path)
                    if path_str not in found_paths:
                        size = path.stat().st_size
                        if size < 10 * 1024 * 1024:
                            configs.append((path_str, size))
                            found_paths.add(path_str)

        return configs

    def get_user_configs_summary(self) -> Dict[str, List[Tuple[str, int]]]:
        """Get all user configs organized by category"""
        all_configs = {}

        # Shell configs
        shell_configs = []
        shell_configs.extend(self.discover_configs("zsh"))
        shell_configs.extend(self.discover_configs("bash"))
        shell_configs.extend(self.discover_configs("fish"))
        if shell_configs:
            all_configs["shells"] = shell_configs

        # Editor configs
        editor_configs = []
        editor_configs.extend(self.discover_configs("nvim"))
        editor_configs.extend(self.discover_configs("neovim"))
        editor_configs.extend(self.discover_configs("vim"))
        editor_configs.extend(self.discover_configs("code"))
        editor_configs.extend(self.discover_configs("vscode"))
        if editor_configs:
            all_configs["editors"] = editor_configs

        # Terminal configs
        terminal_configs = []
        terminal_configs.extend(self.discover_configs("kitty"))
        terminal_configs.extend(self.discover_configs("alacritty"))
        terminal_configs.extend(self.discover_configs("terminator"))
        if terminal_configs:
            all_configs["terminals"] = terminal_configs

        # CLI tool configs
        cli_configs = []
        cli_configs.extend(self.discover_configs("fzf"))
        cli_configs.extend(self.discover_configs("zoxide"))
        cli_configs.extend(self.discover_configs("git"))
        cli_configs.extend(self.discover_configs("ssh"))
        cli_configs.extend(self.discover_configs("cargo"))
        cli_configs.extend(self.discover_configs("rustup"))
        if cli_configs:
            all_configs["cli_tools"] = cli_configs

        return all_configs

    def get_global_configs(self) -> List[Tuple[str, int]]:
        """Get global/user configs like themes, icons, fonts"""
        configs = []
        found_paths: Set[str] = set()
        home = Path.home()

        # Themes
        themes_dir = home / ".themes"
        if themes_dir.exists():
            # Only get theme directories, not all files
            for theme_dir in themes_dir.iterdir():
                if theme_dir.is_dir():
                    # Get CSS/config files from theme
                    for config_file in ["gtk.css", "gtk-dark.css", "index.theme"]:
                        config_path = theme_dir / config_file
                        if config_path.exists() and config_path.is_file():
                            path_str = str(config_path)
                            if path_str not in found_paths:
                                size = config_path.stat().st_size
                                if size < 10 * 1024 * 1024:
                                    configs.append((path_str, size))
                                    found_paths.add(path_str)

        # Icons
        icons_dir = home / ".icons"
        if icons_dir.exists():
            # Only get icon theme index files
            for icon_dir in icons_dir.iterdir():
                if icon_dir.is_dir():
                    index_file = icon_dir / "index.theme"
                    if index_file.exists():
                        path_str = str(index_file)
                        if path_str not in found_paths:
                            size = index_file.stat().st_size
                            configs.append((path_str, size))
                            found_paths.add(path_str)

        # Fonts
        fonts_dir = home / ".fonts"
        if fonts_dir.exists():
            # Don't backup actual font files (too big), just fontconfig
            fontconfig_dir = home / ".config" / "fontconfig"
            if fontconfig_dir.exists():
                for item in fontconfig_dir.rglob("*"):
                    if item.is_file() and item.suffix in [".conf", ".xml"]:
                        path_str = str(item)
                        if path_str not in found_paths:
                            size = item.stat().st_size
                            if size < 10 * 1024 * 1024:
                                configs.append((path_str, size))
                                found_paths.add(path_str)

        # Desktop entries (custom .desktop files)
        apps_dir = home / ".local" / "share" / "applications"
        if apps_dir.exists():
            for desktop_file in apps_dir.glob("*.desktop"):
                path_str = str(desktop_file)
                if path_str not in found_paths:
                    size = desktop_file.stat().st_size
                    configs.append((path_str, size))
                    found_paths.add(path_str)

        return configs


if __name__ == "__main__":
    discovery = SmartConfigDiscovery()

    # Test
    test_apps = [
        "zsh",
        "fzf",
        "kitty",
        "bash",
        "git",
        "nvim",
        "code",
        "cargo",
        "rustup",
    ]

    print("Smart Config Discovery - ONLY Config Files")
    print("=" * 70)

    for app in test_apps:
        configs = discovery.discover_configs(app)
        if configs:
            total_size = sum(size for _, size in configs)
            print(f"\n{app}: {len(configs)} files ({total_size / 1024:.1f} KB)")
            for path, size in configs:
                print(f"  - {path} ({size / 1024:.1f} KB)")
