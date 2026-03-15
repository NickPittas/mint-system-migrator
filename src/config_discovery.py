#!/usr/bin/env python3
"""
Live config discovery for selected applications.

This module does not keep a per-app hardcoded map.
It scans the user's filesystem at runtime and finds candidate config files
for the selected apps under common config roots.
"""

from __future__ import annotations

import glob
import os
import re
from pathlib import Path
from typing import Iterable, List, Set, Tuple


ConfigEntry = Tuple[str, int]


class SmartConfigDiscovery:
    """Discover config files dynamically from the live filesystem."""

    EXCLUDED_DIRS = {
        "__pycache__",
        ".git",
        ".github",
        ".hg",
        ".svn",
        ".cache",
        "cache",
        "cache2",
        "cacheddata",
        "code cache",
        "gpucache",
        "blob_storage",
        "logs",
        "log",
        "tmp",
        "temp",
        "crashpad",
        "crashes",
        "service worker",
        "session storage",
        "sessions",
        "indexeddb",
        "dawncache",
        "shadercache",
        "node_modules",
        "vendor",
        "doc",
        "docs",
        "venv",
        ".venv",
        "toolchains",
        "registry",
        "update hashes",
        "downloads",
        "steamapps",
        "games",
    }

    EXCLUDED_DIR_PARTS = {
        "cache",
        "log",
        "crash",
        "tmp",
        "temp",
        "session",
        "history",
        "backup",
        "storage",
        "snapshot",
        "download",
        "registry",
        "update",
        "test",
        "docs",
        "doc",
        "example",
        "examples",
        "bin",
        "man",
        "source",
        "src",
    }

    EXCLUDED_FILE_NAMES = {
        ".ds_store",
        "thumbs.db",
        ".gitignore",
        ".gitattributes",
        ".gitmodules",
        ".git-credentials",
    }

    EXCLUDED_SUFFIXES = {
        ".log",
        ".lock",
        ".bak",
        ".backup",
        ".old",
        ".pid",
        ".tmp",
        ".temp",
        ".cache",
        ".journal",
    }

    EXCLUDED_NAME_PARTS = {
        "cache",
        "log",
        "crash",
        "lock",
        "tmp",
        "temp",
        "journal",
        "history",
        "backup",
    }

    ALLOWED_EXTENSIONS = {
        ".conf",
        ".cfg",
        ".ini",
        ".json",
        ".jsonc",
        ".toml",
        ".yaml",
        ".yml",
        ".xml",
        ".lua",
        ".vim",
        ".vdf",
        ".desktop",
        ".theme",
        ".rc",
        ".db",
        ".sqlite",
        ".sqlite3",
    }

    STRICT_DATA_EXTENSIONS = {
        ".conf",
        ".cfg",
        ".ini",
        ".json",
        ".jsonc",
        ".toml",
        ".yaml",
        ".yml",
        ".xml",
        ".desktop",
        ".theme",
        ".lua",
        ".vim",
        ".rc",
        ".py",
        ".nk",
        ".pref",
    }

    CONFIG_NAME_KEYWORDS = {
        "config",
        "settings",
        "prefs",
        "pref",
        "preferences",
        "theme",
        "themes",
        "shortcut",
        "shortcuts",
        "workspace",
        "workspaces",
        "preset",
        "presets",
        "toolset",
        "toolsets",
        "menu",
        "init",
        "plugin",
        "plugins",
        "validator",
        "profile",
        "profiles",
        "keybinding",
        "keybindings",
        "auth",
        "token",
        "model",
        "bookmarks",
        "registry",
        "ocio",
    }

    GENERIC_TOKENS = {
        "desktop",
        "stable",
        "studio",
        "browser",
        "community",
        "edition",
        "client",
        "server",
        "gtk",
        "qt",
        "cli",
        "gui",
        "ce",
    }

    MAX_FILE_SIZE = 20 * 1024 * 1024
    MAX_TEXT_PROBE = 4096

    def __init__(self) -> None:
        self.home = Path.home()
        self.xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", self.home / ".config"))
        self.xdg_data = Path(
            os.environ.get("XDG_DATA_HOME", self.home / ".local" / "share")
        )
        self.xdg_state = Path(
            os.environ.get("XDG_STATE_HOME", self.home / ".local" / "state")
        )

    def discover_configs(self, app_name: str) -> List[ConfigEntry]:
        aliases = self._aliases(app_name)
        found: Set[str] = set()
        results: List[ConfigEntry] = []

        for path in self._discover_home_entries(aliases):
            results.extend(self._collect_from_path(path, found))

        for root in (self.xdg_config,):
            for path in self._discover_root_entries(root, aliases):
                results.extend(self._collect_from_path(path, found))

        for root in (self.xdg_data, self.xdg_state):
            for path in self._discover_root_entries(root, aliases):
                results.extend(self._collect_data_path(path, found))

        return sorted(results, key=lambda item: item[0].lower())

    def get_global_configs(self) -> List[ConfigEntry]:
        found: Set[str] = set()
        results: List[ConfigEntry] = []

        global_roots = [
            self.home / ".themes",
            self.home / ".icons",
            self.home / ".fonts",
            self.xdg_config / "fontconfig",
            self.home / ".local" / "share" / "applications",
        ]

        for root in global_roots:
            if not root.exists():
                continue
            if root.is_file():
                results.extend(self._collect_global_file(root, found))
                continue
            for base, dirs, files in os.walk(root):
                dirs[:] = [
                    directory
                    for directory in dirs
                    if not self._is_excluded_dir_name(directory)
                ]
                base_path = Path(base)
                for file_name in files:
                    results.extend(
                        self._collect_global_file(base_path / file_name, found)
                    )

        return sorted(results, key=lambda item: item[0].lower())

    def _aliases(self, app_name: str) -> Set[str]:
        raw = app_name.strip().lower()
        normalized = self._normalize(raw)
        aliases = {raw, normalized}

        parts = [p for p in normalized.split() if p and p not in self.GENERIC_TOKENS]
        aliases.update(parts)
        if parts:
            aliases.add(" ".join(parts))
            aliases.add("".join(parts))

        return {alias for alias in aliases if len(alias) >= 2}

    def _discover_home_entries(self, aliases: Set[str]) -> Iterable[Path]:
        try:
            for child in self.home.iterdir():
                if self._matches_name(child.name, aliases):
                    yield child
        except OSError:
            return

    def _discover_root_entries(self, root: Path, aliases: Set[str]) -> Iterable[Path]:
        if not root.exists() or not root.is_dir():
            return

        try:
            first_level = list(root.iterdir())
        except OSError:
            return

        for child in first_level:
            if self._matches_name(child.name, aliases):
                yield child
            if child.is_dir():
                try:
                    for grandchild in child.iterdir():
                        if grandchild.is_dir() and self._matches_name(
                            grandchild.name, aliases
                        ):
                            yield grandchild
                except OSError:
                    continue

    def _matches_name(self, name: str, aliases: Set[str]) -> bool:
        normalized_name = self._normalize(name)
        if not normalized_name:
            return False
        tokens = normalized_name.split()
        return any(
            normalized_name == alias
            or normalized_name.startswith(alias)
            or normalized_name.startswith(alias + " ")
            or (
                len(alias) >= 5
                and (
                    normalized_name.endswith(alias)
                    or alias in tokens
                    or any(token.startswith(alias) for token in tokens)
                )
            )
            for alias in aliases
        )

    def _collect_from_path(self, path: Path, found: Set[str]) -> List[ConfigEntry]:
        if path.is_file():
            return self._collect_file(path, found)

        if not path.is_dir():
            return []

        if (path / ".git").exists():
            return []

        results: List[ConfigEntry] = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [
                directory
                for directory in dirs
                if not self._is_excluded_dir_name(directory)
            ]
            root_path = Path(root)
            if (root_path / ".git").exists():
                dirs[:] = []
                continue
            for file_name in files:
                child = root_path / file_name
                results.extend(self._collect_file(child, found))
        return results

    def _collect_data_path(self, path: Path, found: Set[str]) -> List[ConfigEntry]:
        if path.is_file():
            return self._collect_data_file(path, found)

        if not path.is_dir():
            return []

        results: List[ConfigEntry] = []
        base_depth = len(path.parts)
        for root, dirs, files in os.walk(path):
            root_path = Path(root)
            depth = len(root_path.parts) - base_depth
            dirs[:] = [
                directory
                for directory in dirs
                if not self._is_excluded_dir_name(directory) and depth < 2
            ]
            for file_name in files:
                child = root_path / file_name
                results.extend(self._collect_data_file(child, found))
        return results

    def _collect_file(self, path: Path, found: Set[str]) -> List[ConfigEntry]:
        path_str = str(path)
        if path_str in found:
            return []
        if not self._is_config_file(path):
            return []

        try:
            size = path.stat().st_size
        except OSError:
            return []

        found.add(path_str)
        results = [(path_str, size)]
        results.extend(self._collect_referenced_paths(path, found))
        return results

    def _collect_global_file(self, path: Path, found: Set[str]) -> List[ConfigEntry]:
        path_str = str(path)
        if path_str in found:
            return []
        if not self._is_global_config_file(path):
            return []

        try:
            size = path.stat().st_size
        except OSError:
            return []

        found.add(path_str)
        return [(path_str, size)]

    def _collect_data_file(self, path: Path, found: Set[str]) -> List[ConfigEntry]:
        path_str = str(path)
        if path_str in found:
            return []
        if not self._is_data_config_file(path):
            return []

        try:
            size = path.stat().st_size
        except OSError:
            return []

        found.add(path_str)
        return [(path_str, size)]

    def _is_config_file(self, path: Path) -> bool:
        try:
            if not path.is_file():
                return False
            size = path.stat().st_size
        except OSError:
            return False

        if size > self.MAX_FILE_SIZE:
            return False
        if any(self._is_excluded_dir_name(part) for part in path.parts[:-1]):
            return False

        suffix = path.suffix.lower()
        name = path.name.lower()

        if name in self.EXCLUDED_FILE_NAMES:
            return False
        if suffix in self.EXCLUDED_SUFFIXES:
            return False
        if any(part in name for part in self.EXCLUDED_NAME_PARTS):
            return False

        if suffix in self.ALLOWED_EXTENSIONS:
            return True

        if name in {
            "config",
            "settings",
            "preferences",
            "prefs.js",
            "bookmarks",
            "known_hosts",
            "authorized_keys",
            "config.json",
            "settings.json",
            "keybindings.json",
            "init.lua",
            "init.vim",
            "kitty.conf",
            "alacritty.toml",
            "alacritty.yml",
            "registry.vdf",
            "localconfig.vdf",
        }:
            return True

        if name.startswith(".") and self._looks_like_text(path):
            return True

        if suffix in {".py", ".nk", ".pref"} and self._has_config_keyword(name):
            return True

        return False

    def _is_data_config_file(self, path: Path) -> bool:
        try:
            if not path.is_file():
                return False
            size = path.stat().st_size
        except OSError:
            return False

        if size > self.MAX_FILE_SIZE:
            return False
        if any(self._is_excluded_dir_name(part) for part in path.parts[:-1]):
            return False

        suffix = path.suffix.lower()
        name = path.name.lower()

        if name in self.EXCLUDED_FILE_NAMES:
            return False
        if suffix in self.EXCLUDED_SUFFIXES:
            return False
        if any(part in name for part in self.EXCLUDED_NAME_PARTS):
            return False
        if suffix not in self.STRICT_DATA_EXTENSIONS:
            return False

        return self._has_config_keyword(name)

    def _is_global_config_file(self, path: Path) -> bool:
        try:
            if not path.is_file():
                return False
            size = path.stat().st_size
        except OSError:
            return False

        if size > self.MAX_FILE_SIZE:
            return False
        if any(self._is_excluded_dir_name(part) for part in path.parts[:-1]):
            return False

        suffix = path.suffix.lower()
        return suffix in {
            ".conf",
            ".cfg",
            ".ini",
            ".json",
            ".jsonc",
            ".toml",
            ".yaml",
            ".yml",
            ".xml",
            ".desktop",
            ".theme",
            ".css",
            ".scss",
            ".svg",
            ".png",
            ".jpg",
            ".jpeg",
            ".ico",
            ".ttf",
            ".otf",
            ".woff",
            ".woff2",
        }

    def _collect_referenced_paths(
        self, path: Path, found: Set[str]
    ) -> List[ConfigEntry]:
        if not self._supports_reference_parsing(path):
            return []

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        patterns = [
            r"^\s*source\s+['\"]?([^'\"\n]+)",
            r"^\s*\.\s+['\"]?([^'\"\n]+)",
            r"^\s*include\s+['\"]?([^'\"\n]+)",
            r"^\s*include-file\s+['\"]?([^'\"\n]+)",
        ]

        referenced: List[ConfigEntry] = []
        for pattern in patterns:
            for match in re.findall(pattern, content, flags=re.MULTILINE):
                candidate = match.strip().strip("\"'")
                if not candidate or candidate.startswith("$"):
                    continue
                for resolved in self._resolve_reference(path.parent, candidate):
                    referenced.extend(self._collect_from_path(resolved, found))

        return referenced

    def _resolve_reference(self, base_dir: Path, candidate: str) -> List[Path]:
        expanded = os.path.expandvars(candidate)
        expanded = os.path.expanduser(expanded)
        target = Path(expanded)
        if not target.is_absolute():
            target = (base_dir / target).resolve()

        if any(char in str(target) for char in "*?["):
            return [
                Path(path)
                for path in glob.glob(str(target), recursive=True)
                if Path(path).exists()
            ]

        try:
            return [target] if target.exists() else []
        except OSError:
            return []

    def _supports_reference_parsing(self, path: Path) -> bool:
        suffix = path.suffix.lower()
        if suffix in {
            ".conf",
            ".cfg",
            ".ini",
            ".toml",
            ".yaml",
            ".yml",
            ".lua",
            ".vim",
            ".rc",
        }:
            return True
        return path.name.lower() in {
            ".zshrc",
            ".bashrc",
            ".profile",
            ".bash_profile",
            "kitty.conf",
            "alacritty.toml",
            "alacritty.yml",
            "config",
        }

    def _looks_like_text(self, path: Path) -> bool:
        try:
            with path.open("rb") as handle:
                chunk = handle.read(self.MAX_TEXT_PROBE)
        except OSError:
            return False

        if b"\x00" in chunk:
            return False

        try:
            chunk.decode("utf-8")
            return True
        except UnicodeDecodeError:
            try:
                chunk.decode("latin-1")
                return True
            except UnicodeDecodeError:
                return False

    def _is_excluded_dir(self, path: Path) -> bool:
        return self._is_excluded_dir_name(path.name)

    def _is_excluded_dir_name(self, name: str) -> bool:
        normalized = self._normalize(name)
        return (
            name.lower() in self.EXCLUDED_DIRS
            or normalized in self.EXCLUDED_DIRS
            or any(part in normalized for part in self.EXCLUDED_DIR_PARTS)
        )

    def _has_config_keyword(self, name: str) -> bool:
        normalized = self._normalize(name)
        return any(keyword in normalized for keyword in self.CONFIG_NAME_KEYWORDS)

    @staticmethod
    def _normalize(value: str) -> str:
        cleaned = value.lower().replace("_", " ").replace("-", " ").replace(".", " ")
        return " ".join(cleaned.split())
