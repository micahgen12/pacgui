#!/usr/bin/env python3
"""
PacGUI: Modern GTK4 / Libadwaita Package Manager for Arch Linux & ALPM-based distributions.
"""

import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from backend.alpm_manager import AlpmManager
from backend.aur_manager import AurManager
from backend.flatpak_manager import FlatpakManager
from backend.mirror_manager import MirrorManager
from backend.snapshot_manager import SnapshotManager
from ui.window import MainWindow


class PacGuiApplication(Adw.Application):
    """Main Adw.Application instance."""

    def __init__(self):
        super().__init__(
            application_id="org.archlinux.PacGUI",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.alpm_mgr = AlpmManager()
        self.aur_mgr = AurManager()
        self.flatpak_mgr = FlatpakManager()
        self.mirror_mgr = MirrorManager()
        self.snapshot_mgr = SnapshotManager()
        self.main_window = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._load_css()
        self._setup_actions()
        self._setup_accels()

    def do_activate(self):
        if not self.main_window:
            self.main_window = MainWindow(
                self,
                self.alpm_mgr,
                self.aur_mgr,
                self.flatpak_mgr,
                self.mirror_mgr,
                self.snapshot_mgr,
            )
        self.main_window.present()

    def _load_css(self):
        """Load custom stylesheet."""
        css_path = os.path.join(os.path.dirname(__file__), "ui", "style.css")
        if os.path.exists(css_path):
            provider = Gtk.CssProvider()
            provider.load_from_path(css_path)
            display = Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display,
                    provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )

    def _setup_actions(self):
        """Register application actions."""
        action_updates = Gio.SimpleAction.new("check_updates", None)
        action_updates.connect("activate", lambda *_: self.main_window.check_updates(show_toast=True) if self.main_window else None)
        self.add_action(action_updates)

        action_cache = Gio.SimpleAction.new("clean_cache", None)
        action_cache.connect("activate", lambda *_: self.main_window._handle_clean_cache("clean_cache") if self.main_window else None)
        self.add_action(action_cache)

        action_find = Gio.SimpleAction.new("find_file", None)
        action_find.connect("activate", lambda *_: self.main_window._on_find_file_owner_clicked(None) if self.main_window else None)
        self.add_action(action_find)

        action_theme = Gio.SimpleAction.new("toggle_theme", None)
        action_theme.connect("activate", self._on_toggle_theme)
        self.add_action(action_theme)

        action_about = Gio.SimpleAction.new("about", None)
        action_about.connect("activate", self._on_show_about)
        self.add_action(action_about)

        action_quit = Gio.SimpleAction.new("quit", None)
        action_quit.connect("activate", lambda *_: self.quit())
        self.add_action(action_quit)

    def _setup_accels(self):
        """Setup keyboard shortcuts."""
        self.set_accels_for_action("app.quit", ["<Ctrl>Q"])
        self.set_accels_for_action("app.check_updates", ["<Ctrl>U"])
        self.set_accels_for_action("app.find_file", ["<Ctrl>O"])

    def _on_toggle_theme(self, _action, _param):
        """Toggle between Dark, Light, and Default color schemes."""
        style_mgr = Adw.StyleManager.get_default()
        if style_mgr.get_color_scheme() == Adw.ColorScheme.FORCE_DARK:
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        elif style_mgr.get_color_scheme() == Adw.ColorScheme.FORCE_LIGHT:
            style_mgr.set_color_scheme(Adw.ColorScheme.DEFAULT)
        else:
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)

    def _on_show_about(self, _action, _param):
        """Display Libadwaita About window."""
        about = Adw.AboutWindow(
            transient_for=self.main_window,
            application_name="PacGUI",
            application_icon="system-software-install-symbolic",
            developer_name="Antigravity Team & Arch Community",
            version="2.0.0",
            copyright="© 2026",
            issue_url="https://github.com/micahgen12/pacgui",
            website="https://github.com/micahgen12/pacgui",
            license_type=Gtk.License.GPL_3_0,
            comments="Fast, modern GTK4 / Libadwaita Graphical Package Manager for Arch Linux & ALPM distributions.",
        )
        about.present()


def main():
    app = PacGuiApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
