"""
Main Application Window for PacGUI.
"""

import threading
from typing import List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, GObject, Gtk, Pango

from backend.alpm_manager import AlpmManager
from backend.aur_manager import AurManager
from backend.flatpak_manager import FlatpakManager
from backend.mirror_manager import MirrorManager
from backend.models import FlatpakApp, PackageInfo, QueueItem, TransactionTask, UpdateInfo
from backend.runner import TransactionRunner
from backend.snapshot_manager import SnapshotManager
from ui.file_owner_dialog import FileOwnerDialog
from ui.flatpak_view import FlatpakView
from ui.maintenance_view import MaintenanceView
from ui.package_detail import PackageDetailView
from ui.package_list import PackageListView
from ui.queue_bar import QueueBar
from ui.terminal_dialog import TerminalDialog
from ui.updates_view import UpdatesView


class MainWindow(Adw.ApplicationWindow):
    """Primary application window with sidebar, package list, detail inspector, and tools."""

    def __init__(
        self,
        app: Adw.Application,
        alpm_mgr: AlpmManager,
        aur_mgr: AurManager,
        flatpak_mgr: FlatpakManager,
        mirror_mgr: MirrorManager,
        snapshot_mgr: SnapshotManager,
    ):
        super().__init__(
            application=app,
            title="PacGUI - Pacman Package Manager",
            default_width=1220,
            default_height=780,
        )
        self.alpm_mgr = alpm_mgr
        self.aur_mgr = aur_mgr
        self.flatpak_mgr = flatpak_mgr
        self.mirror_mgr = mirror_mgr
        self.snapshot_mgr = snapshot_mgr
        self.runner = TransactionRunner()

        self._search_timeout_id: Optional[int] = None
        self._current_scope = "all"
        self._current_sort = "name_asc"
        self._current_repo_filter: Optional[str] = None
        self._enable_aur = False

        self._setup_ui()
        self._load_initial_data()

    def _setup_ui(self):
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        self.toolbar_view = Adw.ToolbarView()
        self.toast_overlay.set_child(self.toolbar_view)

        # Top Header Bar
        header = Adw.HeaderBar()
        self.toolbar_view.add_top_bar(header)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_lbl = Gtk.Label(label="PacGUI", css_classes=["title"])
        self.subtitle_lbl = Gtk.Label(label="Arch Linux Package Manager", css_classes=["subtitle"])
        title_box.append(title_lbl)
        title_box.append(self.subtitle_lbl)
        header.set_title_widget(title_box)

        # Refresh button
        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Refresh Databases (Ctrl+R)")
        refresh_btn.connect("clicked", lambda _: self.refresh_all(show_toast=True))
        header.pack_start(refresh_btn)

        # File owner tool button
        btn_find_file = Gtk.Button(icon_name="system-search-symbolic")
        btn_find_file.set_tooltip_text("Find File Owner (pacman -Qo)")
        btn_find_file.connect("clicked", self._on_find_file_owner_clicked)
        header.pack_start(btn_find_file)

        # App Menu
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu = Gio.Menu()
        menu.append("Check Updates", "app.check_updates")
        menu.append("Clean Cache", "app.clean_cache")
        menu.append("Find File Owner", "app.find_file")
        menu.append("Toggle Color Scheme", "app.toggle_theme")
        menu.append("About PacGUI", "app.about")
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)

        # Vertical layout: Main Paned + Bottom QueueBar
        root_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.toolbar_view.set_content(root_vbox)

        # Main Paned
        self.main_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.main_paned.set_position(250)
        self.main_paned.set_vexpand(True)
        root_vbox.append(self.main_paned)

        # Bottom Queue Bar
        self.queue_bar = QueueBar(
            parent_window=self,
            on_apply_queue=self._handle_apply_queue,
        )
        root_vbox.append(self.queue_bar)

        # --- 1. Left Sidebar ---
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sidebar_box.set_size_request(240, -1)
        sidebar_box.set_margin_top(12)
        sidebar_box.set_margin_bottom(12)
        sidebar_box.set_margin_start(10)
        sidebar_box.set_margin_end(6)
        self.main_paned.set_start_child(sidebar_box)

        # Search entry
        self.search_entry = Gtk.SearchEntry(placeholder_text="Search packages (Ctrl+F)...")
        self.search_entry.connect("search-changed", self._on_search_changed)
        sidebar_box.append(self.search_entry)

        # Repo Filter Dropdown
        repo_filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        repo_lbl = Gtk.Label(label="Repo:", css_classes=["caption"])
        repo_filter_box.append(repo_lbl)

        repos_list = ["All Repositories"] + self.alpm_mgr.registered_repos
        self.repo_dropdown = Gtk.DropDown.new_from_strings(repos_list)
        self.repo_dropdown.set_hexpand(True)
        self.repo_dropdown.connect("notify::selected-item", self._on_repo_filter_changed)
        repo_filter_box.append(self.repo_dropdown)
        sidebar_box.append(repo_filter_box)

        # AUR Search Switch
        aur_row = Adw.ActionRow(title="Search AUR")
        aur_row.set_subtitle(f"via {self.aur_mgr.helper or 'AUR RPC'}")
        self.aur_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.aur_switch.connect("notify::active", self._on_aur_toggled)
        aur_row.add_suffix(self.aur_switch)
        sidebar_box.append(aur_row)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sidebar_box.append(sep)

        nav_scrolled = Gtk.ScrolledWindow(vexpand=True)
        sidebar_box.append(nav_scrolled)

        self.nav_list = Gtk.ListBox()
        self.nav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.nav_list.add_css_class("navigation-sidebar")
        self.nav_list.connect("row-selected", self._on_nav_selected)
        nav_scrolled.set_child(self.nav_list)

        # Standard Sections
        self.row_browse = self._create_nav_row("Browse All Packages", "folder-saved-search-symbolic", "all")
        self.row_installed = self._create_nav_row("Installed Packages", "emblem-ok-symbolic", "installed")
        self.row_explicit = self._create_nav_row("Explicitly Installed", "starred-symbolic", "explicit")
        self.row_deps = self._create_nav_row("Dependencies", "package-x-generic-symbolic", "dependencies")
        self.row_updates = self._create_nav_row("System Updates", "software-update-available-symbolic", "updates", has_badge=True)
        self.row_flatpaks = self._create_nav_row("Flatpak Hub", "application-x-executable-symbolic", "flatpaks")
        self.row_maintenance = self._create_nav_row("Maintenance and Tools", "user-trash-symbolic", "maintenance")

        self.nav_list.append(self.row_browse)
        self.nav_list.append(self.row_installed)
        self.nav_list.append(self.row_explicit)
        self.nav_list.append(self.row_deps)
        self.nav_list.append(self.row_updates)
        if self.flatpak_mgr.is_available:
            self.nav_list.append(self.row_flatpaks)
        self.nav_list.append(self.row_maintenance)

        # Curated Categories Header
        cat_header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        cat_header_box.set_margin_top(8)
        cat_header_box.set_margin_start(10)
        cat_header_box.set_margin_bottom(4)
        cat_lbl = Gtk.Label(label="CATEGORIES", css_classes=["caption", "heading"], halign=Gtk.Align.START)
        cat_header_box.append(cat_lbl)
        self.nav_list.append(cat_header_box)

        # Curated Categories Rows
        self.nav_list.append(self._create_nav_row("Development", "utilities-terminal-symbolic", "cat:development"))
        self.nav_list.append(self._create_nav_row("Multimedia", "applications-multimedia-symbolic", "cat:multimedia"))
        self.nav_list.append(self._create_nav_row("Internet and Network", "applications-internet-symbolic", "cat:internet"))
        self.nav_list.append(self._create_nav_row("Graphics and 3D", "applications-graphics-symbolic", "cat:graphics"))
        self.nav_list.append(self._create_nav_row("System and Utilities", "applications-system-symbolic", "cat:system"))
        self.nav_list.append(self._create_nav_row("Games and Emulation", "applications-games-symbolic", "cat:games"))
        self.nav_list.append(self._create_nav_row("Office and Reading", "x-office-document-symbolic", "cat:office"))

        # --- 2. Right Split: Content View + Package Details ---
        self.content_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.content_paned.set_position(460)
        self.main_paned.set_end_child(self.content_paned)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.content_paned.set_start_child(self.stack)

        # 2a. Package List View
        self.package_list_view = PackageListView(
            on_selected=self._on_package_selected,
            on_action=self._handle_package_action,
            on_queue=self._handle_add_to_queue,
            on_sort_changed=self._handle_sort_changed,
        )
        self.stack.add_named(self.package_list_view, "packages")

        # 2b. Updates View
        self.updates_view = UpdatesView(
            on_check_updates=lambda: self.check_updates(show_toast=True),
            on_upgrade_all=self._handle_upgrade_all,
            on_update_single=self._handle_update_single,
        )
        self.stack.add_named(self.updates_view, "updates")

        # 2c. Flatpak View
        self.flatpak_view = FlatpakView(
            flatpak_mgr=self.flatpak_mgr,
            on_action=self._handle_flatpak_action,
            on_update_all=self._handle_flatpak_update_all,
        )
        self.stack.add_named(self.flatpak_view, "flatpaks")

        # 2d. Maintenance View
        self.maintenance_view = MaintenanceView(
            alpm_mgr=self.alpm_mgr,
            mirror_mgr=self.mirror_mgr,
            snapshot_mgr=self.snapshot_mgr,
            on_clean_cache=self._handle_clean_cache,
            on_remove_orphans=self._handle_remove_orphans,
            on_rank_mirrors=self._handle_rank_mirrors,
            on_troubleshoot=self._handle_troubleshoot,
            on_restore_snapshot=self._handle_restore_snapshot,
            on_refresh=self.refresh_all,
        )
        self.stack.add_named(self.maintenance_view, "maintenance")

        # 3. Package Detail View
        self.package_detail_view = PackageDetailView(
            on_action=self._handle_package_action,
            on_select_dep=self._navigate_to_package,
        )
        self.content_paned.set_end_child(self.package_detail_view)

    def _create_nav_row(self, title: str, icon_name: str, scope_key: str, has_badge: bool = False) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.scope_key = scope_key

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(10)
        box.set_margin_end(10)
        row.set_child(box)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        box.append(icon)

        lbl = Gtk.Label(label=title, halign=Gtk.Align.START, hexpand=True)
        box.append(lbl)

        if has_badge:
            badge = Gtk.Label(label="", css_classes=["sidebar-badge"])
            badge.set_visible(False)
            box.append(badge)
            row.badge_widget = badge

        return row

    def _load_initial_data(self):
        self.nav_list.select_row(self.row_browse)
        self._update_counts()
        self._execute_search()

    def _update_counts(self):
        def _check_bg():
            updates = self.alpm_mgr.get_updates()
            cache_info = self.alpm_mgr.get_cache_info()
            orphans = self.alpm_mgr.get_orphans()
            logs = self.alpm_mgr.get_recent_logs(100)

            def _update_ui():
                if hasattr(self.row_updates, "badge_widget"):
                    if updates:
                        self.row_updates.badge_widget.set_label(str(len(updates)))
                        self.row_updates.badge_widget.set_visible(True)
                    else:
                        self.row_updates.badge_widget.set_visible(False)

                self.updates_view.set_updates(updates)
                self.maintenance_view.set_cache_info(cache_info)
                self.maintenance_view.set_orphans(orphans)
                self.maintenance_view.set_logs(logs)
                self.maintenance_view.refresh_status()

                local_count = len(self.alpm_mgr._local_cache)
                sync_count = len(self.alpm_mgr._sync_cache)
                self.subtitle_lbl.set_label(f"{local_count} installed • {sync_count} in repositories")

            GLib.idle_add(_update_ui)

        threading.Thread(target=_check_bg, daemon=True).start()

    def _on_nav_selected(self, _box, row):
        if not row or not hasattr(row, "scope_key"):
            return

        self._current_scope = row.scope_key
        if self._current_scope == "updates":
            self.stack.set_visible_child_name("updates")
        elif self._current_scope == "flatpaks":
            self.stack.set_visible_child_name("flatpaks")
            self.flatpak_view.load_installed()
        elif self._current_scope == "maintenance":
            self.stack.set_visible_child_name("maintenance")
            self.maintenance_view.refresh_status()
            self._update_counts()
        else:
            self.stack.set_visible_child_name("packages")
            self._execute_search()

    def _on_search_changed(self, entry):
        if self._search_timeout_id:
            GLib.source_remove(self._search_timeout_id)
        self._search_timeout_id = GLib.timeout_add(200, self._execute_search)

    def _on_repo_filter_changed(self, dropdown, _param):
        selected_item = dropdown.get_selected_item()
        if selected_item:
            val = selected_item.get_string()
            self._current_repo_filter = None if val == "All Repositories" else val
            self._execute_search()

    def _on_aur_toggled(self, switch, _param):
        self._enable_aur = switch.get_active()
        self._execute_search()

    def _handle_sort_changed(self, sort_key: str):
        self._current_sort = sort_key
        self._execute_search()

    def _execute_search(self) -> bool:
        self._search_timeout_id = None
        query = self.search_entry.get_text().strip()

        if query and self._current_scope in ("updates", "flatpaks", "maintenance"):
            self.nav_list.select_row(self.row_browse)
            return False

        results = self.alpm_mgr.search_packages(
            query=query,
            scope=self._current_scope,
            repo=self._current_repo_filter,
            sort_by=self._current_sort,
            limit=300,
        )

        if self._enable_aur and query and len(query) >= 2 and self._current_scope in ("all",):
            def _aur_search_bg():
                aur_results = self.aur_mgr.search(query, limit=30)

                def _merge_aur():
                    combined = list(results)
                    existing_names = {p.name for p in combined}
                    for ap in aur_results:
                        if ap.name not in existing_names:
                            combined.append(ap)
                    self.alpm_mgr._apply_sorting(combined, sort_by=self._current_sort, query=query)
                    self.package_list_view.set_packages(combined)

                GLib.idle_add(_merge_aur)

            threading.Thread(target=_aur_search_bg, daemon=True).start()

        self.package_list_view.set_packages(results)
        return False

    def _on_package_selected(self, pkg: PackageInfo):
        full_info = self.alpm_mgr.get_package_info(pkg.name, repo=pkg.repo, deep=True) or pkg
        self.package_detail_view.display_package(full_info)

    def _navigate_to_package(self, pkg_name: str):
        pkg = self.alpm_mgr.get_package_info(pkg_name, deep=True)
        if pkg:
            self.package_detail_view.display_package(pkg)
        else:
            self.search_entry.set_text(pkg_name)
            self._execute_search()

    def _on_find_file_owner_clicked(self, _btn):
        dialog = FileOwnerDialog(self, self.alpm_mgr, self._navigate_to_package)
        dialog.present()

    def _handle_add_to_queue(self, item: QueueItem):
        self.queue_bar.add_item(item)
        toast = Adw.Toast(title=f"Added {item.pkg_name} ({item.action}) to queue.")
        self.toast_overlay.add_toast(toast)

    def _handle_apply_queue(self, items: List[QueueItem]):
        installs = [i.pkg_name for i in items if i.action in ("install", "reinstall")]
        removals = [i.pkg_name for i in items if i.action == "remove"]
        has_aur = any(i.is_aur for i in items)

        task = TransactionTask(
            action_type="batch",
            packages=installs,
            remove_packages=removals,
            title="Batch Package Transaction",
            description=f"Applying batch operations: {len(installs)} install, {len(removals)} remove",
            use_aur_helper=has_aur and bool(self.aur_mgr.helper),
        )
        self._launch_terminal_dialog(task)

    def _handle_package_action(self, action_type: str, pkg: PackageInfo, cascade: bool = True):
        flags = ["--noconfirm"]
        is_aur = pkg.is_aur or (pkg.repo == "aur")
        use_aur = is_aur and bool(self.aur_mgr.helper)

        title = f"{action_type.capitalize()} {pkg.name}"
        desc = f"Executing package transaction for {pkg.name}"

        task = TransactionTask(
            action_type=action_type,
            packages=[pkg.name],
            title=title,
            description=desc,
            flags=flags,
            use_aur_helper=use_aur,
        )
        self._launch_terminal_dialog(task)

    def _handle_flatpak_action(self, action_type: str, app: FlatpakApp):
        act_key = "flatpak_install" if action_type == "install" else "flatpak_remove"
        title = f"{action_type.capitalize()} Flatpak: {app.name}"
        task = TransactionTask(
            action_type=act_key,
            packages=[app.app_id],
            title=title,
            description=f"Executing Flatpak action for {app.app_id}",
        )
        self._launch_terminal_dialog(task)

    def _handle_flatpak_update_all(self):
        task = TransactionTask(
            action_type="flatpak_update",
            packages=[],
            title="Update All Flatpaks",
            description="Updating all installed Flatpak runtimes and applications",
        )
        self._launch_terminal_dialog(task)

    def _handle_upgrade_all(self):
        task = TransactionTask(
            action_type="upgrade",
            packages=[],
            title="System Upgrade",
            description="Upgrading all outdated packages to latest repository versions",
            flags=["--noconfirm"],
            use_aur_helper=bool(self.aur_mgr.helper and self._enable_aur),
        )
        self._launch_terminal_dialog(task)

    def _handle_update_single(self, pkg_name: str):
        task = TransactionTask(
            action_type="install",
            packages=[pkg_name],
            title=f"Upgrade {pkg_name}",
            description=f"Upgrading {pkg_name} to latest repository version",
            flags=["--noconfirm"],
        )
        self._launch_terminal_dialog(task)

    def _handle_clean_cache(self, action_key: str):
        title = "Clean Package Cache" if action_key == "clean_cache" else "Aggressive Cache Prune"
        task = TransactionTask(
            action_type=action_key,
            packages=[],
            title=title,
            description="Pruning old package archives from /var/cache/pacman/pkg",
        )
        self._launch_terminal_dialog(task)

    def _handle_remove_orphans(self, orphan_names: List[str]):
        task = TransactionTask(
            action_type="remove_orphans",
            packages=orphan_names,
            title="Remove Orphan Packages",
            description=f"Removing {len(orphan_names)} unused dependency packages",
            flags=["--noconfirm"],
        )
        self._launch_terminal_dialog(task)

    def _handle_rank_mirrors(self, tool: str, country: Optional[str]):
        cmd = self.mirror_mgr.build_rank_command(tool=tool, country=country)
        task = TransactionTask(
            action_type="custom",
            packages=[],
            title="Benchmark & Rank Mirrors",
            description="Benchmarking fastest mirrors and saving to /etc/pacman.d/mirrorlist",
            flags=cmd,
        )
        self._launch_terminal_dialog(task)

    def _handle_troubleshoot(self, tool_action: str):
        title = "Unlock Database" if tool_action == "unlock_db" else "Repair Keyring"
        desc = "Removing database lock file" if tool_action == "unlock_db" else "Initializing and populating pacman keys"
        task = TransactionTask(
            action_type=tool_action,
            packages=[],
            title=title,
            description=desc,
        )
        self._launch_terminal_dialog(task)

    def _handle_restore_snapshot(self, missing_packages: List[str]):
        if not missing_packages:
            toast = Adw.Toast(title="All snapshot packages are already installed.")
            self.toast_overlay.add_toast(toast)
            return

        task = TransactionTask(
            action_type="install",
            packages=missing_packages,
            title=f"Restore Snapshot ({len(missing_packages)} pkgs)",
            description=f"Installing {len(missing_packages)} missing packages from snapshot",
            flags=["--noconfirm"],
        )
        self._launch_terminal_dialog(task)

    def _launch_terminal_dialog(self, task: TransactionTask):
        dialog = TerminalDialog(
            parent_window=self,
            task=task,
            runner=self.runner,
            on_complete=self._on_transaction_finished,
            aur_helper=self.aur_mgr.helper,
        )
        dialog.present()

    def _on_transaction_finished(self, success: bool):
        if success:
            toast = Adw.Toast(title="Operation completed successfully.")
            self.toast_overlay.add_toast(toast)
        else:
            toast = Adw.Toast(title="Operation failed or was cancelled.")
            self.toast_overlay.add_toast(toast)

        self.refresh_all(show_toast=False)

    def refresh_all(self, show_toast: bool = False):
        self.alpm_mgr.refresh_cache()
        self._update_counts()
        self._execute_search()
        if show_toast:
            toast = Adw.Toast(title="Package databases reloaded.")
            self.toast_overlay.add_toast(toast)

    def check_updates(self, show_toast: bool = False):
        self._update_counts()
        if show_toast:
            toast = Adw.Toast(title="Checking for package updates...")
            self.toast_overlay.add_toast(toast)
