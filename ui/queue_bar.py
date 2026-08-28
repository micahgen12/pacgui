"""
Multi-package action queue bar and batch review dialog.
"""

from typing import Callable, Dict, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, GObject, Gtk, Pango

from backend.models import QueueItem, format_size


def escape(text: Optional[str]) -> str:
    if not text:
        return ""
    return GLib.markup_escape_text(str(text))


class BatchReviewDialog(Adw.Window):
    """Modal dialog displaying all queued changes before applying."""

    def __init__(
        self,
        parent_window: Gtk.Window,
        items: List[QueueItem],
        on_confirm: Callable[[], None],
    ):
        super().__init__(
            transient_for=parent_window,
            modal=True,
            title="Review Pending Changes",
            default_width=580,
            default_height=420,
        )
        self.items = items
        self.on_confirm = on_confirm

        self._setup_ui()

    def _setup_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_box.append(Gtk.Label(label="Batch Operations Queue", css_classes=["title"]))
        title_box.append(Gtk.Label(label=f"{len(self.items)} pending package operations", css_classes=["subtitle"]))
        header.set_title_widget(title_box)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(20)
        content.set_margin_end(20)
        toolbar_view.set_content(content)

        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        content.append(scrolled)

        pref_page = Adw.PreferencesPage()
        scrolled.set_child(pref_page)

        # 1. Installs Group
        installs = [i for i in self.items if i.action in ("install", "reinstall")]
        if installs:
            grp_install = Adw.PreferencesGroup(title=f"Packages to Install ({len(installs)})")
            pref_page.add(grp_install)
            for item in installs:
                row = Adw.ActionRow(title=escape(item.pkg_name), subtitle=escape(f"Repo: {item.repo}"))
                badge_class = "badge-aur" if item.is_aur else "badge-installed"
                badge = Gtk.Label(label=item.action.upper(), css_classes=["badge-pill", badge_class])
                row.add_suffix(badge)
                grp_install.add(row)

        # 2. Removals Group
        removals = [i for i in self.items if i.action == "remove"]
        if removals:
            grp_remove = Adw.PreferencesGroup(title=f"Packages to Remove ({len(removals)})")
            pref_page.add(grp_remove)
            for item in removals:
                row = Adw.ActionRow(title=escape(item.pkg_name), subtitle="Will remove with dependencies (-Rns)")
                badge = Gtk.Label(label="REMOVE", css_classes=["badge-pill", "badge-orphan"])
                row.add_suffix(badge)
                grp_remove.add(row)

        # Bottom buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)
        content.append(btn_box)

        btn_cancel = Gtk.Button(label="Cancel")
        btn_cancel.connect("clicked", lambda _: self.close())
        btn_box.append(btn_cancel)

        btn_apply = Gtk.Button(label="Apply All Changes", css_classes=["suggested-action", "pill"])
        btn_apply.connect("clicked", self._on_apply_clicked)
        btn_box.append(btn_apply)

    def _on_apply_clicked(self, _btn):
        self.close()
        if self.on_confirm:
            self.on_confirm()


class QueueBar(Gtk.Box):
    """Floating action bar at the bottom of the window for queued batch operations."""

    def __init__(
        self,
        parent_window: Gtk.Window,
        on_apply_queue: Callable[[List[QueueItem]], None],
    ):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.parent_window = parent_window
        self.on_apply_queue = on_apply_queue
        self._queue: Dict[str, QueueItem] = {}

        self._setup_ui()
        self.set_visible(False)

    def _setup_ui(self):
        self.add_css_class("stat-card")
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.set_margin_bottom(12)
        self.set_margin_top(6)

        icon = Gtk.Image.new_from_icon_name("starred-symbolic")
        self.append(icon)

        # Status text
        self.label = Gtk.Label(label="0 operations queued", hexpand=True, halign=Gtk.Align.START)
        self.label.set_markup("<b>Queue:</b> 0 items")
        self.append(self.label)

        # Clear button
        btn_clear = Gtk.Button(label="Clear", css_classes=["flat"])
        btn_clear.connect("clicked", lambda _: self.clear())
        self.append(btn_clear)

        # Review & Apply button
        self.btn_review = Gtk.Button(
            label="Review & Apply",
            icon_name="emblem-ok-symbolic",
            css_classes=["suggested-action", "pill"],
        )
        self.btn_review.connect("clicked", self._on_review_clicked)
        self.append(self.btn_review)

    def add_item(self, item: QueueItem):
        """Add or update an item in the queue."""
        self._queue[item.pkg_name] = item
        self._update_display()

    def remove_item(self, pkg_name: str):
        """Remove item from queue."""
        if pkg_name in self._queue:
            del self._queue[pkg_name]
            self._update_display()

    def clear(self):
        """Clear all queued items."""
        self._queue.clear()
        self._update_display()

    def get_items(self) -> List[QueueItem]:
        """Get all queued items."""
        return list(self._queue.values())

    def _update_display(self):
        """Update count label and visibility."""
        items = list(self._queue.values())
        if not items:
            self.set_visible(False)
            return

        self.set_visible(True)
        installs = sum(1 for i in items if i.action in ("install", "reinstall"))
        removals = sum(1 for i in items if i.action == "remove")

        summary = []
        if installs:
            summary.append(f"{installs} to install")
        if removals:
            summary.append(f"{removals} to remove")

        text = ", ".join(summary)
        self.label.set_markup(f"<b>Pending Queue:</b> {escape(text)}")

    def _on_review_clicked(self, _btn):
        items = self.get_items()
        if not items:
            return

        def _confirmed():
            if self.on_apply_queue:
                self.on_apply_queue(items)
            self.clear()

        dialog = BatchReviewDialog(self.parent_window, items, _confirmed)
        dialog.present()
