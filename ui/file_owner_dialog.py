"""
File Owner Inspector dialog for finding which package owns a specific file on the filesystem.
"""

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, GObject, Gtk, Pango

from backend.alpm_manager import AlpmManager
from backend.models import PackageInfo


def escape(text: Optional[str]) -> str:
    if not text:
        return ""
    return GLib.markup_escape_text(str(text))


class FileOwnerDialog(Adw.Window):
    """Dialog to find which package owns a specific file."""

    def __init__(
        self,
        parent_window: Gtk.Window,
        alpm_mgr: AlpmManager,
        on_navigate: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(
            transient_for=parent_window,
            modal=True,
            title="Find File Owner",
            default_width=520,
            default_height=380,
        )
        self.alpm_mgr = alpm_mgr
        self.on_navigate = on_navigate
        self.found_pkg: Optional[PackageInfo] = None

        self._setup_ui()

    def _setup_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_box.append(Gtk.Label(label="File Owner Lookup", css_classes=["title"]))
        title_box.append(Gtk.Label(label="Inspect which package installed a specific file", css_classes=["subtitle"]))
        header.set_title_widget(title_box)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(20)
        content.set_margin_end(20)
        toolbar_view.set_content(content)

        # Input row
        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        content.append(input_box)

        self.entry = Gtk.Entry(placeholder_text="Enter file path (e.g. /usr/bin/bash or libssl.so)...")
        self.entry.set_hexpand(True)
        self.entry.connect("activate", self._on_inspect_clicked)
        input_box.append(self.entry)

        btn_inspect = Gtk.Button(label="Inspect", css_classes=["suggested-action", "pill"])
        btn_inspect.connect("clicked", self._on_inspect_clicked)
        input_box.append(btn_inspect)

        # Result display
        self.result_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.result_card.add_css_class("stat-card")
        self.result_card.set_visible(False)
        content.append(self.result_card)

        self.pkg_title = Gtk.Label(label="", css_classes=["title-2"], halign=Gtk.Align.START)
        self.result_card.append(self.pkg_title)

        self.pkg_desc = Gtk.Label(label="", css_classes=["subtitle"], wrap=True, halign=Gtk.Align.START)
        self.result_card.append(self.pkg_desc)

        self.pkg_details = Gtk.Label(label="", css_classes=["caption"], halign=Gtk.Align.START)
        self.result_card.append(self.pkg_details)

        # View package button
        self.btn_view_pkg = Gtk.Button(
            label="View in Package Details",
            icon_name="go-next-symbolic",
            css_classes=["pill"],
            halign=Gtk.Align.START,
        )
        self.btn_view_pkg.connect("clicked", self._on_view_pkg_clicked)
        self.result_card.append(self.btn_view_pkg)

        # Not found message
        self.not_found_label = Gtk.Label(
            label="No matching package found for this path.",
            css_classes=["destructive-action"],
            halign=Gtk.Align.START,
        )
        self.not_found_label.set_visible(False)
        content.append(self.not_found_label)

    def _on_inspect_clicked(self, _btn):
        path = self.entry.get_text().strip()
        if not path:
            return

        pkg = self.alpm_mgr.get_file_owner(path)
        self.found_pkg = pkg

        if pkg:
            self.not_found_label.set_visible(False)
            self.result_card.set_visible(True)
            self.pkg_title.set_label(f"Owned by: {pkg.name}")
            self.pkg_desc.set_label(pkg.desc or "No description.")
            self.pkg_details.set_label(
                f"Version: {pkg.version} • Repo: {pkg.repo} • Installed Size: {pkg.formatted_installed_size}"
            )
        else:
            self.result_card.set_visible(False)
            self.not_found_label.set_label(f"No installed package owns '{path}'.")
            self.not_found_label.set_visible(True)

    def _on_view_pkg_clicked(self, _btn):
        if self.found_pkg and self.on_navigate:
            self.on_navigate(self.found_pkg.name)
            self.close()
