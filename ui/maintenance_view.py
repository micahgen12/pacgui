"""
Maintenance view for cache cleaning, orphan removal, and transaction history.
"""

from typing import Callable, Dict, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, GObject, Gtk, Pango

from backend.models import LogEntry, PackageInfo, format_size


def escape(text: Optional[str]) -> str:
    """Safely escape text for Pango markup in AdwActionRow."""
    if not text:
        return ""
    return GLib.markup_escape_text(str(text))


class MaintenanceView(Gtk.Box):
    """Maintenance dashboard for pacman cache, orphans, and log history."""

    def __init__(
        self,
        on_clean_cache: Optional[Callable[[str], None]] = None,
        on_remove_orphans: Optional[Callable[[List[str]], None]] = None,
        on_refresh: Optional[Callable[[], None]] = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.on_clean_cache = on_clean_cache
        self.on_remove_orphans = on_remove_orphans
        self.on_refresh = on_refresh
        self.orphans: List[PackageInfo] = []

        self._orphan_rows: List[Adw.ActionRow] = []
        self._log_rows: List[Adw.ActionRow] = []

        self._setup_ui()

    def _setup_ui(self):
        # Scrolled page
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self.append(scrolled)

        pref_page = Adw.PreferencesPage()
        pref_page.set_margin_top(16)
        pref_page.set_margin_bottom(24)
        scrolled.set_child(pref_page)

        # === 1. Cache Cleaner Group ===
        cache_group = Adw.PreferencesGroup(
            title="Pacman Package Cache",
            description="Manage downloaded package archives in /var/cache/pacman/pkg.",
        )
        pref_page.add(cache_group)

        # Cache stats row
        self.cache_stats_row = Adw.ActionRow(title="Cache Disk Usage", subtitle="Calculating...")
        cache_group.add(self.cache_stats_row)

        # Prune keep 2
        row_prune = Adw.ActionRow(
            title="Clean Old Versions",
            subtitle="Remove all cached package versions except the most recent 2 (paccache -r)",
        )
        btn_prune = Gtk.Button(label="Clean", css_classes=["pill"])
        btn_prune.connect("clicked", lambda _: self.on_clean_cache("clean_cache") if self.on_clean_cache else None)
        row_prune.add_suffix(btn_prune)
        cache_group.add(row_prune)

        # Prune keep 1
        row_prune_1 = Adw.ActionRow(
            title="Aggressive Prune",
            subtitle="Keep only the 1 latest version of each package (paccache -rk1)",
        )
        btn_prune_1 = Gtk.Button(label="Prune (Keep 1)", css_classes=["pill"])
        btn_prune_1.connect("clicked", lambda _: self.on_clean_cache("clean_cache_all") if self.on_clean_cache else None)
        row_prune_1.add_suffix(btn_prune_1)
        cache_group.add(row_prune_1)

        # === 2. Orphan Packages Group ===
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

        # === 3. Recent Log / History Group ===
        self.log_group = Adw.PreferencesGroup(
            title="Recent Pacman History",
            description="Recent package installations, upgrades, and removals from /var/log/pacman.log.",
        )
        pref_page.add(self.log_group)

        self.log_expander = Adw.ExpanderRow(title="Transaction Log Entries")
        self.log_expander.set_expanded(True)
        self.log_group.add(self.log_expander)

    def set_cache_info(self, info: Dict[str, any]):
        """Update cache statistics display."""
        size_str = format_size(info.get("total_size", 0))
        count = info.get("pkg_count", 0)
        self.cache_stats_row.set_subtitle(escape(f"{size_str} across {count} cached package archives"))

    def set_orphans(self, orphans: List[PackageInfo]):
        """Update orphan packages display."""
        self.orphans = orphans

        # Clear expander children
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

    def _on_clean_orphans_clicked(self, _btn):
        if self.orphans and self.on_remove_orphans:
            pkg_names = [p.name for p in self.orphans]
            self.on_remove_orphans(pkg_names)
