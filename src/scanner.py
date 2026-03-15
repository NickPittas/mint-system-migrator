#!/usr/bin/env python3
"""
Fast scanner using apt-mark to differentiate user vs auto packages
apt-mark showauto = packages installed as dependencies (pre-installed/system)
apt-mark showmanual = packages explicitly installed by user or mint-meta
"""

import subprocess
import json
from pathlib import Path
from typing import Set, List, Dict, Optional, Tuple, Callable
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
    is_preinstalled: bool = False

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
            "is_preinstalled": self.is_preinstalled,
        }


@dataclass
class Service:
    name: str
    display_name: str = ""
    enabled: bool = False
    active: bool = False
    selected: bool = True

    def to_dict(self):
        return {
            "name": self.name,
            "display_name": self.display_name,
            "enabled": self.enabled,
            "active": self.active,
            "selected": self.selected,
        }


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


@dataclass
class Repository:
    type: str
    name: str
    url: str
    components: List[str] = field(default_factory=list)
    key_file: Optional[str] = None
    enabled: bool = True

    def to_dict(self):
        return {
            "type": self.type,
            "name": self.name,
            "url": self.url,
            "components": self.components,
            "key_file": self.key_file,
            "enabled": self.enabled,
        }


# Known pre-installed package patterns (quick check)
PREINSTALLED_PATTERNS = {
    # Libraries
    "lib",
    "lib32",
    "lib64",
    "libx32",
    # Kernel
    "linux-image",
    "linux-headers",
    "linux-modules",
    "linux-tools",
    # Firmware
    "firmware-",
    # Python modules
    "python3-",
    "python-",
    # Perl modules
    "-perl",
    # GObject
    "gir1.2-",
    # GStreamer
    "gstreamer",
    # Fonts
    "fonts-",
    # ISO
    "iso-codes",
}

# Mint-specific packages
MINT_PACKAGES = {
    "mint-meta-cinnamon",
    "mint-meta-core",
    "mint-meta-codecs",
    "mint-artwork",
    "mint-common",
    "mint-themes",
    "mint-info-cinnamon",
    "mintbackup",
    "mintchat",
    "mintdrivers",
    "mintinstall",
    "mintlocale",
    "mintmenu",
    "mintreport",
    "mintsources",
    "mintstick",
    "mintsysadm",
    "mintsystem",
    "mintupdate",
    "mintupload",
    "mintwelcome",
    "cinnamon",
    "cinnamon-common",
    "cinnamon-control-center",
    "cinnamon-control-center-data",
    "cinnamon-desktop-data",
    "cinnamon-l10n",
    "cinnamon-screensaver",
    "cinnamon-session",
    "cinnamon-settings-daemon",
    "muffin",
    "muffin-common",
    "nemo",
    "nemo-data",
    "nemo-fileroller",
    "cjs",
    "muffin-dbg",
    "cinnamon-dbg",
}

# Default apps
DEFAULT_APPS = {
    "firefox",
    "firefox-locale-en",
    "firefox-locale-en-us",
    "celluloid",
    "vlc",
    "vlc-bin",
    "vlc-data",
    "vlc-plugin-base",
    "rhythmbox",
    "rhythmbox-data",
    "rhythmbox-plugins",
    "libreoffice-calc",
    "libreoffice-core",
    "libreoffice-gtk3",
    "libreoffice-common",
    "libreoffice-impress",
    "libreoffice-writer",
    "libreoffice-style-elementary",
    "drawing",
    "pix",
    "pix-dbg",
    "gthumb",
    "gthumb-data",
    "xed",
    "xreader",
    "xviewer",
    "xplayer",
    "warpinator",
    "webapp-manager",
    "sticky",
    "hypnotix",
    "thingy",
    "simple-scan",
    "bulk-rename",
    "bulky",
    "baobab",
    "gnome-calculator",
    "gnome-calendar",
    "gnome-screenshot",
    "gnome-disk-utility",
    "gnome-system-monitor",
    "gnome-font-viewer",
    "gnome-logs",
    "gnome-power-manager",
}

# System utilities
SYSTEM_UTILS = {
    "bash",
    "coreutils",
    "grep",
    "sed",
    "awk",
    "tar",
    "gzip",
    "bzip2",
    "xz-utils",
    "mount",
    "util-linux",
    "findutils",
    "diffutils",
    "libc6",
    "libc-bin",
    "libgcc-s1",
    "libstdc++6",
    "systemd",
    "systemd-sysv",
    "dbus",
    "dpkg",
    "apt",
    "apt-utils",
    "debconf",
    "ucf",
    "base-files",
    "base-passwd",
    "grub-pc",
    "grub-common",
    "os-prober",
    "efibootmgr",
    "network-manager",
    "cups",
    "avahi-daemon",
    "bluetooth",
    "pulseaudio",
    "alsa-utils",
    "bluez",
    "blueman",
}


def is_preinstalled_pattern(pkg: str) -> bool:
    """Quick check if package matches pre-installed patterns"""
    if pkg in MINT_PACKAGES or pkg in DEFAULT_APPS or pkg in SYSTEM_UTILS:
        return True

    for pattern in PREINSTALLED_PATTERNS:
        if pkg.startswith(pattern) or pattern in pkg:
            return True

    return False


def has_user_config(pkg: str) -> Tuple[bool, List[str]]:
    """Check if a package has user configuration files"""
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


class FastApplicationScanner:
    """Fast scanner using apt-mark"""

    def __init__(self):
        self.progress_callback = None
        self.log_callback = None
        self.auto_packages: Set[str] = set()
        self.manual_packages: Set[str] = set()
        self.mint_preinstalled: Set[str] = set()

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

    def load_package_lists(self):
        """Load auto and manual package lists from apt-mark"""
        self.progress(18, "Loading package lists...")

        # Load comprehensive pre-installed packages list (mint-meta + auto-installed)
        preinstalled_file = Path.home() / "all_preinstalled_packages.txt"
        if preinstalled_file.exists():
            self.mint_preinstalled = set(
                preinstalled_file.read_text().strip().split("\n")
            )
            self.log(f"Loaded {len(self.mint_preinstalled)} pre-installed packages")
        else:
            self.log(
                "Warning: all_preinstalled_packages.txt not found, using patterns only"
            )

        # Get manually installed packages
        result = subprocess.run(
            ["apt-mark", "showmanual"], capture_output=True, text=True, timeout=30
        )
        self.manual_packages = set(result.stdout.strip().split("\n"))
        self.log(f"Found {len(self.manual_packages)} manually installed packages")

    def is_preinstalled(self, pkg: str) -> bool:
        """Check if package is pre-installed"""
        # Check against mint list
        if pkg in self.mint_preinstalled:
            return True

        # Check patterns
        if is_preinstalled_pattern(pkg):
            return True

        return False

    def scan_apt_packages(self) -> List[Application]:
        """Scan APT packages"""
        apps = []

        self.load_package_lists()

        self.progress(20, "Analyzing packages...")

        # Process manual packages
        manual_list = sorted(self.manual_packages)
        total = len(manual_list)

        kept = 0
        skipped_preinstalled = 0

        for i, pkg in enumerate(manual_list):
            if not pkg:
                continue

            # Progress
            if i % 100 == 0:
                percent = 20 + int((i / total) * 30)
                self.progress(percent, f"Processing {i}/{total}: {pkg}")

            # Check if pre-installed
            if self.is_preinstalled(pkg):
                # Check if it has user configs (then we keep it for config backup)
                has_config, config_paths = has_user_config(pkg)

                if has_config:
                    self.log(f"  [CONFIG] {pkg}: Pre-installed but has user configs")

                    # Get package info
                    try:
                        result = subprocess.run(
                            [
                                "dpkg-query",
                                "-W",
                                "-f=${binary:Summary}|${Version}",
                                pkg,
                            ],
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

                    app = Application(
                        name=pkg,
                        display_name=pkg.replace("-", " ").title(),
                        description=(
                            desc + " [config only]" if desc else "[config only]"
                        ),
                        install_method="apt",
                        install_source=pkg,
                        version=version,
                        category="System (Config Only)",
                        config_paths=config_paths,
                        is_preinstalled=True,
                        selected=True,
                    )
                    apps.append(app)
                    kept += 1
                else:
                    skipped_preinstalled += 1

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
            kept += 1

        self.log(f"")
        self.log(f"Results:")
        self.log(f"  Kept {kept} user packages")
        self.log(f"  Skipped {skipped_preinstalled} pre-installed (no configs)")

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
            ],
            "Media": ["gimp", "kdenlive", "vlc", "mpv", "obs", "davinci", "resolve"],
            "Communication": ["slack", "telegram", "discord", "thunderbird"],
            "Browser": ["firefox", "chrome", "chromium", "vivaldi", "brave"],
            "System": ["htop", "neofetch", "conky"],
            "Gaming": ["steam", "lutris", "wine"],
            "Productivity": ["obsidian", "libreoffice"],
            "Security": ["tailscale", "zerotier"],
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


class FastSystemScanner:
    """Main fast scanner"""

    def __init__(self):
        self.app_scanner = FastApplicationScanner()
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
                        if len(parts) >= 3:
                            url = parts[1]
                            key_file = None
                            if "signed-by=" in line:
                                match = re.search(r"signed-by=([^\s\]]+)", line)
                                if match:
                                    key_file = match.group(1)

                            repos.append(
                                Repository(
                                    type="apt", name=f.stem, url=url, key_file=key_file
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
        self.log("Linux Mint Migration Tool - Fast Scanner")
        self.log("=" * 60)
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


# Backwards compatibility
Application = Application
Service = Service
VMConfig = VMConfig
Repository = Repository
SystemScanner = FastSystemScanner
VerboseSystemScanner = FastSystemScanner


if __name__ == "__main__":
    print("Testing Fast Scanner...")
    print("=" * 60)

    scanner = FastSystemScanner()

    def log(msg):
        print(msg)

    def progress(pct, msg):
        print(f"[{pct:3d}%] {msg}")

    scanner.set_callbacks(progress, log)
    result = scanner.scan_all()

    output_file = Path.home() / "scan_result_fast.json"
    output_file.write_text(json.dumps(result, indent=2))
    print(f"\n✓ Saved to: {output_file}")
