"""
Maintenance view for cache cleaning, orphan removal, mirror ranking, snapshots, and troubleshooting.
"""

from typing import Callable, Dict, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, GObject, Gtk, Pango

from backend.alpm_manager import AlpmManager
from backend.mirror_manager import MirrorManager
from backend.models import LogEntry, PackageInfo, SnapshotInfo, format_size
from backend.snapshot_manager import SnapshotManager


def escape(text: Optional[str]) -> str:
    """Safely escape text for Pango markup in AdwActionRow."""
    if not text:
        return ""
    return GLib.markup_escape_text(str(text))


class MaintenanceView(Gtk.Box):
    """Comprehensive maintenance dashboard for pacman system tools."""

    def __init__(
        self,
        alpm_mgr: AlpmManager,
        mirror_mgr: MirrorManager,
        snapshot_mgr: SnapshotManager,
        on_clean_cache: Optional[Callable[[str], None]] = None,
        on_remove_orphans: Optional[Callable[[List[str]], None]] = None,
        on_rank_mirrors: Optional[Callable[[str, Optional[str]], None]] = None,
        on_troubleshoot: Optional[Callable[[str], None]] = None,
        on_restore_snapshot: Optional[Callable[[List[str]], None]] = None,
        on_refresh: Optional[Callable[[], None]] = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.alpm_mgr = alpm_mgr
        self.mirror_mgr = mirror_mgr
        self.snapshot_mgr = snapshot_mgr

        self.on_clean_cache = on_clean_cache
        self.on_remove_orphans = on_remove_orphans
        self.on_rank_mirrors = on_rank_mirrors
        self.on_troubleshoot = on_troubleshoot
        self.on_restore_snapshot = on_restore_snapshot
        self.on_refresh = on_refresh

        self.orphans: List[PackageInfo] = []
        self._orphan_rows: List[Adw.ActionRow] = []
        self._log_rows: List[Adw.ActionRow] = []
        self._snapshot_rows: List[Adw.ActionRow] = []

        self._setup_ui()

    def _setup_ui(self):
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self.append(scrolled)

        pref_page = Adw.PreferencesPage()
        pref_page.set_margin_top(16)
        pref_page.set_margin_bottom(24)
        scrolled.set_child(pref_page)

        # === 1. System Health & Lock Troubleshooter Group ===
        health_group = Adw.PreferencesGroup(
            title="System Health and Troubleshooting",
            description="Fix common pacman issues, keyring validation errors, and database locks.",
        )
        pref_page.add(health_group)

        # Database lock row
        self.lock_row = Adw.ActionRow(title="Database Lock (/var/lib/pacman/db.lck)", subtitle="Checking lock status...")
        self.btn_unlock = Gtk.Button(label="Unlock Database", css_classes=["destructive-action", "pill"])
        self.btn_unlock.connect("clicked", lambda _: self.on_troubleshoot("unlock_db") if self.on_troubleshoot else None)
        self.lock_row.add_suffix(self.btn_unlock)
        health_group.add(self.lock_row)

        # Keyring repair row
        row_keyring = Adw.ActionRow(
            title="Repair Arch and CachyOS Keyring",
            subtitle="Re-initialize and populate pacman GPG keys to resolve signature verification failures",
        )
        btn_keyring = Gtk.Button(label="Fix Keyring", css_classes=["pill"])
        btn_keyring.connect("clicked", lambda _: self.on_troubleshoot("repair_keyring") if self.on_troubleshoot else None)
        row_keyring.add_suffix(btn_keyring)
        health_group.add(row_keyring)

        # === 2. Mirror Benchmark & Optimizer Group ===
        mirror_group = Adw.PreferencesGroup(
            title="Mirror Benchmark and Speed Optimizer",
            description="Automatically benchmark and rank the fastest download servers into /etc/pacman.d/mirrorlist.",
        )
        pref_page.add(mirror_group)

        self.mirror_status_row = Adw.ActionRow(title="Active Mirrors", subtitle="Loading mirrorlist...")
        btn_rank = Gtk.Button(label="Rank and Update Mirrors", icon_name="network-server-symbolic", css_classes=["suggested-action", "pill"])
        btn_rank.connect("clicked", self._on_rank_clicked)
        self.mirror_status_row.add_suffix(btn_rank)
        mirror_group.add(self.mirror_status_row)

        # === 3. Package Cache Cleaner Group ===
        cache_group = Adw.PreferencesGroup(
            title="Pacman Package Cache",
            description="Manage downloaded package archives in /var/cache/pacman/pkg.",
        )
        pref_page.add(cache_group)

        self.cache_stats_row = Adw.ActionRow(title="Cache Disk Usage", subtitle="Calculating...")
        cache_group.add(self.cache_stats_row)

        row_prune = Adw.ActionRow(
            title="Clean Old Versions",
            subtitle="Remove all cached package versions except the most recent 2 (paccache -r)",
        )
        btn_prune = Gtk.Button(label="Clean", css_classes=["pill"])
        btn_prune.connect("clicked", lambda _: self.on_clean_cache("clean_cache") if self.on_clean_cache else None)
        row_prune.add_suffix(btn_prune)
        cache_group.add(row_prune)

        row_prune_1 = Adw.ActionRow(
            title="Aggressive Prune",
            subtitle="Keep only the 1 latest version of each package (paccache -rk1)",
        )
        btn_prune_1 = Gtk.Button(label="Prune (Keep 1)", css_classes=["pill"])
        btn_prune_1.connect("clicked", lambda _: self.on_clean_cache("clean_cache_all") if self.on_clean_cache else None)
        row_prune_1.add_suffix(btn_prune_1)
        cache_group.add(row_prune_1)

        # === 4. Orphan Packages Group ===
        self.orphans_group = Adw.PreferencesGroup(
            title="Orphan Packages",
            description="Packages that were installed as dependencies but are no longer required by any installed package.",
        )
        pref_page.add(self.orphans_group)

        self.orphans_summary_row = Adw.ActionRow(title="Detected Orphans", subtitle="Scanning...")
        self.btn_clean_orphans = Gtk.Button(
            label="Remove All Orphans",
            css_classes=["destructive-action", "pill"],
        )
        self.btn_clean_orphans.connect("clicked", self._on_clean_orphans_clicked)
        self.orphans_summary_row.add_suffix(self.btn_clean_orphans)
        self.orphans_group.add(self.orphans_summary_row)

        self.orphans_expander = Adw.ExpanderRow(title="View Orphaned Packages")
        self.orphans_group.add(self.orphans_expander)

        # === 5. Package Snapshots Group ===
        self.snapshot_group = Adw.PreferencesGroup(
            title="Package List Snapshots (Backup and Restore)",
            description="Export your explicitly installed package list for backup or batch reinstall on other systems.",
        )
        pref_page.add(self.snapshot_group)

        row_export = Adw.ActionRow(
            title="Create Package Snapshot",
            subtitle="Export all explicitly installed packages to a snapshot file",
        )
        btn_export = Gtk.Button(label="Export Snapshot", icon_name="document-save-symbolic", css_classes=["pill"])
        btn_export.connect("clicked", self._on_export_snapshot_clicked)
        row_export.add_suffix(btn_export)
        self.snapshot_group.add(row_export)

        self.snapshots_expander = Adw.ExpanderRow(title="Saved Snapshots")
        self.snapshot_group.add(self.snapshots_expander)

        # === 6. Recent Log / History Group ===
        self.log_group = Adw.PreferencesGroup(
            title="Recent Pacman History",
            description="Recent package installations, upgrades, and removals from /var/log/pacman.log.",
        )
        pref_page.add(self.log_group)

        self.log_expander = Adw.ExpanderRow(title="Transaction Log Entries")
        self.log_expander.set_expanded(True)
        self.log_group.add(self.log_expander)

    def refresh_status(self):
        """Update lock and mirror status."""
        # Check DB lock
        is_locked = self.alpm_mgr.is_db_locked()
        if is_locked:
            self.lock_row.set_subtitle("Database is LOCKED by /var/lib/pacman/db.lck (Click Unlock to remove)")
            self.btn_unlock.set_visible(True)
        else:
            self.lock_row.set_subtitle("Database is unlocked and healthy.")
            self.btn_unlock.set_visible(False)

        # Mirrors
        mirrors = self.mirror_mgr.get_current_mirrors(limit=3)
        if mirrors:
            self.mirror_status_row.set_subtitle(f"Top server: {mirrors[0]}")
        else:
            self.mirror_status_row.set_subtitle("No active mirrors found.")

        # Snapshots
        self._load_saved_snapshots()

    def set_cache_info(self, info: Dict[str, any]):
        """Update cache statistics display."""
        size_str = format_size(info.get("total_size", 0))
        count = info.get("pkg_count", 0)
        self.cache_stats_row.set_subtitle(escape(f"{size_str} across {count} cached package archives"))

    def set_orphans(self, orphans: List[PackageInfo]):
        """Update orphan packages display."""
        self.orphans = orphans

        for r in self._orphan_rows:
            self.orphans_expander.remove(r)
        self._orphan_rows.clear()

        total_size = sum(p.installed_size for p in orphans)
        size_str = format_size(total_size)

        if not orphans:
            self.orphans_summary_row.set_subtitle("No orphan packages found. Your system is tidy!")
            self.btn_clean_orphans.set_sensitive(False)
            self.orphans_expander.set_visible(False)
            return

        self.orphans_summary_row.set_subtitle(escape(f"{len(orphans)} unneeded packages ({size_str} disk space)"))
        self.btn_clean_orphans.set_sensitive(True)
        self.orphans_expander.set_visible(True)
        self.orphans_expander.set_subtitle(escape(f"{len(orphans)} packages"))

        for p in orphans:
            row = Adw.ActionRow(title=escape(p.name), subtitle=escape(f"Version: {p.version} • Size: {p.formatted_installed_size}"))
            self.orphans_expander.add_row(row)
            self._orphan_rows.append(row)

    def set_logs(self, logs: List[LogEntry]):
        """Update transaction log display."""
        for r in self._log_rows:
            self.log_expander.remove(r)
        self._log_rows.clear()

        if not logs:
            self.log_expander.set_subtitle("No recent log entries")
            return

        self.log_expander.set_subtitle(escape(f"{len(logs)} recent operations"))

        for entry in logs:
            row = Adw.ActionRow(
                title=escape(f"{entry.action.capitalize()}: {entry.pkg_name}"),
                subtitle=escape(f"{entry.timestamp}  •  {entry.version_info}"),
            )
            badge_class = "badge-installed"
            if entry.action == "removed":
                badge_class = "badge-orphan"
            elif entry.action == "upgraded":
                badge_class = "badge-update"

            badge = Gtk.Label(label=entry.action.upper(), css_classes=["badge-pill", badge_class])
            row.add_suffix(badge)
            self.log_expander.add_row(row)
            self._log_rows.append(row)

    def _load_saved_snapshots(self):
        """Populate saved snapshots list."""
        for r in self._snapshot_rows:
            self.snapshots_expander.remove(r)
        self._snapshot_rows.clear()

        snapshots = self.snapshot_mgr.list_saved_snapshots()
        self.snapshots_expander.set_subtitle(f"{len(snapshots)} saved snapshots")

        for snap in snapshots:
            row = Adw.ActionRow(
                title=escape(snap.name),
                subtitle=escape(f"{snap.package_count} packages • Created: {snap.created_at}"),
            )
            btn_restore = Gtk.Button(label="Restore", icon_name="document-revert-symbolic", css_classes=["pill"])
            btn_restore.connect("clicked", lambda _, s=snap: self._on_restore_clicked(s))
            row.add_suffix(btn_restore)
            self.snapshots_expander.add_row(row)
            self._snapshot_rows.append(row)

    def _on_export_snapshot_clicked(self, _btn):
        explicit_pkgs = [p.name for p in self.alpm_mgr.search_packages(scope="explicit", limit=5000)]
        snap = self.snapshot_mgr.export_snapshot(explicit_pkgs)
        self._load_saved_snapshots()

    def _on_restore_clicked(self, snap: SnapshotInfo):
        installed = [p.name for p in self.alpm_mgr.search_packages(scope="installed", limit=5000)]
        missing = self.snapshot_mgr.get_missing_packages(snap.packages, installed)
        if self.on_restore_snapshot:
            self.on_restore_snapshot(missing)

    def _on_rank_clicked(self, _btn):
        tool = "reflector" if self.mirror_mgr.has_reflector else ("rate-mirrors" if self.mirror_mgr.has_rate_mirrors else "auto")
        if self.on_rank_mirrors:
            self.on_rank_mirrors(tool, "Worldwide")

    def _on_clean_orphans_clicked(self, _btn):
        if self.orphans and self.on_remove_orphans:
            pkg_names = [p.name for p in self.orphans]
            self.on_remove_orphans(pkg_names)
