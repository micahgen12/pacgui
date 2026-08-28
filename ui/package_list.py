"""
Package list view showing filterable, searchable packages with sorting and queue controls.
"""

from typing import Callable, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, GObject, Gtk, Pango

from backend.models import PackageInfo, QueueItem


class PackageRow(Gtk.ListBoxRow):
    """Custom ListBoxRow representing a single package item."""

    def __init__(
        self,
        pkg: PackageInfo,
        on_action: Optional[Callable[[str, PackageInfo, bool], None]] = None,
        on_queue: Optional[Callable[[QueueItem], None]] = None,
    ):
        super().__init__()
        self.pkg = pkg
        self.on_action = on_action
        self.on_queue = on_queue

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

        # Top row in mid_box: Name + Version + Repo Badge + Size
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        mid_box.append(top_row)

        name_label = Gtk.Label(label=self.pkg.name, css_classes=["package-title"], halign=Gtk.Align.START)
        top_row.append(name_label)

        ver_label = Gtk.Label(label=self.pkg.version, css_classes=["package-version"], halign=Gtk.Align.START)
        top_row.append(ver_label)

        repo_class = "badge-aur" if self.pkg.is_aur else "badge-repo"
        repo_badge = Gtk.Label(label=self.pkg.repo, css_classes=["badge-pill", repo_class], halign=Gtk.Align.START)
        top_row.append(repo_badge)

        if self.pkg.installed_size > 0 or self.pkg.download_size > 0:
            sz_str = self.pkg.formatted_installed_size if self.pkg.is_installed else self.pkg.formatted_download_size
            sz_label = Gtk.Label(label=sz_str, css_classes=["caption"], halign=Gtk.Align.START)
            sz_label.set_opacity(0.7)
            top_row.append(sz_label)

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

        # Right side: Queue button & Direct Action Button
        btn_q = Gtk.Button(icon_name="list-add-symbolic", css_classes=["flat", "circular"])
        btn_q.set_tooltip_text("Add to Action Queue")
        btn_q.connect("clicked", self._on_queue_clicked)
        box.append(btn_q)

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

    def _on_queue_clicked(self, _btn):
        if self.on_queue:
            act = "remove" if self.pkg.is_installed else "install"
            item = QueueItem(
                pkg_name=self.pkg.name,
                action=act,
                repo=self.pkg.repo,
                is_aur=self.pkg.is_aur,
                size=self.pkg.installed_size or self.pkg.download_size,
            )
            self.on_queue(item)

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
        on_queue: Optional[Callable[[QueueItem], None]] = None,
        on_sort_changed: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.on_selected = on_selected
        self.on_action = on_action
        self.on_queue = on_queue
        self.on_sort_changed = on_sort_changed
        self.packages: List[PackageInfo] = []

        self._setup_ui()

    def _setup_ui(self):
        # Sort header bar
        sort_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sort_bar.set_margin_start(12)
        sort_bar.set_margin_end(12)
        sort_bar.set_margin_top(6)
        sort_bar.set_margin_bottom(6)
        self.append(sort_bar)

        self.count_badge = Gtk.Label(label="0 packages", css_classes=["caption"], halign=Gtk.Align.START, hexpand=True)
        sort_bar.append(self.count_badge)

        sort_lbl = Gtk.Label(label="Sort:", css_classes=["caption"])
        sort_bar.append(sort_lbl)

        sort_options = [
            "Name (A-Z)",
            "Name (Z-A)",
            "Size (Largest First)",
            "Size (Smallest First)",
            "Build Date (Newest)",
        ]
        self.sort_dropdown = Gtk.DropDown.new_from_strings(sort_options)
        self.sort_dropdown.connect("notify::selected", self._on_sort_selected)
        sort_bar.append(self.sort_dropdown)

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
        self.count_badge.set_label(f"{len(packages)} packages")

        while child := self.list_box.get_first_child():
            self.list_box.remove(child)

        if not packages:
            self.scrolled.set_visible(False)
            self.status_page.set_visible(True)
            return

        self.status_page.set_visible(False)
        self.scrolled.set_visible(True)

        for pkg in packages:
            row = PackageRow(pkg, on_action=self.on_action, on_queue=self.on_queue)
            self.list_box.append(row)

        first = self.list_box.get_row_at_index(0)
        if first:
            self.list_box.select_row(first)

    def _on_sort_selected(self, dropdown, _param):
        idx = dropdown.get_selected()
        mapping = {
            0: "name_asc",
            1: "name_desc",
            2: "size_desc",
            3: "size_asc",
            4: "date_desc",
        }
        key = mapping.get(idx, "name_asc")
        if self.on_sort_changed:
            self.on_sort_changed(key)

    def _on_row_selected(self, _box, row):
        if row and isinstance(row, PackageRow) and self.on_selected:
            self.on_selected(row.pkg)
