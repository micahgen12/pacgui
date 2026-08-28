"""
Package detail view for inspecting package metadata, dependencies, files, and actions.
"""

from typing import Callable, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, GObject, Gtk, Pango

from backend.models import PackageInfo, format_size


def escape(text: Optional[str]) -> str:
    """Safely escape text for Pango markup in AdwActionRow."""
    if not text:
        return ""
    return GLib.markup_escape_text(str(text))


class PackageDetailView(Gtk.Box):
    """Detailed view for an individual package."""

    def __init__(
        self,
        on_action: Optional[Callable[[str, PackageInfo, bool], None]] = None,
        on_select_dep: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.on_action = on_action  # on_action(action_type, pkg_info, cascade)
        self.on_select_dep = on_select_dep  # on_select_dep(pkg_name)
        self.current_pkg: Optional[PackageInfo] = None

        self._dep_rows: List[Adw.ActionRow] = []
        self._optdep_rows: List[Adw.ActionRow] = []
        self._reqby_rows: List[Adw.ActionRow] = []
        self._file_rows: List[Adw.ActionRow] = []

        self._setup_ui()

    def _setup_ui(self):
        # Empty placeholder state
        self.status_page = Adw.StatusPage(
            icon_name="system-software-install-symbolic",
            title="Select a Package",
            description="Choose a package from the list to view details, dependencies, files, and actions.",
            vexpand=True,
            hexpand=True,
        )
        self.append(self.status_page)

        # Scrolled container for detail content
        self.scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_visible(False)
        self.append(self.scrolled)

        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.content_box.set_margin_top(20)
        self.content_box.set_margin_bottom(24)
        self.content_box.set_margin_start(24)
        self.content_box.set_margin_end(24)
        self.scrolled.set_child(self.content_box)

        # --- Header Hero Section ---
        hero_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.content_box.append(hero_box)

        # Top row: Package Name & Status Badges
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hero_box.append(title_row)

        self.name_label = Gtk.Label(
            label="",
            css_classes=["title-1"],
            halign=Gtk.Align.START,
            hexpand=True,
            selectable=True,
        )
        title_row.append(self.name_label)

        self.badges_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_row.append(self.badges_box)

        # Version & Repo Subtitle
        sub_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hero_box.append(sub_row)

        self.version_label = Gtk.Label(
            label="",
            css_classes=["package-version"],
            halign=Gtk.Align.START,
            selectable=True,
        )
        sub_row.append(self.version_label)

        # Description
        self.desc_label = Gtk.Label(
            label="",
            css_classes=["package-desc"],
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD,
            halign=Gtk.Align.START,
            selectable=True,
        )
        hero_box.append(self.desc_label)

        # Action Buttons Bar
        self.actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.actions_box.set_margin_top(6)
        hero_box.append(self.actions_box)

        self.install_btn = Gtk.Button(label="Install", css_classes=["suggested-action", "pill"])
        self.install_btn.connect("clicked", self._on_install_clicked)
        self.actions_box.append(self.install_btn)

        self.reinstall_btn = Gtk.Button(label="Reinstall", css_classes=["pill"])
        self.reinstall_btn.connect("clicked", self._on_reinstall_clicked)
        self.actions_box.append(self.reinstall_btn)

        self.remove_btn = Gtk.Button(label="Remove", css_classes=["destructive-action", "pill"])
        self.remove_btn.connect("clicked", self._on_remove_clicked)
        self.actions_box.append(self.remove_btn)

        self.cascade_check = Gtk.CheckButton(label="Remove dependencies (-Rns)", active=True)
        self.actions_box.append(self.cascade_check)

        self.website_btn = Gtk.LinkButton(label="Website")
        self.website_btn.set_halign(Gtk.Align.END)
        self.website_btn.set_hexpand(True)
        self.actions_box.append(self.website_btn)

        # --- Preferences Groups / Details Section ---
        self.pref_page = Adw.PreferencesPage()
        self.content_box.append(self.pref_page)

        # 1. Details Group
        self.details_group = Adw.PreferencesGroup(title="Package Information")
        self.pref_page.add(self.details_group)

        self.row_repo = Adw.ActionRow(title="Repository")
        self.details_group.add(self.row_repo)

        self.row_packager = Adw.ActionRow(title="Maintainer / Packager")
        self.details_group.add(self.row_packager)

        self.row_licenses = Adw.ActionRow(title="License")
        self.details_group.add(self.row_licenses)

        self.row_arch = Adw.ActionRow(title="Architecture")
        self.details_group.add(self.row_arch)

        self.row_size_installed = Adw.ActionRow(title="Installed Size")
        self.details_group.add(self.row_size_installed)

        self.row_size_download = Adw.ActionRow(title="Download Size")
        self.details_group.add(self.row_size_download)

        self.row_dates = Adw.ActionRow(title="Build / Install Date")
        self.details_group.add(self.row_dates)

        # 2. Dependencies Group
        self.deps_group = Adw.PreferencesGroup(title="Dependencies")
        self.pref_page.add(self.deps_group)

        # 3. Optional Dependencies Group
        self.optdeps_group = Adw.PreferencesGroup(title="Optional Dependencies")
        self.pref_page.add(self.optdeps_group)

        # 4. Required By Group
        self.reqby_group = Adw.PreferencesGroup(title="Required By (Dependents)")
        self.pref_page.add(self.reqby_group)

        # 5. Provides / Conflicts / Replaces Group
        self.relations_group = Adw.PreferencesGroup(title="Package Relations")
        self.pref_page.add(self.relations_group)

        self.row_provides = Adw.ActionRow(title="Provides")
        self.relations_group.add(self.row_provides)

        self.row_conflicts = Adw.ActionRow(title="Conflicts")
        self.relations_group.add(self.row_conflicts)

        self.row_replaces = Adw.ActionRow(title="Replaces")
        self.relations_group.add(self.row_replaces)

        # 6. Installed Files Group
        self.files_group = Adw.PreferencesGroup(title="Installed Files")
        self.pref_page.add(self.files_group)

        self.files_expander = Adw.ExpanderRow(title="View Package Files")
        self.files_group.add(self.files_expander)

    def display_package(self, pkg: PackageInfo):
        """Populate view with package metadata."""
        self.current_pkg = pkg
        self.status_page.set_visible(False)
        self.scrolled.set_visible(True)

        self.name_label.set_label(pkg.name)
        self.version_label.set_label(f"Version: {pkg.version} • Repo: {pkg.repo}")
        self.desc_label.set_label(pkg.desc or "No description provided.")

        # Update badges
        while child := self.badges_box.get_first_child():
            self.badges_box.remove(child)

        # Installed badge
        if pkg.is_installed:
            badge = Gtk.Label(label="Installed", css_classes=["badge-pill", "badge-installed"])
            self.badges_box.append(badge)
            if pkg.is_orphan:
                orph_badge = Gtk.Label(label="Orphan", css_classes=["badge-pill", "badge-orphan"])
                self.badges_box.append(orph_badge)
            elif pkg.is_explicit:
                exp_badge = Gtk.Label(label="Explicit", css_classes=["badge-pill", "badge-repo"])
                self.badges_box.append(exp_badge)
        else:
            not_badge = Gtk.Label(label="Not Installed", css_classes=["badge-pill", "code-pill"])
            self.badges_box.append(not_badge)

        if pkg.is_aur:
            aur_badge = Gtk.Label(
                label=f"AUR (Votes: {pkg.aur_votes})",
                css_classes=["badge-pill", "badge-aur"],
            )
            self.badges_box.append(aur_badge)

        if pkg.has_update:
            up_badge = Gtk.Label(
                label=f"Update: {pkg.new_version}",
                css_classes=["badge-pill", "badge-update"],
            )
            self.badges_box.append(up_badge)

        # Website
        if pkg.url:
            self.website_btn.set_uri(pkg.url)
            self.website_btn.set_visible(True)
        else:
            self.website_btn.set_visible(False)

        # Action buttons state
        if pkg.is_installed:
            self.install_btn.set_visible(False)
            self.reinstall_btn.set_visible(True)
            self.remove_btn.set_visible(True)
            self.cascade_check.set_visible(True)
        else:
            self.install_btn.set_visible(True)
            self.reinstall_btn.set_visible(False)
            self.remove_btn.set_visible(False)
            self.cascade_check.set_visible(False)

        # Info rows with safe escaping
        self.row_repo.set_subtitle(escape(pkg.repo))
        self.row_packager.set_subtitle(escape(pkg.packager or "Unknown"))
        self.row_licenses.set_subtitle(escape(", ".join(pkg.licenses) if pkg.licenses else "None"))
        self.row_arch.set_subtitle(escape(pkg.arch or "Any"))
        self.row_size_installed.set_subtitle(escape(pkg.formatted_installed_size))
        self.row_size_download.set_subtitle(escape(pkg.formatted_download_size))

        date_str = ""
        if pkg.build_date:
            date_str += f"Built: {pkg.build_date.strftime('%Y-%m-%d %H:%M')}  "
        if pkg.install_date:
            date_str += f"Installed: {pkg.install_date.strftime('%Y-%m-%d %H:%M')}"
        self.row_dates.set_subtitle(escape(date_str or "N/A"))

        # Relations
        self.row_provides.set_subtitle(escape(", ".join(pkg.provides) if pkg.provides else "None"))
        self.row_conflicts.set_subtitle(escape(", ".join(pkg.conflicts) if pkg.conflicts else "None"))
        self.row_replaces.set_subtitle(escape(", ".join(pkg.replaces) if pkg.replaces else "None"))

        # Dynamic Groups: Dependencies
        self._populate_deps_group(pkg)
        self._populate_optdeps_group(pkg)
        self._populate_reqby_group(pkg)
        self._populate_files_group(pkg)

    def _populate_deps_group(self, pkg: PackageInfo):
        """Populate dependencies list."""
        for r in self._dep_rows:
            self.deps_group.remove(r)
        self._dep_rows.clear()

        if not pkg.depends:
            row = Adw.ActionRow(title="None", subtitle="No dependencies required")
            self.deps_group.add(row)
            self._dep_rows.append(row)
            return

        for dep in pkg.depends:
            clean_name = dep.split(">")[0].split("<")[0].split("=")[0].strip()
            row = Adw.ActionRow(title=escape(dep))
            row.set_activatable(True)
            nav_btn = Gtk.Button(icon_name="go-next-symbolic", css_classes=["flat", "circular"])
            nav_btn.connect("clicked", lambda _, name=clean_name: self._on_dep_clicked(name))
            row.add_suffix(nav_btn)
            row.connect("activated", lambda _, name=clean_name: self._on_dep_clicked(name))
            self.deps_group.add(row)
            self._dep_rows.append(row)

    def _populate_optdeps_group(self, pkg: PackageInfo):
        """Populate optional dependencies."""
        for r in self._optdep_rows:
            self.optdeps_group.remove(r)
        self._optdep_rows.clear()

        if not pkg.optdepends:
            row = Adw.ActionRow(title="None", subtitle="No optional dependencies")
            self.optdeps_group.add(row)
            self._optdep_rows.append(row)
            return

        for opt in pkg.optdepends:
            parts = opt.split(":", 1)
            title = parts[0].strip()
            sub = parts[1].strip() if len(parts) > 1 else ""
            row = Adw.ActionRow(title=escape(title), subtitle=escape(sub))
            row.set_activatable(True)
            clean_name = title.split(">")[0].split("<")[0].split("=")[0].strip()
            row.connect("activated", lambda _, name=clean_name: self._on_dep_clicked(name))
            self.optdeps_group.add(row)
            self._optdep_rows.append(row)

    def _populate_reqby_group(self, pkg: PackageInfo):
        """Populate reverse dependencies."""
        for r in self._reqby_rows:
            self.reqby_group.remove(r)
        self._reqby_rows.clear()

        if not pkg.requiredby:
            row = Adw.ActionRow(title="None", subtitle="No installed packages depend on this")
            self.reqby_group.add(row)
            self._reqby_rows.append(row)
            return

        for req in pkg.requiredby:
            row = Adw.ActionRow(title=escape(req))
            row.set_activatable(True)
            nav_btn = Gtk.Button(icon_name="go-next-symbolic", css_classes=["flat", "circular"])
            nav_btn.connect("clicked", lambda _, name=req: self._on_dep_clicked(name))
            row.add_suffix(nav_btn)
            row.connect("activated", lambda _, name=req: self._on_dep_clicked(name))
            self.reqby_group.add(row)
            self._reqby_rows.append(row)

    def _populate_files_group(self, pkg: PackageInfo):
        """Populate file list expander."""
        for r in self._file_rows:
            self.files_expander.remove(r)
        self._file_rows.clear()

        self.files_expander.set_subtitle(f"{len(pkg.files)} files installed" if pkg.is_installed else "Not installed")
        if not pkg.is_installed or not pkg.files:
            self.files_group.set_visible(False)
            return

        self.files_group.set_visible(True)
        for filepath in pkg.files[:200]:
            frow = Adw.ActionRow(title=escape(f"/{filepath.lstrip('/')}"))
            self.files_expander.add_row(frow)
            self._file_rows.append(frow)

    def _on_dep_clicked(self, dep_name: str):
        if self.on_select_dep:
            self.on_select_dep(dep_name)

    def _on_install_clicked(self, _btn):
        if self.current_pkg and self.on_action:
            action = "aur_install" if self.current_pkg.is_aur else "install"
            self.on_action(action, self.current_pkg, False)

    def _on_reinstall_clicked(self, _btn):
        if self.current_pkg and self.on_action:
            action = "aur_install" if self.current_pkg.is_aur else "reinstall"
            self.on_action(action, self.current_pkg, False)

    def _on_remove_clicked(self, _btn):
        if self.current_pkg and self.on_action:
            cascade = self.cascade_check.get_active()
            self.on_action("remove", self.current_pkg, cascade)
