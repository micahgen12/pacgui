"""
Updates view for managing system updates and package upgrades.
"""

from typing import Callable, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, GObject, Gtk, Pango

from backend.models import UpdateInfo


def escape(text: Optional[str]) -> str:
    """Safely escape text for Pango markup in AdwActionRow."""
    if not text:
        return ""
    return GLib.markup_escape_text(str(text))


class UpdateRow(Adw.ActionRow):
    """Row displaying a pending package upgrade."""

    def __init__(
        self,
        update: UpdateInfo,
        on_update_single: Optional[Callable[[str], None]] = None,
    ):
        super().__init__()
        self.update_info = update

        self.set_title(escape(update.name))
        self.set_subtitle(escape(f"{update.old_version}  →  {update.new_version}"))

        # Repo badge
        if update.repo:
            repo_badge = Gtk.Label(
                label=update.repo,
                css_classes=["badge-pill", "badge-repo"],
            )
            self.add_suffix(repo_badge)

        # Download size
        if update.download_size > 0:
            size_label = Gtk.Label(
                label=update.formatted_size,
                css_classes=["code-pill"],
            )
            self.add_suffix(size_label)

        # Single update button
        if on_update_single:
            btn = Gtk.Button(icon_name="software-update-available-symbolic", css_classes=["flat", "circular"])
            btn.set_tooltip_text(f"Upgrade {update.name}")
            btn.connect("clicked", lambda _: on_update_single(update.name))
            self.add_suffix(btn)


class UpdatesView(Gtk.Box):
    """System updates panel."""

    def __init__(
        self,
        on_check_updates: Optional[Callable[[], None]] = None,
        on_upgrade_all: Optional[Callable[[], None]] = None,
        on_update_single: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.on_check_updates = on_check_updates
        self.on_upgrade_all = on_upgrade_all
        self.on_update_single = on_update_single
        self.updates: List[UpdateInfo] = []
        self._update_rows: List[Adw.ActionRow] = []

        self._setup_ui()

    def _setup_ui(self):
        # Header banner card
        header_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        header_card.set_margin_top(16)
        header_card.set_margin_start(20)
        header_card.set_margin_end(20)
        header_card.add_css_class("stat-card")
        self.append(header_card)

        # Title & count
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_box.set_hexpand(True)
        header_card.append(title_box)

        self.count_label = Gtk.Label(label="System Updates", css_classes=["title-2"], halign=Gtk.Align.START)
        title_box.append(self.count_label)

        self.summary_label = Gtk.Label(
            label="Check for new software releases from Arch and CachyOS repos.",
            css_classes=["subtitle"],
            halign=Gtk.Align.START,
        )
        title_box.append(self.summary_label)

        # Action buttons in banner
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header_card.append(btn_box)

        self.check_btn = Gtk.Button(label="Check Now", icon_name="view-refresh-symbolic", css_classes=["pill"])
        self.check_btn.connect("clicked", lambda _: self.on_check_updates() if self.on_check_updates else None)
        btn_box.append(self.check_btn)

        self.upgrade_all_btn = Gtk.Button(
            label="Upgrade System",
            icon_name="software-update-available-symbolic",
            css_classes=["suggested-action", "pill"],
        )
        self.upgrade_all_btn.connect("clicked", lambda _: self.on_upgrade_all() if self.on_upgrade_all else None)
        btn_box.append(self.upgrade_all_btn)

        # Scrolled view for updates list
        self.scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self.scrolled.set_margin_start(20)
        self.scrolled.set_margin_end(20)
        self.append(self.scrolled)

        self.pref_page = Adw.PreferencesPage()
        self.scrolled.set_child(self.pref_page)

        self.group = Adw.PreferencesGroup(title="Available Package Updates")
        self.pref_page.add(self.group)

        # Up-to-date status page
        self.status_page = Adw.StatusPage(
            icon_name="emblem-ok-symbolic",
            title="Your System is Up to Date",
            description="All packages in your local database match the latest repository releases.",
            vexpand=True,
            hexpand=True,
        )
        self.append(self.status_page)

    def set_updates(self, updates: List[UpdateInfo]):
        """Populate updates list."""
        self.updates = updates

        # Clear existing rows
        for r in self._update_rows:
            self.group.remove(r)
        self._update_rows.clear()

        if not updates:
            self.scrolled.set_visible(False)
            self.status_page.set_visible(True)
            self.upgrade_all_btn.set_sensitive(False)
            self.count_label.set_label("0 Updates Available")
            self.summary_label.set_label("Your packages are up to date.")
            return

        self.status_page.set_visible(False)
        self.scrolled.set_visible(True)
        self.upgrade_all_btn.set_sensitive(True)

        self.count_label.set_label(f"{len(updates)} Updates Available")
        self.summary_label.set_label(f"Upgrades ready for installation via pacman.")

        for item in updates:
            row = UpdateRow(item, on_update_single=self.on_update_single)
            self.group.add(row)
            self._update_rows.append(row)
