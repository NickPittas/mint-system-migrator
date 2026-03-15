#!/usr/bin/env python3
"""
Config Backup Module - Backs up ONLY user configuration files
Uses config_discovery to find actual config files per app
"""

import os
import json
import shutil
import tarfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

try:
    from .config_discovery import SmartConfigDiscovery
except ImportError:
    from config_discovery import SmartConfigDiscovery


@dataclass
class ConfigBackupResult:
    """Result of a config backup operation"""

    success: bool
    backed_up_files: List[str] = field(default_factory=list)
    failed_files: List[Tuple[str, str]] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    total_size: int = 0
    archive_path: Optional[Path] = None
    error_message: str = ""
    apps_found: int = 0
    apps_without_configs: List[str] = field(default_factory=list)


class ConfigBackup:
    """Handles backing up user configuration files ONLY"""

    def __init__(self):
        self.progress_callback = None
        self.log_callback = None
        self.cancelled = False

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

    def cancel(self):
        """Cancel the backup operation"""
        self.cancelled = True
        self.log("Backup cancelled by user")

    def backup_configs(
        self,
        apps: List[dict],
        output_dir: Path,
        include_global: bool = True,
    ) -> ConfigBackupResult:
        """
        Backup configurations for selected applications

        Args:
            apps: List of application dicts with 'name' key
            output_dir: Directory to save backup archive
            include_global: Whether to include global configs (themes, fonts, etc.)

        Returns:
            ConfigBackupResult with backup details
        """
        result = ConfigBackupResult(success=False)
        self.cancelled = False

        backup_dir = None

        try:
            self.progress(0, "Discovering config files...")

            # Create discovery instance
            discovery = SmartConfigDiscovery()

            # Collect all config files per app
            all_configs: Dict[str, List[str]] = {}
            apps_without_configs = []

            for app in apps:
                if self.cancelled:
                    result.error_message = "Cancelled by user"
                    return result

                app_name = app.get("name", app.get("display_name", "")).lower()
                if not app_name:
                    continue

                # Discover configs for this app
                configs = discovery.discover_configs(app_name)

                if configs:
                    # configs is now list of (path, size) tuples
                    all_configs[app_name] = [c[0] for c in configs]
                    total_kb = sum(c[1] for c in configs) / 1024
                    self.log(
                        f"  {app_name}: {len(configs)} config files ({total_kb:.1f} KB)"
                    )
                else:
                    apps_without_configs.append(app_name)

            if include_global:
                self.progress(10, "Discovering global configs...")
                app_specific_paths = {
                    path for app_paths in all_configs.values() for path in app_paths
                }
                global_configs = [
                    path
                    for path, _ in discovery.get_global_configs()
                    if path not in app_specific_paths
                ]
                if global_configs:
                    all_configs["_global"] = global_configs
                    self.log(f"  Global: {len(global_configs)} files")

            result.apps_found = len(all_configs)
            result.apps_without_configs = apps_without_configs

            if not all_configs:
                result.error_message = "No configuration files found"
                self.log("⚠ No config files found for any selected apps")
                return result

            # Calculate total size first (for user info)
            total_size = 0
            for app_name, paths in all_configs.items():
                for path_str in paths:
                    path = Path(path_str)
                    if path.exists() and path.is_file():
                        try:
                            size = path.stat().st_size
                            # Warn if individual file is huge (might be a database or binary)
                            if size > 10 * 1024 * 1024:  # 10MB
                                self.log(
                                    f"  ⚠ Warning: Large file {path.name} ({self._format_size(size)})"
                                )
                            total_size += size
                        except:
                            pass

            self.log(f"")
            self.log(f"Total config size: {self._format_size(total_size)}")

            if total_size > 500 * 1024 * 1024:  # 500MB warning
                self.log(
                    f"⚠ WARNING: Configs are very large ({self._format_size(total_size)})"
                )
                self.log("  This might include databases or unintended files")

            # Create backup directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"mint_configs_{timestamp}"
            backup_dir = output_dir / backup_name
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Create metadata
            metadata = {
                "backup_date": datetime.now().isoformat(),
                "applications": list(all_configs.keys()),
                "total_apps": len(all_configs),
                "apps_without_configs": apps_without_configs,
                "config_paths_by_app": all_configs,
                "total_size_bytes": total_size,
                "version": "2.0",
            }

            metadata_path = backup_dir / "backup_manifest.json"
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            compatibility_metadata_path = backup_dir / "backup_metadata.json"
            with open(compatibility_metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            result.backed_up_files.append(str(metadata_path))

            # Copy config files
            total_files = sum(len(paths) for paths in all_configs.values())
            current_file = 0

            for app_name, paths in all_configs.items():
                if self.cancelled:
                    result.error_message = "Cancelled by user"
                    # Cleanup
                    if backup_dir.exists():
                        shutil.rmtree(backup_dir)
                    return result

                self.progress(
                    int(20 + (current_file / total_files) * 60),
                    f"Backing up {app_name}...",
                )

                # Create app-specific directory
                app_backup_dir = backup_dir / app_name
                app_backup_dir.mkdir(exist_ok=True)

                for src_path_str in paths:
                    src_path = Path(src_path_str)

                    try:
                        if not src_path.exists():
                            result.skipped_files.append(str(src_path))
                            continue

                        # SECURITY CHECK: Only backup files, never directories
                        if not src_path.is_file():
                            self.log(f"    ⚠ Skipping directory: {src_path.name}")
                            result.skipped_files.append(str(src_path))
                            continue

                        # SECURITY CHECK: Skip files that are too large (likely databases/binaries)
                        file_size = src_path.stat().st_size
                        if file_size > 50 * 1024 * 1024:  # 50MB
                            self.log(
                                f"    ⚠ Skipping large file: {src_path.name} ({self._format_size(file_size)})"
                            )
                            result.skipped_files.append(str(src_path))
                            continue

                        # Calculate relative path to preserve structure
                        try:
                            rel_path = src_path.relative_to(Path.home())
                        except ValueError:
                            # Path not under home, use filename only
                            rel_path = Path(src_path.name)

                        dest_path = app_backup_dir / rel_path
                        dest_path.parent.mkdir(parents=True, exist_ok=True)

                        # Copy the file
                        shutil.copy2(src_path, dest_path)
                        result.backed_up_files.append(str(src_path))
                        result.total_size += file_size

                    except (PermissionError, OSError, shutil.Error) as e:
                        result.failed_files.append((str(src_path), str(e)))
                        self.log(f"    ✗ {src_path.name} - {e}")

                current_file += len(paths)

            # Create tarball
            self.progress(85, "Creating archive...")
            archive_path = output_dir / f"{backup_name}.tar.gz"

            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(backup_dir, arcname=backup_name)

            # Clean up temp directory
            shutil.rmtree(backup_dir)

            result.archive_path = archive_path
            result.success = True

            self.progress(100, "Backup complete!")
            self.log(f"")
            self.log(f"✓ Archive created: {archive_path}")
            self.log(f"✓ Total size: {self._format_size(result.total_size)}")
            self.log(f"✓ Files backed up: {len(result.backed_up_files)}")

            if result.skipped_files:
                self.log(f"⚠ Skipped: {len(result.skipped_files)}")
            if result.failed_files:
                self.log(f"✗ Failed: {len(result.failed_files)}")
            if apps_without_configs:
                self.log(f"ℹ Apps without configs: {', '.join(apps_without_configs)}")

            return result

        except Exception as e:
            result.error_message = str(e)
            self.log(f"✗ Backup failed: {e}")
            # Cleanup on error
            try:
                if backup_dir and backup_dir.exists():
                    shutil.rmtree(backup_dir)
            except:
                pass
            return result

    def _format_size(self, size_bytes: int) -> str:
        """Format bytes to human readable string"""
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


if __name__ == "__main__":
    # Test the backup module
    print("Testing Config Backup Module...")
    print("=" * 60)

    backup = ConfigBackup()

    def log(msg):
        print(msg)

    def progress(pct, msg):
        print(f"[{pct:3d}%] {msg}")

    backup.set_callbacks(progress, log)

    # Test with some sample apps
    test_apps = [{"name": "git"}, {"name": "bash"}, {"name": "vim"}]

    result = backup.backup_configs(
        apps=test_apps,
        output_dir=Path.home() / "test_backup_output",
        include_global=False,
    )

    if result.success:
        print(f"\n✓ Backup successful!")
        print(f"  Archive: {result.archive_path}")
        print(f"  Size: {backup._format_size(result.total_size)}")
        print(f"  Files: {len(result.backed_up_files)}")
        print(f"  Apps found: {result.apps_found}")
        if result.apps_without_configs:
            print(f"  Apps without configs: {result.apps_without_configs}")
    else:
        print(f"\n✗ Backup failed: {result.error_message}")
