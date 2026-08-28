"""
Flatpak applications management view.
"""

import threading
from typing import Callable, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, GObject, Gtk, Pango

from backend.flatpak_manager import FlatpakManager
from backend.models import FlatpakApp


def escape(text: Optional[str]) -> str:
    if not text:
        return ""
    return GLib.markup_escape_text(str(text))


class FlatpakRow(Adw.ActionRow):
    """Row displaying a single Flatpak application."""

    def __init__(
        self,
        app: FlatpakApp,
        on_action: Optional[Callable[[str, FlatpakApp], None]] = None,
    ):
        super().__init__()
        self.app = app
        self.on_action = on_action

        self.set_title(escape(app.name))
        sub = f"{app.app_id}"
        if app.version:
            sub += f" • v{app.version}"
        if app.desc:
            sub += f" — {app.desc}"
        self.set_subtitle(escape(sub))

        # Origin badge
        origin_badge = Gtk.Label(label=app.origin or "flathub", css_classes=["badge-pill", "badge-repo"])
        self.add_suffix(origin_badge)

        # Installed badge / Action button
        if app.is_installed:
            inst_badge = Gtk.Label(label="Installed", css_classes=["badge-pill", "badge-installed"])
            self.add_suffix(inst_badge)

            btn_del = Gtk.Button(icon_name="user-trash-symbolic", css_classes=["flat", "circular"])
            btn_del.set_tooltip_text(f"Uninstall {app.name}")
            btn_del.connect("clicked", lambda _: self._on_btn_clicked("remove"))
            self.add_suffix(btn_del)
        else:
            btn_inst = Gtk.Button(icon_name="document-save-symbolic", css_classes=["flat", "circular"])
            btn_inst.set_tooltip_text(f"Install {app.name}")
            btn_inst.connect("clicked", lambda _: self._on_btn_clicked("install"))
            self.add_suffix(btn_inst)

    def _on_btn_clicked(self, action: str):
        if self.on_action:
            self.on_action(action, self.app)


class FlatpakView(Gtk.Box):
    """Flatpak application hub."""

    def __init__(
        self,
        flatpak_mgr: FlatpakManager,
        on_action: Optional[Callable[[str, FlatpakApp], None]] = None,
        on_update_all: Optional[Callable[[], None]] = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.flatpak_mgr = flatpak_mgr
        self.on_action = on_action
        self.on_update_all = on_update_all

        self._installed_apps: List[FlatpakApp] = []
        self._search_apps: List[FlatpakApp] = []
        self._rows: List[Adw.ActionRow] = []

        self._setup_ui()
        self.load_installed()

    def _setup_ui(self):
        # Header banner card
        header_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        header_card.set_margin_top(16)
        header_card.set_margin_start(20)
        header_card.set_margin_end(20)
        header_card.add_css_class("stat-card")
        self.append(header_card)

        # Title
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_box.set_hexpand(True)
        header_card.append(title_box)

        self.title_lbl = Gtk.Label(label="Flatpak Hub", css_classes=["title-2"], halign=Gtk.Align.START)
        title_box.append(self.title_lbl)

        self.subtitle_lbl = Gtk.Label(
            label="Sandboxed desktop applications from Flathub and configured remotes.",
            css_classes=["subtitle"],
            halign=Gtk.Align.START,
        )
        title_box.append(self.subtitle_lbl)

        # Action button
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header_card.append(btn_box)

        self.btn_update = Gtk.Button(
            label="Update Flatpaks",
            icon_name="software-update-available-symbolic",
            css_classes=["pill"],
        )
        self.btn_update.connect("clicked", lambda _: self.on_update_all() if self.on_update_all else None)
        btn_box.append(self.btn_update)

        # Search Bar
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        search_box.set_margin_start(20)
        search_box.set_margin_end(20)
        self.append(search_box)

        self.search_entry = Gtk.SearchEntry(placeholder_text="Search Flathub apps (e.g. Discord, Blender, Spotify)...")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self._on_search_changed)
        search_box.append(self.search_entry)

        # Scrolled View
        self.scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self.scrolled.set_margin_start(20)
        self.scrolled.set_margin_end(20)
        self.append(self.scrolled)

        self.pref_page = Adw.PreferencesPage()
        self.scrolled.set_child(self.pref_page)

        self.group = Adw.PreferencesGroup(title="Installed Flatpak Applications")
        self.pref_page.add(self.group)

        # Status page placeholder
        self.status_page = Adw.StatusPage(
            icon_name="application-x-executable-symbolic",
            title="No Flatpak Applications Found",
            description="Search for apps on Flathub or install Flatpak runtime.",
            vexpand=True,
            hexpand=True,
        )
        self.append(self.status_page)
        self.status_page.set_visible(False)

    def load_installed(self):
        """Fetch and render installed Flatpak apps."""
        def _bg():
            apps = self.flatpak_mgr.get_installed_apps()

            def _ui():
                self._installed_apps = apps
                if not self.search_entry.get_text().strip():
                    self.group.set_title(f"Installed Flatpak Applications ({len(apps)})")
                    self._render_apps(apps)

            GLib.idle_add(_ui)

        threading.Thread(target=_bg, daemon=True).start()

    def _on_search_changed(self, entry):
        """Search Flathub when text is entered."""
        query = entry.get_text().strip()
        if not query:
            self.group.set_title(f"Installed Flatpak Applications ({len(self._installed_apps)})")
            self._render_apps(self._installed_apps)
            return

        def _bg_search():
            res = self.flatpak_mgr.search_apps(query, limit=30)

            def _ui_res():
                self._search_apps = res
                self.group.set_title(f"Search Results for '{query}' ({len(res)})")
                self._render_apps(res)

            GLib.idle_add(_ui_res)

        threading.Thread(target=_bg_search, daemon=True).start()

    def _render_apps(self, apps: List[FlatpakApp]):
        """Render list of Flatpak applications."""
        for r in self._rows:
            self.group.remove(r)
        self._rows.clear()

        if not apps:
            self.scrolled.set_visible(False)
            self.status_page.set_visible(True)
            return

        self.status_page.set_visible(False)
        self.scrolled.set_visible(True)

        for app in apps:
            row = FlatpakRow(app, on_action=self.on_action)
            self.group.add(row)
            self._rows.append(row)
