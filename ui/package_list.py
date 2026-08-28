"""
Package list view showing filterable, searchable packages with quick action controls.
"""

from typing import Callable, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, GObject, Gtk, Pango

from backend.models import PackageInfo


class PackageRow(Gtk.ListBoxRow):
    """Custom ListBoxRow representing a single package item."""

    def __init__(
        self,
        pkg: PackageInfo,
        on_action: Optional[Callable[[str, PackageInfo, bool], None]] = None,
    ):
        super().__init__()
        self.pkg = pkg
        self.on_action = on_action

        self._setup_ui()

    def _setup_ui(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        self.set_child(box)

        # Status Icon on the left
        if self.pkg.is_installed:
            if self.pkg.is_orphan:
                status_icon = Gtk.Image.new_from_icon_name("user-trash-symbolic")
                status_icon.add_css_class("badge-orphan")
            elif self.pkg.has_update:
                status_icon = Gtk.Image.new_from_icon_name("software-update-available-symbolic")
                status_icon.add_css_class("badge-update")
            else:
                status_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
                status_icon.add_css_class("badge-installed")
        else:
            status_icon = Gtk.Image.new_from_icon_name("package-x-generic-symbolic")
            status_icon.set_opacity(0.4)

        status_icon.set_pixel_size(24)
        box.append(status_icon)

        # Middle Box: Name, Version, Description
        mid_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        mid_box.set_hexpand(True)
        box.append(mid_box)

        # Top row in mid_box: Name + Version + Repo Badge
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        mid_box.append(top_row)

        name_label = Gtk.Label(label=self.pkg.name, css_classes=["package-title"], halign=Gtk.Align.START)
        top_row.append(name_label)

        ver_label = Gtk.Label(label=self.pkg.version, css_classes=["package-version"], halign=Gtk.Align.START)
        top_row.append(ver_label)

        # Repo Badge
        repo_class = "badge-aur" if self.pkg.is_aur else "badge-repo"
        repo_badge = Gtk.Label(label=self.pkg.repo, css_classes=["badge-pill", repo_class], halign=Gtk.Align.START)
        top_row.append(repo_badge)

        # Description row
        desc_text = self.pkg.desc or "No description."
        desc_label = Gtk.Label(
            label=desc_text,
            css_classes=["package-desc"],
            halign=Gtk.Align.START,
            ellipsize=Pango.EllipsizeMode.END,
            lines=1,
        )
        mid_box.append(desc_label)

        # Right side: Quick Action Button
        if self.pkg.is_installed:
            btn = Gtk.Button(icon_name="user-trash-symbolic", css_classes=["flat", "circular"])
            btn.set_tooltip_text("Remove Package")
            btn.connect("clicked", self._on_quick_remove)
            box.append(btn)
        else:
            btn = Gtk.Button(icon_name="document-save-symbolic", css_classes=["flat", "circular"])
            btn.set_tooltip_text("Install Package")
            btn.connect("clicked", self._on_quick_install)
            box.append(btn)

    def _on_quick_install(self, _btn):
        if self.on_action:
            action = "aur_install" if self.pkg.is_aur else "install"
            self.on_action(action, self.pkg, False)

    def _on_quick_remove(self, _btn):
        if self.on_action:
            self.on_action("remove", self.pkg, True)


class PackageListView(Gtk.Box):
    """List container displaying searched/filtered packages."""

    def __init__(
        self,
        on_selected: Optional[Callable[[PackageInfo], None]] = None,
        on_action: Optional[Callable[[str, PackageInfo, bool], None]] = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.on_selected = on_selected
        self.on_action = on_action
        self.packages: List[PackageInfo] = []

        self._setup_ui()

    def _setup_ui(self):
        # Scrolled window containing list box
        self.scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self.append(self.scrolled)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.add_css_class("navigation-sidebar")
        self.list_box.connect("row-selected", self._on_row_selected)
        self.scrolled.set_child(self.list_box)

        # Empty state status page
        self.status_page = Adw.StatusPage(
            icon_name="system-search-symbolic",
            title="No Packages Found",
            description="Try searching for a different name or changing filters.",
            vexpand=True,
            hexpand=True,
        )
        self.status_page.set_visible(False)
        self.append(self.status_page)

    def set_packages(self, packages: List[PackageInfo]):
        """Load and display package list."""
        self.packages = packages

        # Clear existing rows
        while child := self.list_box.get_first_child():
            self.list_box.remove(child)

        if not packages:
            self.scrolled.set_visible(False)
            self.status_page.set_visible(True)
            return

        self.status_page.set_visible(False)
        self.scrolled.set_visible(True)

        for pkg in packages:
            row = PackageRow(pkg, on_action=self.on_action)
            self.list_box.append(row)

        # Select first row by default if available
        first = self.list_box.get_row_at_index(0)
        if first:
            self.list_box.select_row(first)

    def _on_row_selected(self, _box, row):
        if row and isinstance(row, PackageRow) and self.on_selected:
            self.on_selected(row.pkg)
