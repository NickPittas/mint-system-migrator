#!/usr/bin/env python3
"""
Phase 1b: Enhanced Scanner with Pre-installed Package Detection
Filters out default Mint packages unless they have user configs
"""

import subprocess
import json
import hashlib
from pathlib import Path
from typing import Set, List, Dict, Optional, Tuple
from dataclasses import dataclass, field

# Import the original scanner
import scanner


@dataclass
class PreinstalledPackage:
    """Tracks pre-installed packages and their configs"""

    name: str
    category: str  # 'core', 'desktop', 'utility', 'optional'
    has_config: bool = False
    config_paths: List[str] = field(default_factory=list)
    config_modified: bool = False


class MintPackageDatabase:
    """
    Comprehensive database of packages that come pre-installed with Linux Mint.
    These should be filtered out unless user has modified configs.
    """

    # Core system - absolutely never backup these
    CORE_SYSTEM = {
        "bash",
        "coreutils",
        "grep",
        "sed",
        "awk",
        "gawk",
        "mawk",
        "tar",
        "gzip",
        "bzip2",
        "xz-utils",
        "zip",
        "unzip",
        "mount",
        "util-linux",
        "findutils",
        "diffutils",
        "libc6",
        "libc-bin",
        "libgcc-s1",
        "libstdc++6",
        "sysvinit-utils",
        "init-system-helpers",
        "systemd",
        "systemd-sysv",
        "upstart",
        "dbus",
        "polkitd",
        "accountsservice",
        "login",
        "passwd",
        "adduser",
        "base-files",
        "base-passwd",
        "debianutils",
        "dpkg",
        "apt",
        "apt-utils",
        "apt-transport-https",
        "debconf",
        "ucf",
        "mime-support",
    }

    # Shell and terminal
    SHELLS = {
        "dash",
        "zsh",
        "fish",
        "tcsh",
        "csh",
        "ksh",
        "bash-completion",
        "command-not-found",
    }

    # Hardware and firmware
    HARDWARE = {
        "linux-image",
        "linux-headers",
        "linux-modules",
        "linux-firmware",
        "firmware-linux",
        "firmware-misc-nonfree",
        "firmware-amd-graphics",
        "firmware-realtek",
        "firmware-iwlwifi",
        "firmware-libertas",
        "firmware-ti-connectivity",
        "grub-pc",
        "grub-common",
        "grub2-common",
        "os-prober",
        "efibootmgr",
        "efivar",
        "mokutil",
        "shim-signed",
        "secureboot-db",
        "sbsigntool",
        "amd64-microcode",
        "intel-microcode",
        "iucode-tool",
    }

    # System libraries - never backup
    LIBRARIES = {
        "lib",  # All lib* packages
        "lib32",
        "lib64",
        "libx32",
    }

    # Desktop environment
    DESKTOP = {
        "mint-meta-cinnamon",
        "mint-meta-core",
        "mint-meta-codecs",
        "mint-common",
        "mint-info-cinnamon",
        "mint-themes",
        "mint-artwork",
        "cinnamon",
        "cinnamon-common",
        "cinnamon-control-center",
        "cinnamon-desktop-data",
        "cinnamon-screensaver",
        "cinnamon-session",
        "cinnamon-settings-daemon",
        "muffin",
        "nemo",
        "nemo-data",
        "cjs",
        "muffin-common",
        "gnome-keyring",
        "gnome-keyring-pkcs11",
        "mate-polkit",
        "mate-polkit-common",
        "xserver-xorg",
        "xserver-common",
        "xserver-xephyr",
        "x11-common",
        "x11-utils",
        "x11-xkb-utils",
        "x11-xserver-utils",
        "xinit",
        "xinput",
        "xauth",
        "xfonts-encodings",
        "xfonts-utils",
        "xfonts-base",
        "xfonts-scalable",
        "wayland",
        "wayland-protocols",
        "mesa-utils",
        "mesa-vulkan-drivers",
        "mesa-utils-bin",
        "libgl1-mesa-dri",
        "libglx-mesa0",
        "libegl-mesa0",
        "libgbm1",
    }

    # Desktop apps that come with Mint
    DEFAULT_APPS = {
        # Browsers
        "firefox",
        "firefox-locale-en",
        # Media
        "celluloid",
        "vlc",
        "vlc-bin",
        "vlc-data",
        "vlc-plugin-base",
        "rhythmbox",
        "rhythmbox-data",
        "rhythmbox-plugins",
        # Office
        "libreoffice-calc",
        "libreoffice-core",
        "libreoffice-gtk3",
        "libreoffice-impress",
        "libreoffice-writer",
        "libreoffice-common",
        "libreoffice-style-elementary",
        "libreoffice-style-colibre",
        # Graphics
        "drawing",
        "pix",
        "pix-dbg",
        "gthumb",
        "gthumb-data",
        # Utils
        "xed",
        "xreader",
        "xviewer",
        "xplayer",
        "warpinator",
        "webapp-manager",
        "sticky",
        "hypnotix",
        "simple-scan",
        "thingy",
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
        # Settings
        "gnome-control-center",
        "gnome-settings-daemon",
        "cinnamon-control-center-data",
    }

    # Network and connectivity
    NETWORK = {
        "network-manager",
        "network-manager-gnome",
        "network-manager-pptp",
        "network-manager-openvpn",
        "network-manager-openconnect",
        "wpasupplicant",
        "wireless-tools",
        "wireless-regdb",
        "iw",
        "rfkill",
        "ethtool",
        "net-tools",
        "iproute2",
        "iptables",
        "nftables",
        "ufw",
        "gufw",
        "avahi-daemon",
        "avahi-utils",
        "avahi-autoipd",
        "dnsmasq-base",
        "openresolv",
        "isc-dhcp-client",
        "bluez",
        "bluetooth",
        "blueman",
        "pulseaudio",
        "pulseaudio-utils",
        "pipewire",
        "pipewire-bin",
        "wireplumber",
        "alsa-utils",
        "alsa-base",
        "alsa-topology-conf",
        "alsa-ucm-conf",
    }

    # Printing
    PRINTING = {
        "cups",
        "cups-bsd",
        "cups-client",
        "cups-common",
        "cups-core-drivers",
        "cups-daemon",
        "cups-filters",
        "cups-filters-core-drivers",
        "cups-ipp-utils",
        "cups-pk-helper",
        "cups-ppdc",
        "printer-driver-brlaser",
        "printer-driver-c2esp",
        "printer-driver-gutenprint",
        "printer-driver-hpcups",
        "printer-driver-postscript-hp",
        "hplip",
        "hplip-data",
        "system-config-printer",
        "system-config-printer-common",
        "openprinting-ppds",
    }

    # Fonts and themes
    FONTS_THEMES = {
        "fonts-liberation",
        "fonts-liberation2",
        "fonts-dejavu",
        "fonts-dejavu-core",
        "fonts-dejavu-extra",
        "fonts-freefont-ttf",
        "fonts-noto",
        "fonts-noto-color-emoji",
        "fonts-noto-core",
        "fonts-noto-mono",
        "fonts-ubuntu",
        "fonts-opensymbol",
        "fonts-mathjax",
        "hicolor-icon-theme",
        "adwaita-icon-theme",
        "adwaita-icon-theme-full",
        "ubuntu-mono",
        "yaru-theme-icon",
        "mint-cursor-themes",
        "mint-backgrounds-wallpapers",
        "dmz-cursor-theme",
        "materia-gtk-theme",
        "gtk2-engines-murrine",
        "gtk2-engines-pixbuf",
    }

    # Python/Perl/System libraries
    INTERPRETERS = {
        "python3",
        "python3-minimal",
        "python3.10",
        "python3.10-minimal",
        "python3.11",
        "python3.11-minimal",
        "python3.12",
        "python3.12-minimal",
        "libpython3",
        "libpython3-stdlib",
        "libpython3-minimal",
        "perl",
        "perl-base",
        "perl-modules",
    }

    # Security and crypto
    SECURITY = {
        "openssl",
        "ca-certificates",
        "ca-certificates-java",
        "gnupg",
        "gnupg-utils",
        "gpg",
        "gpg-agent",
        "gpgconf",
        "gpgv",
        "libnss3",
        "libssl3",
        "libgnutls30",
        "apparmor",
        "apparmor-utils",
        "libapparmor1",
        "cryptsetup",
        "cryptsetup-bin",
        "cryptsetup-initramfs",
        "keyutils",
        "libkeyutils1",
    }

    # Build tools (not usually user-installed)
    BUILD_TOOLS = {
        "gcc",
        "gcc-11",
        "gcc-12",
        "gcc-13",
        "gcc-14",
        "g++",
        "g++-11",
        "g++-12",
        "g++-13",
        "g++-14",
        "cpp",
        "cpp-11",
        "cpp-12",
        "cpp-13",
        "cpp-14",
        "binutils",
        "binutils-common",
        "binutils-x86-64-linux-gnu",
        "libc6-dev",
        "libc-dev-bin",
        "linux-libc-dev",
        "make",
        "cmake",
        "automake",
        "autoconf",
        "libtool",
        "pkg-config",
        "pkgconf",
        "pkgconf-bin",
    }

    # Archive and compression
    ARCHIVE = {
        "tar",
        "gzip",
        "bzip2",
        "xz-utils",
        "lz4",
        "zstd",
        "zip",
        "unzip",
        "unrar",
        "p7zip",
        "p7zip-full",
    }

    @classmethod
    def get_all_preinstalled(cls) -> Set[str]:
        """Get complete set of pre-installed package names"""
        all_packages = set()

        all_packages.update(cls.CORE_SYSTEM)
        all_packages.update(cls.SHELLS)
        all_packages.update(cls.HARDWARE)
        all_packages.update(cls.DESKTOP)
        all_packages.update(cls.DEFAULT_APPS)
        all_packages.update(cls.NETWORK)
        all_packages.update(cls.PRINTING)
        all_packages.update(cls.FONTS_THEMES)
        all_packages.update(cls.INTERPRETERS)
        all_packages.update(cls.SECURITY)
        all_packages.update(cls.BUILD_TOOLS)
        all_packages.update(cls.ARCHIVE)

        return all_packages

    @classmethod
    def is_preinstalled(cls, package_name: str) -> bool:
        """Check if a package is pre-installed with Mint"""
        # Direct match
        if package_name in cls.get_all_preinstalled():
            return True

        # Library packages (lib*)
        if package_name.startswith("lib"):
            return True

        # Linux kernel packages
        if any(
            package_name.startswith(p)
            for p in ["linux-image", "linux-headers", "linux-modules"]
        ):
            return True

        # Firmware packages
        if package_name.startswith("firmware-"):
            return True

        # Font packages
        if package_name.startswith("fonts-"):
            return True

        # Python packages (python3-* modules, not the main python3)
        if package_name.startswith("python3-") and package_name not in ["python3-pip"]:
            # Check if it's a standard library module or common pre-installed
            python_modules = {
                "python3-apport",
                "python3-aptdaemon",
                "python3-aptdaemon.gtk3widgets",
                "python3-blinker",
                "python3-cairo",
                "python3-certifi",
                "python3-chardet",
                "python3-click",
                "python3-colorama",
                "python3-commandnotfound",
                "python3-cryptography",
                "python3-cups",
                "python3-cupshelpers",
                "python3-dbus",
                "python3-debian",
                "python3-defer",
                "python3-distutils",
                "python3-gdbm",
                "python3-gi",
                "python3-gi-cairo",
                "python3-httplib2",
                "python3-ibus",
                "python3-idna",
                "python3-jinja2",
                "python3-json-pointer",
                "python3-jsonpatch",
                "python3-jsonschema",
                "python3-jwt",
                "python3-keyring",
                "python3-launchpadlib",
                "python3-lazr.restfulclient",
                "python3-lazr.uri",
                "python3-ldb",
                "python3-louis",
                "python3-lxml",
                "python3-macaroonbakery",
                "python3-markupsafe",
                "python3-nacl",
                "python3-netifaces",
                "python3-oauthlib",
                "python3-olefile",
                "python3-pam",
                "python3-pexpect",
                "python3-pil",
                "python3-problem-report",
                "python3-protobuf",
                "python3-psutil",
                "python3-ptyprocess",
                "python3-pyatspi",
                "python3-pycurl",
                "python3-pymacaroons",
                "python3-pyqt5",
                "python3-pyqt5.sip",
                "python3-renderpm",
                "python3-reportlab",
                "python3-reportlab-accel",
                "python3-requests",
                "python3-rfc3339",
                "python3-secretstorage",
                "python3-simplejson",
                "python3-six",
                "python3-systemd",
                "python3-talloc",
                "python3-tdb",
                "python3-tz",
                "python3-uno",
                "python3-urllib3",
                "python3-wadllib",
                "python3-xdg",
                "python3-xkit",
                "python3-yaml",
                "python3-zeitgeist",
                "python3-zipp",
            }
            if package_name in python_modules:
                return True

        # Perl modules
        if package_name.startswith("lib") and "-perl" in package_name:
            return True

        # GObject introspection
        if package_name.startswith("gir1.2-"):
            return True

        # GStreamer plugins
        if package_name.startswith("gstreamer"):
            return True

        # ISO codes
        if "iso-codes" in package_name:
            return True

        return False


class ConfigDetector:
    """Detects if user has modified configs for a package"""

    # Known config paths for common packages
    KNOWN_CONFIGS = {
        "bash": ["~/.bashrc", "~/.bash_profile", "~/.bash_aliases", "~/.bash_logout"],
        "zsh": [
            "~/.zshrc",
            "~/.zprofile",
            "~/.zshenv",
            "~/.zsh_aliases",
            "~/.oh-my-zsh",
        ],
        "fish": ["~/.config/fish/config.fish", "~/.config/fish/functions"],
        "vim": ["~/.vimrc", "~/.vim"],
        "neovim": ["~/.config/nvim", "~/.nvimrc"],
        "git": ["~/.gitconfig", "~/.gitignore_global", "~/.git-credentials"],
        "ssh": ["~/.ssh/config", "~/.ssh/authorized_keys", "~/.ssh/known_hosts"],
        "gnupg": ["~/.gnupg/gpg.conf", "~/.gnupg/gpg-agent.conf"],
        "tmux": ["~/.tmux.conf"],
        "screen": ["~/.screenrc"],
        "wget": ["~/.wgetrc"],
        "curl": ["~/.curlrc"],
        "npm": ["~/.npmrc"],
        "pip": ["~/.pip/pip.conf", "~/.config/pip/pip.conf"],
        "docker": ["~/.docker/config.json"],
        "alacritty": [
            "~/.config/alacritty/alacritty.yml",
            "~/.config/alacritty/alacritty.toml",
        ],
        "kitty": ["~/.config/kitty/kitty.conf", "~/.kitty.conf"],
        "conky": ["~/.conkyrc", "~/.config/conky"],
    }

    @classmethod
    def has_user_config(cls, package_name: str) -> Tuple[bool, List[str]]:
        """
        Check if a package has user-modified configuration.
        Returns (has_config, list_of_config_paths)
        """
        config_paths = []

        # Check known configs
        if package_name in cls.KNOWN_CONFIGS:
            for path in cls.KNOWN_CONFIGS[package_name]:
                expanded = Path(path).expanduser()
                if expanded.exists():
                    config_paths.append(str(expanded))

        # Check standard XDG paths
        xdg_configs = [
            Path.home() / ".config" / package_name,
            Path.home() / ".config" / package_name.replace("-", "_"),
            Path.home() / f".{package_name}",
            Path.home() / f".{package_name}rc",
            Path.home() / f".{package_name}.conf",
        ]

        for path in xdg_configs:
            if path.exists():
                config_paths.append(str(path))

        # Remove duplicates while preserving order
        seen = set()
        unique_paths = []
        for path in config_paths:
            if path not in seen:
                seen.add(path)
                unique_paths.append(path)

        return len(unique_paths) > 0, unique_paths

    @classmethod
    def is_config_modified(cls, package_name: str, config_path: str) -> bool:
        """
        Check if a config file has been modified from default.
        This is complex - for now, we assume any existing user config is modified.
        """
        # Future enhancement: Compare against distro defaults
        # For now, if it exists in user's home, it's considered modified
        return Path(config_path).expanduser().exists()


class EnhancedApplicationScanner(scanner.ApplicationScanner):
    """Enhanced scanner that filters pre-installed packages intelligently"""

    def __init__(self):
        super().__init__()
        self.preinstalled_db = MintPackageDatabase()
        self.config_detector = ConfigDetector()
        self.preinstalled_with_configs = []  # Track these separately

    def scan_apt_packages(self) -> List[scanner.Application]:
        """Scan APT packages with intelligent filtering"""
        apps = []
        self.preinstalled_with_configs = []

        result = subprocess.run(
            ["apt-mark", "showmanual"], capture_output=True, text=True, timeout=30
        )

        # Get all manual packages
        all_manual = result.stdout.strip().split("\n")

        print(f"Total manually installed packages: {len(all_manual)}")
        print("Filtering pre-installed packages...")

        for pkg in all_manual:
            pkg = pkg.strip()
            if not pkg:
                continue

            # Check if pre-installed
            if self.preinstalled_db.is_preinstalled(pkg):
                # Check if user has modified configs
                has_config, config_paths = self.config_detector.has_user_config(pkg)

                if has_config:
                    # This is pre-installed but has user configs - track separately
                    print(f"  [CONFIG] {pkg} - has user configs")

                    # Get package info
                    pkg_info = subprocess.run(
                        ["dpkg-query", "-W", "-f=${binary:Summary}|${Version}", pkg],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )

                    if pkg_info.returncode == 0:
                        info_parts = pkg_info.stdout.split("|")
                        desc = info_parts[0][:100] if info_parts else ""
                        version = info_parts[1] if len(info_parts) > 1 else ""
                    else:
                        desc = ""
                        version = ""

                    app = scanner.Application(
                        name=pkg,
                        display_name=pkg.replace("-", " ").title(),
                        description=desc + " (config only)",
                        install_method="apt",
                        install_source=pkg,
                        version=version,
                        category="System (Config Only)",
                        config_paths=config_paths,
                        selected=True,
                    )
                    self.preinstalled_with_configs.append(app)
                else:
                    # Pre-installed, no user configs - skip entirely
                    pass

                continue

            # Not pre-installed - check if it's a dependency
            if self._has_reverse_dependencies(pkg, set(all_manual)):
                continue

            # Get package info
            pkg_info = subprocess.run(
                ["dpkg-query", "-W", "-f=${binary:Summary}|${Version}", pkg],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if pkg_info.returncode == 0:
                info_parts = pkg_info.stdout.split("|")
                desc = info_parts[0][:100] if info_parts else ""
                version = info_parts[1] if len(info_parts) > 1 else ""
            else:
                desc = ""
                version = ""

            # Check for configs
            has_config, config_paths = self.config_detector.has_user_config(pkg)

            # Categorize
            category = self._categorize_package(pkg, desc)

            app = scanner.Application(
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

        print(f"Found {len(apps)} user-installed packages")
        print(
            f"Found {len(self.preinstalled_with_configs)} pre-installed packages with configs"
        )

        # Add pre-installed with configs to the list
        apps.extend(self.preinstalled_with_configs)

        return apps


# Monkey-patch the scanner module
def create_enhanced_scanner():
    """Create enhanced scanner instance"""
    original_scanner = scanner.SystemScanner()
    original_scanner.app_scanner = EnhancedApplicationScanner()
    return original_scanner


# Export classes for use in GUI
Application = scanner.Application
Service = scanner.Service
VMConfig = scanner.VMConfig
Repository = scanner.Repository
SystemScanner = scanner.SystemScanner

if __name__ == "__main__":
    # Test the enhanced scanner
    print("Testing Enhanced Scanner...")
    print("=" * 60)

    test_scanner = create_enhanced_scanner()

    def progress(percent, message):
        print(f"[{percent:3d}%] {message}")

    result = test_scanner.scan_all(progress)

    print("\n" + "=" * 60)
    print("SCAN RESULTS")
    print("=" * 60)

    print(f"\nRepositories: {len(result['repositories'])}")

    print(f"\nApplications: {len(result['applications'])}")

    # Group by category
    categories = {}
    for app in result["applications"]:
        cat = app["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(app)

    for cat, apps in sorted(categories.items()):
        print(f"\n  {cat}: {len(apps)} apps")
        for app in apps[:3]:
            config_status = "✓ config" if app["config_paths"] else ""
            print(f"    - {app['name']} ({app['install_method']}) {config_status}")
        if len(apps) > 3:
            print(f"    ... and {len(apps) - 3} more")

    print(f"\nServices: {len(result['services'])}")
    for svc in result["services"]:
        status = "✓ active" if svc["active"] else "○ inactive"
        print(f"  - {svc['name']} ({svc['display_name']}) {status}")

    print(f"\nVMs: {len(result['vms'])}")

    # Save
    output_file = Path.home() / "scan_result_enhanced.json"
    output_file.write_text(json.dumps(result, indent=2))
    print(f"\n✓ Results saved to: {output_file}")
