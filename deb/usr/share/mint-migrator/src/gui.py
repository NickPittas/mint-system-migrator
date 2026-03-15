#!/usr/bin/env python3
"""
Phase 2: PyQt6 GUI Application
Modern native GUI for Linux Mint System Migration Tool
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QApplication,
    QHeaderView,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QCheckBox,
    QTextEdit,
    QProgressBar,
    QSplitter,
    QGroupBox,
    QMessageBox,
    QFileDialog,
    QStatusBar,
    QComboBox,
    QFrame,
    QScrollArea,
    QGridLayout,
    QStackedWidget,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QPalette

# Import scanner, backup, and restore modules
import scanner_whitelist as scanner
from config_backup import ConfigBackup
from restore import MigrationRestorer, RestoreResult


class ScannerThread(QThread):
    """Background thread for system scanning"""

    progress = pyqtSignal(int, str)
    log = pyqtSignal(str, str)
    finished_signal = pyqtSignal(bool, dict)

    def __init__(self):
        super().__init__()
        self.system_scanner = scanner.VerboseSystemScanner()

    def run(self):
        try:
            # Set up callbacks for verbose output
            self.system_scanner.set_callbacks(
                progress_callback=lambda pct, msg: self.progress.emit(pct, msg),
                log_callback=lambda msg: self.log.emit(msg, "info"),
            )

            result = self.system_scanner.scan_all()
            self.finished_signal.emit(True, result)
        except Exception as e:
            self.log.emit(f"Error: {str(e)}", "error")
            self.finished_signal.emit(False, {})


class InstallThread(QThread):
    """Background thread for installation"""

    progress = pyqtSignal(int, str)
    log = pyqtSignal(str, str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, migration_file: Path):
        super().__init__()
        self.migration_file = migration_file

    def run(self):
        # TODO: Implement installation logic
        self.log.emit("Installation not yet implemented", "warning")
        self.finished_signal.emit(True, "Installation would happen here")


class ConfigBackupThread(QThread):
    """Background thread for config backup"""

    progress = pyqtSignal(int, str)
    log = pyqtSignal(str, str)
    finished_signal = pyqtSignal(bool, object)

    def __init__(self, apps: list, output_dir: Path, include_global: bool = True):
        super().__init__()
        self.apps = apps
        self.output_dir = output_dir
        self.include_global = include_global
        self.backup = ConfigBackup()

    def cancel(self):
        """Cancel the backup operation"""
        if self.backup:
            self.backup.cancel()

    def run(self):
        try:
            self.backup.set_callbacks(
                progress_callback=lambda pct, msg: self.progress.emit(pct, msg),
                log_callback=lambda msg: self.log.emit(msg, "info"),
            )

            result = self.backup.backup_configs(
                apps=self.apps,
                output_dir=self.output_dir,
                include_global=self.include_global,
            )
            self.finished_signal.emit(result.success, result)
        except Exception as e:
            self.log.emit(f"Error: {str(e)}", "error")
            self.finished_signal.emit(False, None)


class RestoreThread(QThread):
    """Background thread for restoring migration package"""

    progress = pyqtSignal(int, str)
    log = pyqtSignal(str, str)
    finished_signal = pyqtSignal(bool, object)

    def __init__(
        self,
        package_path: Path,
        selected_apps: list = None,
        dry_run: bool = False,
        staged_restore_root: Path | None = None,
    ):
        super().__init__()
        self.package_path = package_path
        self.selected_apps = selected_apps
        self.dry_run = dry_run
        self.staged_restore_root = staged_restore_root
        self.restorer = None

    def run(self):
        try:
            from restore import MigrationRestorer

            self.restorer = MigrationRestorer()
            self.restorer.set_callbacks(
                progress_callback=lambda pct, msg: self.progress.emit(pct, msg),
                log_callback=lambda msg: self.log.emit(msg, "info"),
                dry_run=self.dry_run,
            )

            result = self.restorer.restore(
                package_path=self.package_path,
                selected_apps=self.selected_apps,
                staged_restore_root=self.staged_restore_root,
            )
            self.finished_signal.emit(result.success, result)
        except Exception as e:
            self.log.emit(f"Error: {str(e)}", "error")
            self.finished_signal.emit(False, None)


class TerminalWidget(QTextEdit):
    """Custom terminal output widget"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 10))
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333;
                padding: 10px;
            }
        """)
        self.setMinimumHeight(100)

    def log(self, message: str, level: str = "info"):
        """Add colored log message"""
        colors = {
            "info": "#569cd6",
            "success": "#4ec9b0",
            "error": "#f44747",
            "warning": "#dcdcaa",
            "command": "#ce9178",
        }

        color = colors.get(level, "#d4d4d4")
        timestamp = datetime.now().strftime("%H:%M:%S")

        self.append(
            f'<span style="color: #666;">[{timestamp}]</span> '
            f'<span style="color: {color};">{message}</span>'
        )

        # Auto-scroll to bottom
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_log(self):
        self.clear()


class AppSelectionWidget(QWidget):
    """Widget for selecting applications"""

    selection_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.applications: List[scanner.Application] = []
        self.categories: Dict[str, List[scanner.Application]] = {}
        self.checkboxes: Dict[str, QCheckBox] = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Controls
        controls = QHBoxLayout()

        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories")
        self.category_filter.currentTextChanged.connect(self.filter_categories)
        controls.addWidget(QLabel("Filter:"))
        controls.addWidget(self.category_filter)

        controls.addStretch()

        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        controls.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self.deselect_all)
        controls.addWidget(deselect_all_btn)

        layout.addLayout(controls)

        # Applications tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Application", "Method", "Description", ""])
        # Use resize modes instead of fixed widths for better responsiveness
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: #252525;
                border: 1px solid #444;
                alternate-background-color: #2a2a2a;
            }
            QTreeWidget::item {
                padding: 5px;
            }
            QTreeWidget::item:selected {
                background-color: #87b722;
                color: white;
            }
            QHeaderView::section {
                background-color: #3d3d3d;
                padding: 5px;
                border: 1px solid #555;
            }
        """)
        layout.addWidget(self.tree)

        # Selection counter
        self.counter_label = QLabel("Selected: 0 / 0")
        layout.addWidget(self.counter_label)

    def set_applications(self, applications: List[scanner.Application]):
        """Load applications into the tree"""
        self.applications = applications
        self.categories = {}
        self.checkboxes = {}

        # Group by category
        for app in applications:
            cat = app.category
            if cat not in self.categories:
                self.categories[cat] = []
            self.categories[cat].append(app)

        # Update category filter
        self.category_filter.clear()
        self.category_filter.addItem("All Categories")
        for cat in sorted(self.categories.keys()):
            self.category_filter.addItem(f"{cat} ({len(self.categories[cat])})")

        self.populate_tree()
        self.update_counter()

    def populate_tree(self):
        """Populate tree widget with applications"""
        self.tree.clear()
        filter_cat = self.category_filter.currentText().split(" (")[0]

        for category in sorted(self.categories.keys()):
            if filter_cat != "All Categories" and category != filter_cat:
                continue

            # Category header
            cat_item = QTreeWidgetItem(self.tree)
            cat_item.setText(0, f"📁 {category}")
            cat_item.setText(3, str(len(self.categories[category])))
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)

            font = cat_item.font(0)
            font.setBold(True)
            cat_item.setFont(0, font)

            # Applications in category
            for app in sorted(self.categories[category], key=lambda x: x.name):
                app_item = QTreeWidgetItem(cat_item)
                app_item.setText(0, app.name)
                app_item.setText(1, app.install_method)
                app_item.setText(2, app.description[:60] if app.description else "")

                # Checkbox for selection
                checkbox = QCheckBox()
                checkbox.setChecked(app.selected)
                checkbox.stateChanged.connect(
                    lambda state, a=app: self.on_checkbox_changed(a, state)
                )
                self.tree.setItemWidget(app_item, 3, checkbox)
                self.checkboxes[app.name] = checkbox

    def on_checkbox_changed(self, app: scanner.Application, state: int):
        """Handle checkbox state change"""
        app.selected = state == Qt.CheckState.Checked.value
        self.update_counter()
        self.selection_changed.emit()

    def select_all(self):
        """Select all applications"""
        for app in self.applications:
            app.selected = True
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(True)
        self.update_counter()
        self.selection_changed.emit()

    def deselect_all(self):
        """Deselect all applications"""
        for app in self.applications:
            app.selected = False
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)
        self.update_counter()
        self.selection_changed.emit()

    def filter_categories(self):
        """Filter by category"""
        self.populate_tree()

    def update_counter(self):
        """Update selection counter"""
        selected = sum(1 for app in self.applications if app.selected)
        total = len(self.applications)
        self.counter_label.setText(f"Selected: {selected} / {total}")

    def get_selected_apps(self) -> List[scanner.Application]:
        """Get list of selected applications"""
        return [app for app in self.applications if app.selected]


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Linux Mint System Migration Tool")
        # Set reasonable minimum size but allow smaller windows
        self.setMinimumSize(800, 600)
        # Start with a good default size
        self.resize(1200, 800)

        self.scanner_thread: Optional[ScannerThread] = None
        self.scan_result: Optional[dict] = None

        self.init_ui()
        self.load_existing_data()

    def init_ui(self):
        """Initialize user interface"""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        # Main layout
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Left sidebar
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)

        # Right content area
        content = self.create_content_area()
        main_layout.addWidget(content, 1)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def create_sidebar(self) -> QWidget:
        """Create left sidebar with controls"""
        sidebar = QWidget()
        sidebar.setMaximumWidth(350)
        sidebar.setMinimumWidth(200)
        sidebar.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
            }
        """)

        layout = QVBoxLayout(sidebar)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("🐧 Mint Migration")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #87b722;")
        layout.addWidget(title)

        version = QLabel("v1.0")
        version.setStyleSheet("color: #888; margin-bottom: 20px;")
        layout.addWidget(version)

        # Mode selection
        mode_group = QGroupBox("Mode")
        mode_layout = QVBoxLayout(mode_group)

        self.mode_backup = QPushButton("📦 Backup Mode")
        self.mode_backup.setCheckable(True)
        self.mode_backup.setChecked(True)
        self.mode_backup.clicked.connect(lambda: self.set_mode("backup"))
        mode_layout.addWidget(self.mode_backup)

        self.mode_restore = QPushButton("🔄 Restore Mode")
        self.mode_restore.setCheckable(True)
        self.mode_restore.clicked.connect(lambda: self.set_mode("restore"))
        mode_layout.addWidget(self.mode_restore)

        layout.addWidget(mode_group)

        # Step buttons
        steps_group = QGroupBox("Steps")
        steps_layout = QVBoxLayout(steps_group)

        self.btn_scan = QPushButton("1️⃣  Scan System")
        self.btn_scan.setMinimumHeight(45)
        self.btn_scan.clicked.connect(self.start_scan)
        steps_layout.addWidget(self.btn_scan)

        self.btn_select = QPushButton("2️⃣  Select Apps")
        self.btn_select.setMinimumHeight(45)
        self.btn_select.setEnabled(False)
        self.btn_select.clicked.connect(lambda: self.content_stack.setCurrentIndex(1))
        steps_layout.addWidget(self.btn_select)

        self.btn_backup = QPushButton("3️⃣  Create Package")
        self.btn_backup.setMinimumHeight(45)
        self.btn_backup.setEnabled(False)
        self.btn_backup.clicked.connect(self.create_migration_package)
        steps_layout.addWidget(self.btn_backup)

        layout.addWidget(steps_group)

        # Backup options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.chk_backup_configs = QCheckBox("Include config files")
        self.chk_backup_configs.setChecked(True)
        self.chk_backup_configs.setToolTip(
            "Backup application configuration files (recommended)"
        )
        options_layout.addWidget(self.chk_backup_configs)

        self.chk_backup_global = QCheckBox("Include global configs")
        self.chk_backup_global.setChecked(True)
        self.chk_backup_global.setToolTip(
            "Backup themes, icons, fonts, and desktop entries"
        )
        options_layout.addWidget(self.chk_backup_global)

        self.chk_dry_run = QCheckBox("Dry run (preview only)")
        self.chk_dry_run.setChecked(False)
        self.chk_dry_run.setToolTip(
            "Show what would be installed without making changes"
        )
        options_layout.addWidget(self.chk_dry_run)

        self.chk_stage_restore = QCheckBox("Safe staged restore to folder")
        self.chk_stage_restore.setChecked(False)
        self.chk_stage_restore.setToolTip(
            "Restore configs into a separate folder instead of your real home directory"
        )
        options_layout.addWidget(self.chk_stage_restore)

        layout.addWidget(options_group)

        # Progress
        self.progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(self.progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setWordWrap(True)
        self.progress_label.setMaximumWidth(280)
        self.progress_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        progress_layout.addWidget(self.progress_label)

        # Cancel button
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #c75450;
                color: white;
                border: none;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #d75450;
            }
        """)
        self.btn_cancel.clicked.connect(self.cancel_operation)
        progress_layout.addWidget(self.btn_cancel)

        layout.addWidget(self.progress_group)

        layout.addStretch()

        # Stats
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)

        self.stat_total = QLabel("Applications: 0")
        stats_layout.addWidget(self.stat_total)

        self.stat_selected = QLabel("Selected: 0")
        stats_layout.addWidget(self.stat_selected)

        self.stat_repos = QLabel("Repositories: 0")
        stats_layout.addWidget(self.stat_repos)

        self.stat_services = QLabel("Services: 0")
        stats_layout.addWidget(self.stat_services)

        layout.addWidget(stats_group)

        return sidebar

    def create_content_area(self) -> QWidget:
        """Create main content area"""
        content = QWidget()
        content.setStyleSheet("background-color: #1e1e1e;")

        layout = QVBoxLayout(content)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Stacked widget for different views
        self.content_stack = QStackedWidget()

        # Welcome view
        self.welcome_widget = self.create_welcome_view()
        self.content_stack.addWidget(self.welcome_widget)

        # Selection view
        self.selection_widget = AppSelectionWidget()
        self.selection_widget.selection_changed.connect(self.update_stats)
        self.content_stack.addWidget(self.selection_widget)

        layout.addWidget(self.content_stack, 1)

        # Terminal
        terminal_group = QGroupBox("Terminal Output")
        terminal_layout = QVBoxLayout(terminal_group)
        terminal_layout.setContentsMargins(10, 15, 10, 10)

        self.terminal = TerminalWidget()
        terminal_layout.addWidget(self.terminal)

        # Terminal controls
        term_controls = QHBoxLayout()

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.terminal.clear_log)
        term_controls.addWidget(clear_btn)

        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(self.copy_terminal)
        term_controls.addWidget(copy_btn)

        save_btn = QPushButton("Save Log")
        save_btn.clicked.connect(self.save_log)
        term_controls.addWidget(save_btn)

        term_controls.addStretch()

        terminal_layout.addLayout(term_controls)
        layout.addWidget(terminal_group)

        return content

    def create_welcome_view(self) -> QWidget:
        """Create welcome screen"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        welcome = QLabel("Welcome to Linux Mint Migration Tool")
        welcome.setStyleSheet("font-size: 28px; font-weight: bold; color: #87b722;")
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(welcome)

        desc = QLabel("""This tool helps you migrate your Linux Mint system to a new machine.

✓ Scans for all installed applications and repositories
✓ Backs up configurations (not the apps themselves)
✓ Generates installation scripts for the new system
✓ Handles apt, flatpak, snap, and manual installs

Click 'Scan System' to begin.""")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet(
            "font-size: 14px; color: #aaa; padding: 20px; max-width: 600px;"
        )
        layout.addWidget(desc)

        start_btn = QPushButton("🚀  Start System Scan")
        start_btn.setMinimumHeight(60)
        start_btn.setMinimumWidth(300)
        start_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                background-color: #87b722;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 15px 30px;
            }
            QPushButton:hover {
                background-color: #6a9119;
            }
            QPushButton:pressed {
                background-color: #5a7d16;
            }
        """)
        start_btn.clicked.connect(self.start_scan)
        layout.addWidget(start_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

        return widget

    def set_mode(self, mode: str):
        """Switch between backup and restore modes"""
        self.current_mode = mode
        if mode == "backup":
            self.mode_backup.setChecked(True)
            self.mode_restore.setChecked(False)
            self.btn_scan.setText("1️⃣  Scan System")
            self.btn_backup.setText("3️⃣  Create Package")
            self.btn_scan.setEnabled(True)
            self.btn_select.setEnabled(self.scan_result is not None)
            self.btn_backup.setEnabled(self.scan_result is not None)
        else:
            self.mode_backup.setChecked(False)
            self.mode_restore.setChecked(True)
            self.btn_scan.setText("1️⃣  Load Package")
            self.btn_backup.setText("3️⃣  Restore Selected")
            self.btn_scan.setEnabled(True)
            self.btn_select.setEnabled(False)
            self.btn_backup.setEnabled(False)

    def start_scan(self):
        """Start system scan or load package based on mode"""
        if getattr(self, "current_mode", "backup") == "restore":
            self.load_migration_package()
        else:
            self.terminal.clear_log()
            self.terminal.log("=" * 60, "info")
            self.terminal.log("Starting System Scan...", "info")
            self.terminal.log("=" * 60, "info")

            self.btn_scan.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)

            self.scanner_thread = ScannerThread()
            self.scanner_thread.progress.connect(self.on_scan_progress)
            self.scanner_thread.log.connect(self.terminal.log)
            self.scanner_thread.finished_signal.connect(self.on_scan_finished)
            self.scanner_thread.start()

    def load_migration_package(self):
        """Load migration package for restore mode"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Migration Package",
            str(Path.home()),
            "JSON Files (*.json);;All Files (*)",
        )

        if not file_path:
            return

        self.terminal.clear_log()
        self.terminal.log("=" * 60, "info")
        self.terminal.log("Loading Migration Package...", "info")
        self.terminal.log("=" * 60, "info")

        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            self.scan_result = data
            self._last_package_path = file_path

            # Convert dict back to Application objects
            apps = [
                scanner.Application(**app_dict)
                for app_dict in data.get("applications", [])
            ]
            self.selection_widget.set_applications(apps)

            # Enable buttons
            self.btn_select.setEnabled(True)
            self.btn_backup.setEnabled(True)

            # Show selection view
            self.content_stack.setCurrentIndex(1)

            # Update stats
            self.update_stats()

            self.terminal.log(f"\n✓ Loaded package from: {file_path}", "success")
            self.terminal.log(f"  Applications: {len(apps)}")
            self.terminal.log(f"  Repositories: {len(data.get('repositories', []))}")
            self.terminal.log(f"  Services: {len(data.get('services', []))}")
            self.terminal.log("\nSelect applications to restore.", "info")
            self.status_bar.showMessage(f"Loaded {len(apps)} applications", 5000)

        except Exception as e:
            self.terminal.log(f"\n✗ Failed to load package: {e}", "error")
            self.status_bar.showMessage("Failed to load package", 5000)

    def on_scan_progress(self, percent: int, message: str):
        """Update scan progress"""
        self.progress_bar.setValue(percent)
        self.progress_label.setText(message)
        self.status_bar.showMessage(message)

    def on_scan_finished(self, success: bool, result: dict):
        """Handle scan completion"""
        self.btn_scan.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.progress_label.setText("")

        if success:
            self.scan_result = result

            # Convert dict back to Application objects
            apps = [
                scanner.Application(**app_dict) for app_dict in result["applications"]
            ]
            self.selection_widget.set_applications(apps)

            # Enable buttons
            self.btn_select.setEnabled(True)
            self.btn_backup.setEnabled(True)

            # Show selection view
            self.content_stack.setCurrentIndex(1)

            # Update stats
            self.update_stats()

            self.terminal.log(
                "\n✓ Scan complete! Select applications to include.", "success"
            )
            self.status_bar.showMessage(f"Found {len(apps)} applications", 5000)
        else:
            self.terminal.log("\n✗ Scan failed!", "error")
            self.status_bar.showMessage("Scan failed", 5000)

    def update_stats(self):
        """Update statistics display"""
        if not self.scan_result:
            return

        apps = self.selection_widget.get_selected_apps()
        total = len(self.selection_widget.applications)
        selected = len(apps)

        self.stat_total.setText(f"Applications: {total}")
        self.stat_selected.setText(f"Selected: {selected}")
        self.stat_repos.setText(
            f"Repositories: {len(self.scan_result.get('repositories', []))}"
        )
        self.stat_services.setText(
            f"Services: {len(self.scan_result.get('services', []))}"
        )

    def create_migration_package(self):
        """Create migration package or restore based on mode"""
        if getattr(self, "current_mode", "backup") == "restore":
            self.start_restore()
        else:
            self.start_backup()

    def start_backup(self):
        """Create migration package with optional config backup"""
        if not self.scan_result:
            return

        selected_apps = self.selection_widget.get_selected_apps()
        if not selected_apps:
            QMessageBox.warning(
                self, "No Selection", "Please select at least one application."
            )
            return

        # Update scan result with selected apps
        self.scan_result["applications"] = [app.to_dict() for app in selected_apps]
        self.scan_result["export_date"] = datetime.now().isoformat()

        # Ask for save location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Migration Package",
            str(Path.home() / "mint-migration.json"),
            "JSON Files (*.json);;All Files (*)",
        )

        if not file_path:
            return

        # Store for later use
        self._last_package_path = file_path

        # Save JSON package
        with open(file_path, "w") as f:
            json.dump(self.scan_result, f, indent=2)

        self.terminal.log(f"\n✓ Migration package saved: {file_path}", "success")
        self.status_bar.showMessage(f"Saved to {file_path}", 5000)

        # Backup configs if enabled
        if self.chk_backup_configs.isChecked():
            self.terminal.log("\nStarting config backup...", "info")
            self.btn_backup.setEnabled(False)
            self.btn_cancel.setVisible(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)

            output_dir = Path(file_path).parent
            self.config_backup_thread = ConfigBackupThread(
                apps=[app.to_dict() for app in selected_apps],
                output_dir=output_dir,
                include_global=self.chk_backup_global.isChecked(),
            )
            self.config_backup_thread.progress.connect(self.on_config_backup_progress)
            self.config_backup_thread.log.connect(self.terminal.log)
            self.config_backup_thread.finished_signal.connect(
                self.on_config_backup_finished
            )
            self.config_backup_thread.start()
        else:
            self.show_completion_dialog(file_path, selected_apps)

    def start_restore(self):
        """Start restore process from loaded package"""
        if not self.scan_result:
            return

        selected_apps = self.selection_widget.get_selected_apps()
        if not selected_apps:
            QMessageBox.warning(
                self, "No Selection", "Please select at least one application."
            )
            return

        # Get package path
        package_path = Path(getattr(self, "_last_package_path", ""))
        if not package_path.exists():
            QMessageBox.warning(
                self, "No Package", "Please load a migration package first."
            )
            return

        # Confirm restore
        dry_run = (
            self.chk_dry_run.isChecked() if hasattr(self, "chk_dry_run") else False
        )
        staged_restore_root = None
        staged_restore = (
            self.chk_stage_restore.isChecked()
            if hasattr(self, "chk_stage_restore")
            else False
        )
        if staged_restore:
            staged_dir = QFileDialog.getExistingDirectory(
                self,
                "Choose staged restore folder",
                str(Path.home() / "MintRestorePreview"),
            )
            if not staged_dir:
                return
            staged_restore_root = Path(staged_dir)

        mode_str = "[DRY-RUN] " if dry_run else ""
        staged_note = (
            "\n\nStaged restore mode will restore configs into a separate folder and will not install apps, add repos, or enable services."
            if staged_restore_root
            else ""
        )

        reply = QMessageBox.question(
            self,
            f"{mode_str}Confirm Restore",
            f"{mode_str}This will install {len(selected_apps)} applications, add repositories, and restore configs.{staged_note}\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Start restore
        self.terminal.log("\n" + "=" * 60, "info")
        self.terminal.log(f"{mode_str}Starting Restore...", "info")
        self.terminal.log("=" * 60, "info")

        self.btn_backup.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        selected_app_names = [app.name for app in selected_apps]

        self.restore_thread = RestoreThread(
            package_path=package_path,
            selected_apps=selected_app_names,
            dry_run=dry_run,
            staged_restore_root=staged_restore_root,
        )
        self.restore_thread.progress.connect(self.on_restore_progress)
        self.restore_thread.log.connect(self.terminal.log)
        self.restore_thread.finished_signal.connect(self.on_restore_finished)
        self.restore_thread.start()

    def on_restore_progress(self, percent: int, message: str):
        """Update restore progress"""
        self.progress_bar.setValue(percent)
        self.progress_label.setText(message)
        self.status_bar.showMessage(message)

    def on_restore_finished(self, success: bool, result):
        """Handle restore completion"""
        self.btn_backup.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.progress_label.setText("")

        if result and success:
            mode_str = "[DRY-RUN] " if result.dry_run else ""
            self.terminal.log(f"\n{mode_str}✓ Restore completed!", "success")
            self.terminal.log(f"  Installed: {len(result.installed_apps)}")
            self.terminal.log(f"  Repos: {len(result.added_repos)}")
            self.terminal.log(f"  Configs: {len(result.restored_configs)}")
            self.terminal.log(f"  Services: {len(result.enabled_services)}")
            if getattr(result, "staged_restore_root", None):
                self.terminal.log(f"  Staged to: {result.staged_restore_root}", "info")

            if result.failed_apps:
                self.terminal.log(f"  Failed: {len(result.failed_apps)}")

            QMessageBox.information(
                self,
                f"{mode_str}Restore Complete",
                f"{mode_str}Restore completed!\n\n"
                f"Installed: {len(result.installed_apps)}\n"
                f"Repositories: {len(result.added_repos)}\n"
                f"Configs: {len(result.restored_configs)}\n"
                f"Services: {len(result.enabled_services)}"
                + (
                    f"\nStaged to: {result.staged_restore_root}"
                    if getattr(result, "staged_restore_root", None)
                    else ""
                ),
            )
        else:
            self.terminal.log("\n✗ Restore failed!", "error")
            QMessageBox.critical(
                self,
                "Restore Failed",
                "The restore operation failed. Check the log for details.",
            )

    def on_config_backup_progress(self, percent: int, message: str):
        """Update config backup progress"""
        self.progress_bar.setValue(percent)
        self.progress_label.setText(message)
        self.status_bar.showMessage(message)

    def on_config_backup_finished(self, success: bool, result):
        """Handle config backup completion"""
        self.btn_backup.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setText("")

        selected_apps = self.selection_widget.get_selected_apps()
        # Get the file path from the last saved location
        file_path = getattr(self, "_last_package_path", "unknown")

        if success and result:
            if result.archive_path and file_path != "unknown":
                try:
                    with open(file_path, "r") as handle:
                        package_data = json.load(handle)
                    package_data["config_archive_name"] = result.archive_path.name
                    package_data["config_archive_path"] = str(result.archive_path)
                    with open(file_path, "w") as handle:
                        json.dump(package_data, handle, indent=2)
                except Exception as e:
                    self.terminal.log(
                        f"⚠ Failed to update package metadata with config archive: {e}",
                        "warning",
                    )
            self.terminal.log(
                f"\n✓ Config backup complete: {result.archive_path}", "success"
            )
            self.show_completion_dialog(file_path, selected_apps, result)
        else:
            self.terminal.log(
                "\n⚠ Config backup failed, but package was saved", "warning"
            )
            self.show_completion_dialog(file_path, selected_apps)

    def show_completion_dialog(self, file_path: str, selected_apps, backup_result=None):
        """Show package creation completion dialog"""
        message = (
            f"Migration package saved to:\n{file_path}\n\n"
            f"Applications: {len(selected_apps)}\n"
            f"Services: {len(self.scan_result.get('services', []) if self.scan_result else [])}\n"
            f"VMs: {len(self.scan_result.get('vms', []) if self.scan_result else [])}"
        )

        if backup_result and backup_result.archive_path:
            message += f"\n\nConfig backup:\n{backup_result.archive_path}\n"
            message += f"Size: {self._format_size(backup_result.total_size)}"

        QMessageBox.information(self, "Package Created", message)

    def _format_size(self, size_bytes: int) -> str:
        """Format bytes to human readable string"""
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def cancel_operation(self):
        """Cancel the current operation"""
        self.terminal.log("\n⚠ Cancelling operation...", "warning")

        # Cancel config backup if running
        if (
            hasattr(self, "config_backup_thread")
            and self.config_backup_thread
            and self.config_backup_thread.isRunning()
        ):
            self.config_backup_thread.cancel()
            self.btn_cancel.setVisible(False)
            self.btn_backup.setEnabled(True)
            self.terminal.log("Backup cancelled", "warning")

    def copy_terminal(self):
        """Copy terminal content to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.terminal.toPlainText())
        self.status_bar.showMessage("Copied to clipboard", 2000)

    def save_log(self):
        """Save terminal log to file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Log",
            str(Path.home() / "mint-migration-log.txt"),
            "Text Files (*.txt);;All Files (*)",
        )

        if file_path:
            with open(file_path, "w") as f:
                f.write(self.terminal.toPlainText())
            self.status_bar.showMessage(f"Log saved to {file_path}", 3000)

    def load_existing_data(self):
        """Load existing scan data if available"""
        scan_file = Path.home() / "scan_result.json"
        if scan_file.exists():
            try:
                with open(scan_file, "r") as f:
                    self.scan_result = json.load(f)

                apps = [
                    scanner.Application(**app_dict)
                    for app_dict in self.scan_result["applications"]
                ]
                self.selection_widget.set_applications(apps)

                self.btn_select.setEnabled(True)
                self.btn_backup.setEnabled(True)

                self.update_stats()
                self.terminal.log(
                    f"Loaded {len(apps)} applications from previous scan", "info"
                )
            except Exception as e:
                self.terminal.log(f"Could not load previous scan: {e}", "warning")


def main():
    app = QApplication(sys.argv)

    # Set application-wide stylesheet
    app.setStyle("Fusion")
    app.setStyleSheet("""
        QMainWindow {
            background-color: #1e1e1e;
        }
        QWidget {
            background-color: #1e1e1e;
            color: #e0e0e0;
        }
        QPushButton {
            background-color: #3d3d3d;
            border: 1px solid #555;
            padding: 8px 16px;
            border-radius: 4px;
            color: #e0e0e0;
        }
        QPushButton:hover {
            background-color: #4d4d4d;
            border-color: #666;
        }
        QPushButton:pressed {
            background-color: #87b722;
            color: white;
        }
        QPushButton:disabled {
            background-color: #2b2b2b;
            color: #666;
        }
        QPushButton:checked {
            background-color: #87b722;
            color: white;
            border-color: #6a9119;
        }
        QGroupBox {
            border: 1px solid #444;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
            color: #87b722;
        }
        QComboBox {
            background-color: #3d3d3d;
            border: 1px solid #555;
            padding: 5px;
            border-radius: 3px;
        }
        QComboBox:hover {
            border-color: #666;
        }
        QComboBox::drop-down {
            border: none;
        }
        QComboBox QAbstractItemView {
            background-color: #3d3d3d;
            border: 1px solid #555;
            selection-background-color: #87b722;
        }
        QProgressBar {
            border: 1px solid #444;
            border-radius: 3px;
            text-align: center;
            height: 20px;
        }
        QProgressBar::chunk {
            background-color: #87b722;
            border-radius: 2px;
        }
        QLabel {
            color: #e0e0e0;
        }
        QStatusBar {
            background-color: #2b2b2b;
            color: #888;
        }
    """)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
