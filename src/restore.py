#!/usr/bin/env python3
"""
Restore Module - Restores applications and configurations from migration package
Handles apt packages, flatpak apps, configs, repositories, and services
"""

import os
import base64
import json
import shutil
import tarfile
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

try:
    from .config_backup import ConfigBackup
except ImportError:
    from config_backup import ConfigBackup


@dataclass
class RestoreResult:
    """Result of a restore operation"""

    success: bool
    installed_apps: List[str] = field(default_factory=list)
    failed_apps: List[Tuple[str, str]] = field(default_factory=list)
    restored_configs: List[str] = field(default_factory=list)
    failed_configs: List[Tuple[str, str]] = field(default_factory=list)
    added_repos: List[str] = field(default_factory=list)
    enabled_services: List[str] = field(default_factory=list)
    error_message: str = ""
    dry_run: bool = False
    staged_restore_root: Optional[str] = None


class AppRestorer:
    """Restores applications from migration package"""

    def __init__(self):
        self.progress_callback = None
        self.log_callback = None
        self.dry_run = False

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

    def _run_privileged(
        self, command: List[str], input_text: Optional[str] = None
    ) -> subprocess.CompletedProcess:
        runners = []
        if shutil.which("pkexec"):
            runners.append(["pkexec", *command])
        runners.append(["sudo", *command])

        last_error = None
        for runner in runners:
            try:
                result = subprocess.run(
                    runner,
                    input=input_text,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                return result
            except Exception as e:
                last_error = e

        raise RuntimeError(
            str(last_error) if last_error else "No privileged runner available"
        )

    def check_package_available(self, package_name: str, install_method: str) -> bool:
        """Check if a package is available in repositories"""
        try:
            if install_method == "apt":
                result = subprocess.run(
                    ["apt-cache", "search", "^" + package_name + "$"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return package_name in result.stdout
            elif install_method == "flatpak":
                result = subprocess.run(
                    ["flatpak", "search", package_name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return package_name in result.stdout
            return False
        except:
            return False

    def install_apt_package(self, package_name: str) -> Tuple[bool, str]:
        """Install an apt package"""
        if self.dry_run:
            return True, "[DRY-RUN] Would install"

        try:
            # Update package list first
            self.log(f"  Installing {package_name}...")

            result = self._run_privileged(["apt-get", "install", "-y", package_name])

            if result.returncode == 0:
                return True, "Installed successfully"
            else:
                return False, result.stderr[:200]
        except subprocess.TimeoutExpired:
            return False, "Installation timed out"
        except Exception as e:
            return False, str(e)

    def install_flatpak(self, app_id: str) -> Tuple[bool, str]:
        """Install a flatpak application"""
        if self.dry_run:
            return True, "[DRY-RUN] Would install"

        try:
            self.log(f"  Installing flatpak {app_id}...")

            result = subprocess.run(
                ["flatpak", "install", "-y", "flathub", app_id],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                return True, "Installed successfully"
            else:
                return False, result.stderr[:200]
        except subprocess.TimeoutExpired:
            return False, "Installation timed out"
        except Exception as e:
            return False, str(e)

    def add_repository(self, repo: Dict) -> Tuple[bool, str]:
        """Add a repository to the system"""
        if self.dry_run:
            return True, "[DRY-RUN] Would add repository"

        try:
            repo_type = repo.get("type", "apt")

            if repo_type == "apt":
                # Check if already exists
                repo_file = Path(f"/etc/apt/sources.list.d/{repo['name']}.list")
                if repo_file.exists():
                    return True, "Repository already exists"

                self.log(f"  Adding repository: {repo['name']}")

                repo_line = repo.get("source_line", "").strip()
                if not repo_line:
                    suite = repo.get("suite") or repo.get("codename")
                    components = repo.get("components", [])
                    if not repo.get("url") or not suite:
                        return False, "Repository data incomplete for restore"
                    repo_line = (
                        f"deb {repo['url']} {suite} {' '.join(components)}".strip()
                    )

                key_file = repo.get("key_file")
                key_content = repo.get("key_file_content_base64")
                if key_file and key_content:
                    key_bytes = base64.b64decode(key_content)
                    with tempfile.NamedTemporaryFile(delete=False) as temp_key:
                        temp_key.write(key_bytes)
                        temp_key_path = temp_key.name
                    try:
                        self._run_privileged(
                            ["mkdir", "-p", str(Path(key_file).parent)]
                        )
                        install_key = self._run_privileged(
                            ["install", "-m", "644", temp_key_path, key_file]
                        )
                        if install_key.returncode != 0:
                            return False, install_key.stderr[:200]
                    finally:
                        Path(temp_key_path).unlink(missing_ok=True)
                elif key_file and not Path(key_file).exists():
                    return False, f"Repository key missing for {repo['name']}"

                with tempfile.NamedTemporaryFile("w", delete=False) as temp_repo:
                    temp_repo.write(repo_line + "\n")
                    temp_repo_path = temp_repo.name
                try:
                    install_repo = self._run_privileged(
                        ["install", "-m", "644", temp_repo_path, str(repo_file)]
                    )
                    if install_repo.returncode != 0:
                        return False, install_repo.stderr[:200]
                finally:
                    Path(temp_repo_path).unlink(missing_ok=True)

                # Update apt
                update_result = self._run_privileged(["apt-get", "update"])
                if update_result.returncode != 0:
                    return False, update_result.stderr[:200]

                return True, "Repository added"

            elif repo_type == "flatpak":
                # Check if remote exists
                result = subprocess.run(
                    ["flatpak", "remotes"], capture_output=True, text=True
                )

                if repo["name"] in result.stdout:
                    return True, "Remote already exists"

                self.log(f"  Adding flatpak remote: {repo['name']}")

                result = subprocess.run(
                    [
                        "flatpak",
                        "remote-add",
                        "--if-not-exists",
                        repo["name"],
                        repo["url"],
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode == 0:
                    return True, "Remote added"
                else:
                    return False, result.stderr[:200]

            return False, f"Unknown repository type: {repo_type}"

        except Exception as e:
            return False, str(e)

    def enable_service(self, service_name: str) -> Tuple[bool, str]:
        """Enable and start a systemd service"""
        if self.dry_run:
            return True, "[DRY-RUN] Would enable service"

        try:
            self.log(f"  Enabling service: {service_name}")

            # Enable service
            result = self._run_privileged(["systemctl", "enable", service_name])

            if result.returncode != 0:
                return False, result.stderr[:200]

            # Start service
            result = self._run_privileged(["systemctl", "start", service_name])

            if result.returncode == 0:
                return True, "Service enabled and started"
            else:
                return True, "Service enabled (start failed)"

        except Exception as e:
            return False, str(e)


class MigrationRestorer:
    """Main class for restoring from migration package"""

    def __init__(self):
        self.app_restorer = AppRestorer()
        self.progress_callback = None
        self.log_callback = None
        self.dry_run = False

    def set_callbacks(self, progress_callback=None, log_callback=None, dry_run=False):
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.dry_run = dry_run
        self.app_restorer.set_callbacks(progress_callback, log_callback)
        self.app_restorer.dry_run = dry_run

    def log(self, message: str):
        if self.log_callback:
            self.log_callback(message)

    def progress(self, percent: int, message: str):
        if self.progress_callback:
            self.progress_callback(percent, message)
        self.log(message)

    def _find_config_archive(self, package_path: Path, data: Dict) -> Optional[Path]:
        candidates: List[Path] = []

        if data.get("config_archive_name"):
            candidates.append(package_path.parent / data["config_archive_name"])

        candidates.append(package_path.parent / f"{package_path.stem}_configs.tar.gz")

        for pattern in ("mint_configs_*.tar.gz", "mint_migration_configs_*.tar.gz"):
            candidates.extend(
                sorted(
                    package_path.parent.glob(pattern),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
            )

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def load_migration_package(self, package_path: Path) -> Optional[Dict]:
        """Load and validate migration package"""
        try:
            self.progress(0, "Loading migration package...")

            if not package_path.exists():
                self.log(f"✗ Package not found: {package_path}")
                return None

            with open(package_path, "r") as f:
                data = json.load(f)

            # Validate required fields
            if "applications" not in data:
                self.log("✗ Invalid package: missing applications")
                return None

            self.log(f"✓ Loaded package from: {package_path}")
            self.log(f"  Created: {data.get('export_date', 'unknown')}")
            self.log(f"  Applications: {len(data.get('applications', []))}")
            self.log(f"  Repositories: {len(data.get('repositories', []))}")
            self.log(f"  Services: {len(data.get('services', []))}")

            return data

        except json.JSONDecodeError as e:
            self.log(f"✗ Invalid JSON: {e}")
            return None
        except Exception as e:
            self.log(f"✗ Error loading package: {e}")
            return None

    def restore(
        self,
        package_path: Path,
        selected_apps: Optional[List[str]] = None,
        install_apps: bool = True,
        restore_configs: bool = True,
        add_repos: bool = True,
        enable_services: bool = True,
        staged_restore_root: Optional[Path] = None,
    ) -> RestoreResult:
        """
        Restore from migration package

        Args:
            package_path: Path to the JSON migration package
            selected_apps: List of app names to restore (None = all)
            install_apps: Whether to install applications
            restore_configs: Whether to restore configs from companion archive
            add_repos: Whether to add repositories
            enable_services: Whether to enable services

        Returns:
            RestoreResult with details of the operation
        """
        result = RestoreResult(
            success=False,
            dry_run=self.dry_run,
            staged_restore_root=str(staged_restore_root)
            if staged_restore_root
            else None,
        )

        try:
            # Load package
            data = self.load_migration_package(package_path)
            if not data:
                result.error_message = "Failed to load migration package"
                return result

            mode_str = "[DRY-RUN] " if self.dry_run else ""
            self.log("")
            self.log(f"{mode_str}Starting restoration...")
            self.log("=" * 60)

            if staged_restore_root:
                install_apps = False
                add_repos = False
                enable_services = False
                self.log(
                    f"Staged restore mode: restoring configs into {staged_restore_root}"
                )
                self.log("System changes are disabled in staged restore mode")

            # Add repositories first
            if add_repos and data.get("repositories"):
                self.progress(5, "Adding repositories...")
                repos = data["repositories"]

                for i, repo in enumerate(repos):
                    success, msg = self.app_restorer.add_repository(repo)
                    if success:
                        result.added_repos.append(repo.get("name", "unknown"))
                        self.log(f"  ✓ {repo.get('name', 'unknown')}")
                    else:
                        self.log(f"  ⚠ {repo.get('name', 'unknown')}: {msg}")

                self.log(f"Added {len(result.added_repos)}/{len(repos)} repositories")

            # Install applications
            if install_apps and data.get("applications"):
                apps = data["applications"]

                # Filter selected apps if specified
                if selected_apps:
                    apps = [a for a in apps if a.get("name") in selected_apps]

                total_apps = len(apps)
                self.log("")
                self.log(f"Installing {total_apps} applications...")

                if total_apps == 0:
                    self.log("No applications selected for restore")

                for i, app in enumerate(apps):
                    if not app.get("selected", True):
                        continue

                    app_name = app.get("name", "unknown")
                    install_method = app.get("install_method", "apt")
                    install_source = app.get("install_source", app_name)

                    progress_pct = 10 + int((i / total_apps) * 60)
                    self.progress(progress_pct, f"Installing {app_name}...")

                    # Check if already installed
                    if install_method == "apt":
                        check = subprocess.run(
                            ["dpkg", "-l", app_name], capture_output=True, text=True
                        )
                        if check.returncode == 0 and "ii" in check.stdout:
                            self.log(f"  ✓ {app_name} already installed")
                            result.installed_apps.append(app_name)
                            continue
                    elif install_method == "flatpak":
                        check = subprocess.run(
                            ["flatpak", "list", "--app"], capture_output=True, text=True
                        )
                        if install_source in check.stdout:
                            self.log(f"  ✓ {app_name} already installed")
                            result.installed_apps.append(app_name)
                            continue

                    # Install
                    if install_method == "apt":
                        success, msg = self.app_restorer.install_apt_package(app_name)
                    elif install_method == "flatpak":
                        success, msg = self.app_restorer.install_flatpak(install_source)
                    else:
                        success = False
                        msg = f"Unknown install method: {install_method}"

                    if success:
                        result.installed_apps.append(app_name)
                        self.log(f"  ✓ {app_name}")
                    else:
                        result.failed_apps.append((app_name, msg))
                        self.log(f"  ✗ {app_name}: {msg}")

                self.log(f"")
                self.log(
                    f"Installed: {len(result.installed_apps)}, Failed: {len(result.failed_apps)}"
                )

            # Restore configs
            if restore_configs:
                self.progress(75, "Restoring configurations...")

                # Look for companion config archive
                config_archive = self._find_config_archive(package_path, data)

                if config_archive and config_archive.exists():
                    self.log(f"Found config archive: {config_archive.name}")

                    backup = ConfigBackup()
                    backup.set_callbacks(self.progress_callback, self.log_callback)

                    config_result = backup.restore_configs(
                        config_archive,
                        dry_run=self.dry_run,
                        selected_apps=selected_apps,
                        restore_root=staged_restore_root,
                    )

                    result.restored_configs = config_result.backed_up_files
                    result.failed_configs = config_result.failed_files

                    if config_result.success:
                        self.log(
                            f"✓ Restored {len(result.restored_configs)} config files"
                        )
                    else:
                        self.log(
                            f"⚠ Config restore had issues: {config_result.error_message}"
                        )
                else:
                    self.log("No config archive found (optional)")

            # Enable services
            if enable_services and data.get("services"):
                self.progress(90, "Enabling services...")
                services = data["services"]

                self.log("")
                self.log(f"Enabling {len(services)} services...")

                for svc in services:
                    if not svc.get("selected", True):
                        continue

                    svc_name = svc.get("name", "")
                    if svc_name:
                        success, msg = self.app_restorer.enable_service(svc_name)
                        if success:
                            result.enabled_services.append(svc_name)
                            self.log(f"  ✓ {svc_name}")
                        else:
                            self.log(f"  ⚠ {svc_name}: {msg}")

                self.log(f"Enabled {len(result.enabled_services)} services")

            # Complete
            self.progress(100, "Restore complete!")
            self.log("")
            self.log("=" * 60)
            self.log(f"{mode_str}Restore Summary:")
            self.log(f"  Applications: {len(result.installed_apps)} installed")
            self.log(f"  Repositories: {len(result.added_repos)} added")
            self.log(f"  Configs: {len(result.restored_configs)} restored")
            self.log(f"  Services: {len(result.enabled_services)} enabled")

            if result.failed_apps:
                self.log(f"  Failed apps: {len(result.failed_apps)}")

            result.success = True
            return result

        except Exception as e:
            result.error_message = str(e)
            self.log(f"✗ Restore failed: {e}")
            return result


if __name__ == "__main__":
    # Test the restore module
    print("Testing Restore Module...")
    print("=" * 60)

    restorer = MigrationRestorer()

    def log(msg):
        print(msg)

    def progress(pct, msg):
        print(f"[{pct:3d}%] {msg}")

    restorer.set_callbacks(progress, log, dry_run=True)

    # Test loading a package
    test_package = Path.home() / "mint-migration.json"
    if test_package.exists():
        result = restorer.restore(test_package)

        if result.success:
            print(f"\n✓ Restore test completed!")
            print(f"  Would install: {len(result.installed_apps)} apps")
            print(f"  Would add: {len(result.added_repos)} repos")
            print(f"  Would restore: {len(result.restored_configs)} configs")
        else:
            print(f"\n✗ Restore test failed: {result.error_message}")
    else:
        print(f"\n⚠ No test package found at {test_package}")
        print("Create a migration package first to test restore.")
