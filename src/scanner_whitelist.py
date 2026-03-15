#!/usr/bin/env python3
"""
Whitelist-based scanner - only include known user applications
This is more reliable than trying to filter out system packages
"""

import subprocess
import base64
import json
from pathlib import Path
from typing import Set, List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import re


@dataclass
class Application:
    name: str
    display_name: str = ""
    description: str = ""
    install_method: str = "unknown"
    install_source: str = ""
    version: str = ""
    category: str = "Other"
    selected: bool = True
    config_paths: List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "install_method": self.install_method,
            "install_source": self.install_source,
            "version": self.version,
            "category": self.category,
            "selected": self.selected,
            "config_paths": self.config_paths,
        }


@dataclass
class Repository:
    type: str
    name: str
    url: str
    components: List[str] = field(default_factory=list)
    suite: str = ""
    source_line: str = ""
    key_file: Optional[str] = None
    key_file_content_base64: Optional[str] = None
    enabled: bool = True

    def to_dict(self):
        return {
            "type": self.type,
            "name": self.name,
            "url": self.url,
            "components": self.components,
            "suite": self.suite,
            "source_line": self.source_line,
            "key_file": self.key_file,
            "key_file_content_base64": self.key_file_content_base64,
            "enabled": self.enabled,
        }


# WHITELIST: Known user-installed applications
# Only these will be included by default
KNOWN_USER_APPS = {
    # Development
    "code",
    "vscode",
    "visual-studio-code",
    "docker",
    "docker-ce",
    "docker.io",
    "git",
    "git-lfs",
    "nodejs",
    "npm",
    "yarn",
    "python3-pip",
    "pipx",
    "vim",
    "vim-gtk",
    "neovim",
    "nvim",
    "alacritty",
    "kitty",
    "wezterm",
    "terminator",
    "tilix",
    "fzf",
    "bat",
    "exa",
    "eza",
    "ripgrep",
    "fd-find",
    "zoxide",
    "htop",
    "btop",
    "gotop",
    "bashtop",
    "jetbrains-toolbox",
    "pycharm",
    "intellij-idea",
    "dbeaver",
    "dbeaver-ce",
    "postman",
    "insomnia",
    "gitkraken",
    # Media
    "gimp",
    "krita",
    "inkscape",
    "blender",
    "kdenlive",
    "shotcut",
    "openshot",
    "obs-studio",
    "simplescreenrecorder",
    "vlc",
    "mpv",
    "celluloid",
    "rhythmbox",
    "clementine",
    "amarok",
    "audacity",
    "ardour",
    "lmms",
    "handbrake",
    "makemkv",
    "davinci-resolve",
    "davinci-resolve-studio",
    "darktable",
    "rawtherapee",
    # Communication
    "slack",
    "slack-desktop",
    "discord",
    "discord-canary",
    "telegram",
    "telegram-desktop",
    "signal",
    "signal-desktop",
    "thunderbird",
    "evolution",
    "hexchat",
    "irssi",
    "weechat",
    "zoom",
    "teams",
    "microsoft-teams",
    "skype",
    "skypeforlinux",
    "element",
    "element-desktop",
    "jitsi",
    "jitsi-meet",
    # Browsers
    "firefox",
    "firefox-esr",
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
    "brave",
    "brave-browser",
    "vivaldi",
    "vivaldi-stable",
    "opera",
    "opera-stable",
    "microsoft-edge",
    "microsoft-edge-stable",
    "librewolf",
    # Gaming
    "steam",
    "steam-launcher",
    "lutris",
    "wine",
    "wine-stable",
    "winehq-stable",
    "playonlinux",
    "retroarch",
    "minecraft",
    "minecraft-launcher",
    "discord",
    "gamemode",
    "mangohud",
    # Productivity
    "obsidian",
    "obsidian-md",
    "notion",
    "notion-app",
    "todoist",
    "anki",
    "calibre",
    "okular",
    "evince",
    "zathura",
    "joplin",
    "joplin-desktop",
    "standard-notes",
    "marktext",
    "typora",
    # Security
    "zerotier-one",
    "zerotier-cli",
    "tailscale",
    "tailscaled",
    "wireguard",
    "wireguard-tools",
    "openvpn",
    "openvpn-systemd-resolved",
    "protonvpn",
    "protonvpn-cli",
    "protonvpn-gui",
    "nordvpn",
    "expressvpn",
    "keepassxc",
    "keepass2",
    "bitwarden",
    "bitwarden-cli",
    "veracrypt",
    # System Tools
    "neofetch",
    "pfetch",
    "screenfetch",
    "stacer",
    "timeshift",
    "timeshift-autosnap",
    "gnome-tweaks",
    "tweaks",
    "dconf-editor",
    "gparted",
    "bleachbit",
    "deja-dup",
    "duplicity",
    "backintime",
    "conky",
    "conky-all",
    "conky-manager",
    "coolercontrol",
    "coolercontrold",
    # Network
    "qbittorrent",
    "transmission",
    "transmission-gtk",
    "deluge",
    "vuze",
    "syncthing",
    "syncthing-gtk",
    "filezilla",
    "putty",
    "remmina",
    "anydesk",
    "teamviewer",
    "rustdesk",
    # Cloud Storage
    "dropbox",
    "megasync",
    "nextcloud",
    "nextcloud-desktop",
    "owncloud",
    "owncloud-client",
    "pcloud",
    "insync",
    "rclone",
    "rclone-browser",
    # Utilities
    "flameshot",
    "peek",
    "kazam",
    "shutter",
    "xclip",
    "xsel",
    "redshift",
    "redshift-gtk",
    "f.lux",
    "fluxgui",
    "latte-dock",
    "plank",
    "cairo-dock",
    "tint2",
    # Virtualization
    "virtualbox",
    "virtualbox-6.1",
    "virtualbox-7.0",
    "virt-manager",
    "qemu",
    "qemu-kvm",
    "podman",
    "podman-docker",
    "vagrant",
    # Programming Languages
    "golang",
    "golang-go",
    "rustc",
    "cargo",
    "ruby",
    "ruby-dev",
    "openjdk",
    "default-jdk",
    "dotnet",
    "dotnet-sdk",
    "flutter",
    "android-studio",
    # Creative
    "godot",
    "godot-engine",
    "unity",
    "unity-hub",
    "unreal-engine",
    "figma-linux",
    "penpot",
    "penpot-desktop",
    "kicad",
    "freecad",
    "openscad",
    "cura",
    "prusa-slicer",
    "bambu-studio",
    # Custom
    "gallerybrowser",
    "spruce",
    "fan-control",
    "mission-center",
    "trayscale",
    "sunshine",
    "buzz",
    "fsearch",
    "hidamari",
    "angryip",
    "ipscan",
    "bleachbit",
    "ktailctl",
    "nomacs",
}


# Dependency/library patterns to exclude
DEPENDENCY_PATTERNS = {
    "-data",
    "-common",
    "-dev",
    "-dbg",
    "-doc",
    "-examples",
    "-locale-",
    "-l10n",
    "-i18n",
    "-locale-",
    "-plugin",
    "-plugins",
    "-addon",
    "-addons",
    "-bin",
    "-utils",
    "-tools",
    "-runtime",
    "-qt",
    "-gtk",
    "-cli",
    "-gui",
    "-daemon",
    "-headless",
    "-driver",
    "-drivers",
    "-module",
    "-modules",
    "-extra",
    "-extras",
    "-base",
    "-core",
    "-libs",
    "-lib",
    "-all",
    "-full",
    "-system",
    "-system-",
    "-devices",
    "-installer",
    "-rootless-extras",
    "-buildx-plugin",
    "-compose-plugin",
}


def is_user_app(pkg: str) -> bool:
    """Check if package is a known user application"""
    # Direct match
    if pkg in KNOWN_USER_APPS:
        return True

    # Check common suffixes/prefixes for main apps
    for app in KNOWN_USER_APPS:
        if pkg == app:
            return True
        # Allow specific suffixes that indicate main app variants
        if pkg.startswith(app + "-"):
            # Check if it's a dependency pattern
            suffix = pkg[len(app) :]
            if any(pattern in suffix for pattern in DEPENDENCY_PATTERNS):
                return False
            # Allow versioned packages (e.g., virtualbox-7.0, openjdk-21-jdk)
            suffix_without_dashes = suffix[1:].replace("-", "").replace(".", "")
            if suffix_without_dashes.isdigit():
                return True
            # Check if suffix contains version numbers (e.g., "21jdk" -> digits mixed with letters)
            if any(char.isdigit() for char in suffix_without_dashes):
                # Contains digits, likely a versioned package
                return True
            # Allow edition variants
            allowed_suffixes = ["-desktop", "-server", "-studio", "-ce", "-stable"]
            if any(suffix.startswith(s) for s in allowed_suffixes):
                return True
            return False
        if pkg.endswith("-" + app):
            return False

        if pkg.endswith("-" + app):
            return False

    return False


def has_user_config(pkg: str) -> Tuple[bool, List[str]]:
    """Check if package has user configs"""
    config_paths = []

    known_configs = {
        "bash": ["~/.bashrc", "~/.bash_profile", "~/.bash_aliases"],
        "zsh": ["~/.zshrc", "~/.zprofile", "~/.zshenv", "~/.oh-my-zsh"],
        "fish": ["~/.config/fish/config.fish"],
        "vim": ["~/.vimrc", "~/.vim"],
        "neovim": ["~/.config/nvim"],
        "git": ["~/.gitconfig", "~/.gitignore_global"],
        "ssh": ["~/.ssh/config", "~/.ssh/authorized_keys"],
        "docker": ["~/.docker/config.json"],
        "alacritty": ["~/.config/alacritty/alacritty.yml"],
        "kitty": ["~/.config/kitty/kitty.conf", "~/.kitty.conf"],
        "conky": ["~/.conkyrc", "~/.config/conky"],
    }

    if pkg in known_configs:
        for path in known_configs[pkg]:
            expanded = Path(path).expanduser()
            if expanded.exists():
                config_paths.append(str(expanded))

    # Check standard paths
    xdg_paths = [
        Path.home() / ".config" / pkg,
        Path.home() / f".{pkg}",
        Path.home() / f".{pkg}rc",
    ]

    for path in xdg_paths:
        if path.exists() and str(path) not in config_paths:
            config_paths.append(str(path))

    return len(config_paths) > 0, config_paths


class WhitelistApplicationScanner:
    """Scanner that only includes whitelisted user applications"""

    def __init__(self):
        self.progress_callback = None
        self.log_callback = None

    def set_callbacks(self, progress_callback=None, log_callback=None):
        self.progress_callback = progress_callback
        self.log_callback = log_callback

    def log(self, message: str):
        if self.log_callback:
            self.log_callback(message)

    def progress(self, percent: int, message: str):
        if self.progress_callback:
            self.progress_callback(percent, message)
        self.log(message)

    def scan_apt_packages(self) -> List[Application]:
        """Scan APT for user applications"""
        apps = []

        self.progress(20, "Scanning for user applications...")

        # Get all installed packages
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Package}\n"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        all_packages = result.stdout.strip().split("\n")

        self.log(
            f"Checking {len(all_packages)} installed packages against whitelist..."
        )

        found = 0
        for i, pkg in enumerate(all_packages):
            if not pkg:
                continue

            # Progress
            if i % 100 == 0:
                percent = 20 + int((i / len(all_packages)) * 30)
                self.progress(percent, f"Checking: {pkg}")

            # Check if it's a user app
            if not is_user_app(pkg):
                continue

            # Get package info
            try:
                result = subprocess.run(
                    ["dpkg-query", "-W", "-f=${binary:Summary}|${Version}", pkg],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )

                if result.returncode == 0:
                    parts = result.stdout.split("|")
                    desc = parts[0][:80] if parts else ""
                    version = parts[1] if len(parts) > 1 else ""
                else:
                    desc = ""
                    version = ""
            except:
                desc = ""
                version = ""

            # Check for configs
            has_config, config_paths = has_user_config(pkg)
            category = self._categorize(pkg, desc)

            app = Application(
                name=pkg,
                display_name=pkg.replace("-", " ").title(),
                description=desc,
                install_method="apt",
                install_source=pkg,
                version=version,
                category=category,
                config_paths=config_paths if has_config else [],
            )
            apps.append(app)
            found += 1
            self.log(f"  ✓ {pkg} ({category})")

        self.log(f"")
        self.log(f"Found {found} user applications")

        return apps

    def _categorize(self, name: str, desc: str) -> str:
        """Categorize package"""
        combined = f"{name} {desc}".lower()

        cats = {
            "Development": [
                "code",
                "git",
                "docker",
                "vim",
                "neovim",
                "vscode",
                "kitty",
                "alacritty",
                "fzf",
                "bat",
                "jetbrains",
                "pycharm",
                "dbeaver",
                "postman",
            ],
            "Media": [
                "gimp",
                "kdenlive",
                "vlc",
                "mpv",
                "obs",
                "davinci",
                "resolve",
                "blender",
                "krita",
                "audacity",
            ],
            "Communication": [
                "slack",
                "telegram",
                "discord",
                "thunderbird",
                "signal",
                "zoom",
                "teams",
            ],
            "Browser": ["firefox", "chrome", "chromium", "vivaldi", "brave", "opera"],
            "Gaming": ["steam", "lutris", "wine", "gamemode"],
            "Security": ["tailscale", "zerotier", "wireguard", "keepass"],
            "System": [
                "htop",
                "neofetch",
                "stacer",
                "conky",
                "timeshift",
                "coolercontrol",
            ],
            "Productivity": ["obsidian", "notion", "calibre", "joplin"],
            "Network": [
                "qbittorrent",
                "transmission",
                "syncthing",
                "filezilla",
                "rustdesk",
            ],
        }

        for cat, keywords in cats.items():
            if any(k in combined for k in keywords):
                return cat

        return "Other"

    def scan_flatpak(self) -> List[Application]:
        """Scan Flatpak"""
        apps = []

        self.progress(50, "Scanning Flatpak apps...")

        try:
            result = subprocess.run(
                ["flatpak", "list", "--app", "--columns=application,name,version"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            for line in result.stdout.strip().split("\n"):
                if "\t" not in line:
                    continue

                parts = line.split("\t")
                if len(parts) >= 3:
                    app_id = parts[0].strip()
                    name = parts[1].strip()
                    version = parts[2].strip() if len(parts) > 2 else ""

                    if any(x in app_id.lower() for x in ["platform", "runtime", "sdk"]):
                        continue

                    apps.append(
                        Application(
                            name=name,
                            display_name=name,
                            description=f"Flatpak: {app_id}",
                            install_method="flatpak",
                            install_source=app_id,
                            version=version,
                            category=self._categorize(name, ""),
                            config_paths=[f"~/.var/app/{app_id}"],
                        )
                    )
                    self.log(f"  ✓ {name}")
        except:
            pass

        self.log(f"Found {len(apps)} Flatpak apps")
        return apps


class WhitelistSystemScanner:
    """Main scanner using whitelist approach"""

    def __init__(self):
        self.app_scanner = WhitelistApplicationScanner()
        self.progress_callback = None
        self.log_callback = None

    def set_callbacks(self, progress_callback=None, log_callback=None):
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.app_scanner.set_callbacks(progress_callback, log_callback)

    def log(self, message: str):
        if self.log_callback:
            self.log_callback(message)

    def progress(self, percent: int, message: str):
        if self.progress_callback:
            self.progress_callback(percent, message)
        self.log(message)

    def scan_repos(self):
        """Scan repos"""
        repos = []
        self.progress(5, "Scanning repositories...")

        sources_d = Path("/etc/apt/sources.list.d")
        if sources_d.exists():
            for f in sources_d.glob("*.list"):
                content = f.read_text()
                for line in content.split("\n"):
                    line = line.strip()
                    if line.startswith("deb ") and not line.startswith("#"):
                        parts = line.split()
                        if len(parts) >= 4:
                            url_index = 1
                            if parts[1].startswith("["):
                                url_index = 2
                            if len(parts) <= url_index + 1:
                                continue

                            url = parts[url_index]
                            suite = parts[url_index + 1]
                            components = parts[url_index + 2 :]

                            key_file = None
                            key_file_content_base64 = None
                            if "signed-by=" in line:
                                match = re.search(r"signed-by=([^\s\]]+)", line)
                                if match:
                                    key_file = match.group(1)
                                    key_path = Path(key_file)
                                    if key_path.exists() and key_path.is_file():
                                        key_file_content_base64 = base64.b64encode(
                                            key_path.read_bytes()
                                        ).decode("ascii")

                            repos.append(
                                Repository(
                                    type="apt",
                                    name=f.stem,
                                    url=url,
                                    components=components,
                                    suite=suite,
                                    source_line=line,
                                    key_file=key_file,
                                    key_file_content_base64=key_file_content_base64,
                                )
                            )

        # Flatpak
        try:
            result = subprocess.run(
                ["flatpak", "remotes", "--columns=name,url"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.strip().split("\n"):
                if "\t" in line:
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        repos.append(
                            Repository(
                                type="flatpak",
                                name=parts[0].strip(),
                                url=parts[1].strip(),
                                source_line="",
                            )
                        )
        except:
            pass

        self.progress(15, f"Found {len(repos)} repositories")
        return repos

    def scan_services(self):
        """Scan services"""
        services = []
        self.progress(80, "Scanning services...")

        important = {
            "zerotier-one": "ZeroTier VPN",
            "tailscaled": "Tailscale VPN",
            "rlm": "RLM License Server",
            "docker": "Docker",
            "libvirtd": "Libvirt",
            "coolercontrold": "CoolerControl",
        }

        try:
            result = subprocess.run(
                [
                    "systemctl",
                    "list-unit-files",
                    "--state=enabled",
                    "--type=service",
                    "--no-pager",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            for line in result.stdout.strip().split("\n")[1:]:
                if "." in line:
                    svc = line.split(".")[0]
                    if svc in important:
                        active = subprocess.run(
                            ["systemctl", "is-active", svc],
                            capture_output=True,
                            text=True,
                        )

                        @dataclass
                        class Service:
                            name: str
                            display_name: str = ""
                            description: str = ""
                            enabled: bool = False
                            active: bool = False
                            selected: bool = True

                            def to_dict(self):
                                return {
                                    "name": self.name,
                                    "display_name": self.display_name,
                                    "description": self.description,
                                    "enabled": self.enabled,
                                    "active": self.active,
                                    "selected": self.selected,
                                }

                        services.append(
                            Service(
                                name=svc,
                                display_name=important[svc],
                                enabled=True,
                                active=active.stdout.strip() == "active",
                            )
                        )
        except:
            pass

        self.progress(85, f"Found {len(services)} services")
        return services

    def scan_vms(self):
        """Scan VMs"""
        vms = []
        self.progress(90, "Scanning VMs...")

        try:
            result = subprocess.run(
                ["virsh", "list", "--all", "--name"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            for vm_name in result.stdout.strip().split("\n"):
                vm_name = vm_name.strip()
                if vm_name:
                    xml_result = subprocess.run(
                        ["virsh", "dumpxml", vm_name],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    if xml_result.returncode == 0:
                        disk_paths = re.findall(
                            r'\u003csource file=[\'"]([^\'"]+)[\'"]\u003e',
                            xml_result.stdout,
                        )

                        @dataclass
                        class VMConfig:
                            name: str
                            type: str
                            xml_config: str = ""
                            disk_paths: List[str] = field(default_factory=list)
                            selected: bool = True

                            def to_dict(self):
                                return {
                                    "name": self.name,
                                    "type": self.type,
                                    "xml_config": self.xml_config,
                                    "disk_paths": self.disk_paths,
                                    "selected": self.selected,
                                }

                        vms.append(
                            VMConfig(
                                name=vm_name,
                                type="kvm",
                                xml_config=xml_result.stdout,
                                disk_paths=disk_paths,
                            )
                        )
        except:
            pass

        self.progress(95, f"Found {len(vms)} VMs")
        return vms

    def scan_all(self) -> dict:
        """Complete scan"""
        from datetime import datetime

        self.progress(0, "Starting scan...")
        self.log("=" * 60)
        self.log("Linux Mint Migration Tool - Whitelist Scanner")
        self.log("=" * 60)
        self.log("")
        self.log("Using whitelist of known user applications")
        self.log("(No system packages will be included)")
        self.log("")

        repos = self.scan_repos()

        apps = []
        apps.extend(self.app_scanner.scan_apt_packages())
        apps.extend(self.app_scanner.scan_flatpak())

        services = self.scan_services()
        vms = self.scan_vms()

        self.progress(100, "Complete!")
        self.log("")
        self.log("=" * 60)
        self.log(f"Found: {len(apps)} apps, {len(services)} services, {len(vms)} VMs")
        self.log("=" * 60)

        return {
            "repositories": [r.to_dict() for r in repos],
            "applications": [a.to_dict() for a in apps],
            "services": [s.to_dict() for s in services],
            "vms": [v.to_dict() for v in vms],
            "scan_date": datetime.now().isoformat(),
        }


# Export for compatibility
SystemScanner = WhitelistSystemScanner
VerboseSystemScanner = WhitelistSystemScanner


if __name__ == "__main__":
    print("Testing Whitelist Scanner...")
    print("=" * 60)

    scanner = WhitelistSystemScanner()

    def log(msg):
        print(msg)

    def progress(pct, msg):
        print(f"[{pct:3d}%] {msg}")

    scanner.set_callbacks(progress, log)
    result = scanner.scan_all()

    output_file = Path.home() / "scan_result_whitelist.json"
    output_file.write_text(json.dumps(result, indent=2))
    print(f"\n✓ Saved to: {output_file}")
