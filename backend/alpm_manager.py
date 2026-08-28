"""
ALPM / Pacman database manager using pyalpm.
"""

import os
import re
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pyalpm
from backend.models import LogEntry, PackageInfo, UpdateInfo


CATEGORY_KEYWORDS = {
    "development": [
        "devel", "base-devel", "compiler", "ide", "debugger", "python", "rust", "golang",
        "java", "c++", "gcc", "clang", "cmake", "ninja", "git", "sdk", "llvm", "glibc",
    ],
    "multimedia": [
        "multimedia", "audio", "video", "sound", "player", "music", "codec", "vlc", "mpv",
        "ffmpeg", "pipewire", "pulseaudio", "alsa", "gstreamer", "midi", "recorder",
    ],
    "internet": [
        "network", "browser", "web", "http", "ssh", "mail", "ftp", "torrent", "chat",
        "messaging", "discord", "telegram", "matrix", "wifi", "vpn", "dns", "client",
    ],
    "graphics": [
        "graphics", "image", "photo", "drawing", "paint", "3d", "blender", "gimp",
        "inkscape", "svg", "png", "jpeg", "font", "rendering", "viewer",
    ],
    "system": [
        "base", "system", "sys-utils", "kernel", "driver", "terminal", "shell", "disk",
        "filesystem", "grub", "boot", "pacman", "systemd", "btrfs", "zfs", "firmware",
    ],
    "games": [
        "games", "game", "emulator", "steam", "wine", "proton", "vulkan", "retro",
        "lutris", "arcade", "rpg", "fps", "simulation",
    ],
    "office": [
        "office", "document", "pdf", "spreadsheet", "word", "writer", "calc",
        "reader", "viewer", "latex", "markdown", "epub", "notes",
    ],
}


class AlpmManager:
    """High performance ALPM manager wrapping pyalpm."""

    def __init__(self, root_dir: str = "/", db_path: str = "/var/lib/pacman", conf_path: str = "/etc/pacman.conf"):
        self.root_dir = root_dir
        self.db_path = db_path
        self.conf_path = conf_path
        self.handle: Optional[pyalpm.Handle] = None
        self.registered_repos: List[str] = []
        self._local_cache: Dict[str, pyalpm.Package] = {}
        self._sync_cache: Dict[str, List[pyalpm.Package]] = {}
        self._updates_cache: Dict[str, str] = {}
        self.initialize()

    def _parse_pacman_conf(self) -> List[str]:
        """Extract repository sections from pacman.conf."""
        repos = []
        if not os.path.exists(self.conf_path):
            return repos
        try:
            with open(self.conf_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("[") and line.endswith("]"):
                        sec = line[1:-1]
                        if sec != "options" and sec not in repos:
                            repos.append(sec)
        except Exception as e:
            print(f"Error reading {self.conf_path}: {e}")
        return repos

    def initialize(self):
        """Initialize the pyalpm Handle and load databases."""
        try:
            self.handle = pyalpm.Handle(self.root_dir, self.db_path)
            self.registered_repos = self._parse_pacman_conf()
            for repo in self.registered_repos:
                try:
                    self.handle.register_syncdb(repo, pyalpm.SIG_DATABASE_OPTIONAL)
                except Exception:
                    pass
            self.refresh_cache()
        except Exception as e:
            print(f"Error initializing AlpmManager: {e}")

    def refresh_cache(self):
        """Reload local and sync package caches."""
        self._local_cache.clear()
        self._sync_cache.clear()
        if not self.handle:
            return

        try:
            local_db = self.handle.get_localdb()
            for pkg in local_db.pkgcache:
                self._local_cache[pkg.name] = pkg
        except Exception as e:
            print(f"Error caching local db: {e}")

        try:
            for sdb in self.handle.get_syncdbs():
                for pkg in sdb.pkgcache:
                    if pkg.name not in self._sync_cache:
                        self._sync_cache[pkg.name] = []
                    self._sync_cache[pkg.name].append(pkg)
        except Exception as e:
            print(f"Error caching sync dbs: {e}")

    def is_db_locked(self) -> bool:
        """Check if pacman database lock file exists."""
        lock_path = os.path.join(self.db_path, "db.lck")
        return os.path.exists(lock_path)

    def _convert_alpm_pkg(self, pkg: pyalpm.Package, repo_name: Optional[str] = None, load_deep: bool = False) -> PackageInfo:
        """Convert a pyalpm.Package object to PackageInfo dataclass."""
        is_installed = False
        installed_ver = ""
        is_explicit = False
        is_orphan = False

        if pkg.name in self._local_cache:
            is_installed = True
            loc_pkg = self._local_cache[pkg.name]
            installed_ver = loc_pkg.version
            is_explicit = (loc_pkg.reason == pyalpm.PKG_REASON_EXPLICIT)
            if not is_explicit and not loc_pkg.compute_requiredby():
                is_orphan = True

        repo = repo_name or (pkg.db.name if pkg.db else "local")
        
        has_update = False
        new_version = ""
        if is_installed and pkg.name in self._sync_cache:
            for spkg in self._sync_cache[pkg.name]:
                if pyalpm.vercmp(spkg.version, installed_ver) > 0:
                    has_update = True
                    new_version = spkg.version
                    break

        install_dt = None
        if hasattr(pkg, "installdate") and pkg.installdate:
            try:
                install_dt = datetime.fromtimestamp(pkg.installdate)
            except Exception:
                pass

        build_dt = None
        if hasattr(pkg, "builddate") and pkg.builddate:
            try:
                build_dt = datetime.fromtimestamp(pkg.builddate)
            except Exception:
                pass

        pkg_info = PackageInfo(
            name=pkg.name,
            version=pkg.version,
            repo=repo,
            desc=pkg.desc or "",
            url=pkg.url or "",
            licenses=list(pkg.licenses or []),
            groups=list(pkg.groups or []),
            arch=pkg.arch or "",
            is_installed=is_installed,
            installed_version=installed_ver,
            install_date=install_dt,
            build_date=build_dt,
            installed_size=pkg.isize or 0,
            download_size=pkg.size or pkg.download_size or 0,
            packager=pkg.packager or "",
            is_explicit=is_explicit,
            is_orphan=is_orphan,
            has_update=has_update,
            new_version=new_version,
            depends=list(pkg.depends or []),
            optdepends=list(pkg.optdepends or []),
            conflicts=list(pkg.conflicts or []),
            provides=list(pkg.provides or []),
            replaces=list(pkg.replaces or []),
        )

        if load_deep:
            if is_installed and pkg.name in self._local_cache:
                loc_pkg = self._local_cache[pkg.name]
                try:
                    pkg_info.requiredby = loc_pkg.compute_requiredby()
                    pkg_info.optionalfor = loc_pkg.compute_optionalfor()
                    raw_files = loc_pkg.files or []
                    pkg_info.files = [
                        f[0] if isinstance(f, (list, tuple)) else str(f)
                        for f in raw_files
                    ]
                except Exception as e:
                    print(f"Error resolving deep metadata for {pkg.name}: {e}")

        return pkg_info

    def get_package_info(self, name: str, repo: Optional[str] = None, deep: bool = True) -> Optional[PackageInfo]:
        """Fetch full PackageInfo for a given name."""
        if repo == "local" or (repo is None and name in self._local_cache):
            loc_pkg = self._local_cache.get(name)
            if loc_pkg:
                return self._convert_alpm_pkg(loc_pkg, repo_name="local", load_deep=deep)

        if name in self._sync_cache:
            pkgs = self._sync_cache[name]
            if repo:
                for p in pkgs:
                    if p.db and p.db.name == repo:
                        return self._convert_alpm_pkg(p, repo_name=repo, load_deep=deep)
            if pkgs:
                return self._convert_alpm_pkg(pkgs[0], load_deep=deep)

        return None

    def search_packages(
        self,
        query: str = "",
        scope: str = "all",  # 'all', 'installed', 'explicit', 'dependencies', 'orphans', 'updates', or 'cat:<name>'
        repo: Optional[str] = None,
        sort_by: str = "name_asc",  # 'name_asc', 'name_desc', 'size_desc', 'size_asc', 'date_desc', 'date_asc'
        limit: int = 300,
    ) -> List[PackageInfo]:
        """Fast multi-field package search with sorting and category support."""
        results: List[PackageInfo] = []
        tokens = query.lower().split() if query else []

        is_category = scope.startswith("cat:")
        category_name = scope[4:] if is_category else None
        cat_keywords = CATEGORY_KEYWORDS.get(category_name, []) if category_name else []

        def matches_tokens(name_lower: str, desc_lower: str, groups: List[str]) -> bool:
            if cat_keywords:
                matched_cat = False
                for kw in cat_keywords:
                    if kw in name_lower or kw in desc_lower or any(kw in g.lower() for g in groups):
                        matched_cat = True
                        break
                if not matched_cat:
                    return False

            if not tokens:
                return True
            for t in tokens:
                if t not in name_lower and t not in desc_lower:
                    return False
            return True

        if scope in ("installed", "explicit", "dependencies", "orphans"):
            for name, pkg in self._local_cache.items():
                name_l = name.lower()
                desc_l = (pkg.desc or "").lower()
                groups = list(pkg.groups or [])
                if not matches_tokens(name_l, desc_l, groups):
                    continue

                is_exp = (pkg.reason == pyalpm.PKG_REASON_EXPLICIT)
                if scope == "explicit" and not is_exp:
                    continue
                if scope == "dependencies" and is_exp:
                    continue
                if scope == "orphans":
                    if is_exp or pkg.compute_requiredby():
                        continue

                results.append(self._convert_alpm_pkg(pkg, repo_name="local", load_deep=False))
                if len(results) >= limit:
                    break

        elif scope == "updates":
            updates = self.get_updates()
            update_names = {u.name: u for u in updates}
            for name in update_names:
                pkg = self._local_cache.get(name)
                if not pkg:
                    continue
                name_l = name.lower()
                desc_l = (pkg.desc or "").lower()
                if not matches_tokens(name_l, desc_l, []):
                    continue
                pinfo = self._convert_alpm_pkg(pkg, repo_name="local", load_deep=False)
                pinfo.has_update = True
                pinfo.new_version = update_names[name].new_version
                results.append(pinfo)
                if len(results) >= limit:
                    break

        else:  # 'all' or category
            seen_names = set()
            for name, pkg_list in self._sync_cache.items():
                if repo:
                    pkg_list = [p for p in pkg_list if p.db and p.db.name == repo]
                if not pkg_list:
                    continue
                pkg = pkg_list[0]
                name_l = name.lower()
                desc_l = (pkg.desc or "").lower()
                groups = list(pkg.groups or [])
                if not matches_tokens(name_l, desc_l, groups):
                    continue

                results.append(self._convert_alpm_pkg(pkg, repo_name=pkg.db.name if pkg.db else None, load_deep=False))
                seen_names.add(name)
                if len(results) >= limit:
                    break

            if len(results) < limit:
                for name, pkg in self._local_cache.items():
                    if name in seen_names:
                        continue
                    name_l = name.lower()
                    desc_l = (pkg.desc or "").lower()
                    groups = list(pkg.groups or [])
                    if not matches_tokens(name_l, desc_l, groups):
                        continue
                    results.append(self._convert_alpm_pkg(pkg, repo_name="local", load_deep=False))
                    if len(results) >= limit:
                        break

        # Sorting logic
        self._apply_sorting(results, sort_by=sort_by, query=query)
        return results

    def _apply_sorting(self, results: List[PackageInfo], sort_by: str, query: str = ""):
        """Sort package list based on criteria."""
        q_lower = query.strip().lower()

        if sort_by == "size_desc":
            results.sort(key=lambda p: (p.installed_size or p.download_size), reverse=True)
        elif sort_by == "size_asc":
            results.sort(key=lambda p: (p.installed_size or p.download_size))
        elif sort_by == "date_desc":
            results.sort(key=lambda p: (p.build_date or p.install_date or datetime.min), reverse=True)
        elif sort_by == "date_asc":
            results.sort(key=lambda p: (p.build_date or p.install_date or datetime.min))
        elif sort_by == "name_desc":
            results.sort(key=lambda p: p.name.lower(), reverse=True)
        else:  # name_asc (default, with exact search match prefix prioritization)
            if query:
                results.sort(
                    key=lambda p: (
                        0 if p.name.lower() == q_lower else (1 if p.name.lower().startswith(q_lower) else 2),
                        p.name.lower(),
                    )
                )
            else:
                results.sort(key=lambda p: p.name.lower())

    def get_file_owner(self, file_path: str) -> Optional[PackageInfo]:
        """Find the package that owns a given file path."""
        clean_path = file_path.strip().lstrip("/")
        # Check in local cache
        for name, pkg in self._local_cache.items():
            for f in (pkg.files or []):
                fname = f[0] if isinstance(f, (list, tuple)) else str(f)
                if fname.rstrip("/") == clean_path or fname.endswith(clean_path):
                    return self.get_package_info(name, deep=True)

        # Fallback to pacman -Qo CLI
        try:
            res = subprocess.run(
                ["pacman", "-Qo", file_path.strip()],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout:
                # Format: '/usr/bin/foo is owned by package-name version'
                parts = res.stdout.strip().split("is owned by")
                if len(parts) > 1:
                    pkg_id = parts[1].strip().split()[0]
                    return self.get_package_info(pkg_id, deep=True)
        except Exception:
            pass

        return None

    def get_orphans(self) -> List[PackageInfo]:
        """Find all orphaned packages."""
        orphans = []
        for name, pkg in self._local_cache.items():
            if pkg.reason == pyalpm.PKG_REASON_DEPEND and not pkg.compute_requiredby():
                orphans.append(self._convert_alpm_pkg(pkg, repo_name="local", load_deep=False))
        orphans.sort(key=lambda p: p.name.lower())
        return orphans

    def get_updates(self) -> List[UpdateInfo]:
        """Check for pending updates using checkupdates or ALPM comparison."""
        updates: List[UpdateInfo] = []
        try:
            res = subprocess.run(
                ["checkupdates"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
            )
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.strip().splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 4 and parts[2] == "->":
                        name = parts[0]
                        old_v = parts[1]
                        new_v = parts[3]
                        repo = ""
                        if name in self._sync_cache and self._sync_cache[name]:
                            repo = self._sync_cache[name][0].db.name if self._sync_cache[name][0].db else ""
                        updates.append(UpdateInfo(name=name, old_version=old_v, new_version=new_v, repo=repo))
                return updates
        except Exception:
            pass

        for name, loc_pkg in self._local_cache.items():
            if name in self._sync_cache:
                for spkg in self._sync_cache[name]:
                    if pyalpm.vercmp(spkg.version, loc_pkg.version) > 0:
                        updates.append(
                            UpdateInfo(
                                name=name,
                                old_version=loc_pkg.version,
                                new_version=spkg.version,
                                repo=spkg.db.name if spkg.db else "",
                                download_size=spkg.size or 0,
                            )
                        )
                        break
        updates.sort(key=lambda u: u.name.lower())
        return updates

    def get_cache_info(self, cache_dir: str = "/var/cache/pacman/pkg") -> Dict[str, any]:
        """Get summary info about pacman package cache."""
        total_size = 0
        pkg_count = 0
        if os.path.exists(cache_dir):
            try:
                for entry in os.scandir(cache_dir):
                    if entry.is_file() and (entry.name.endswith(".pkg.tar.zst") or entry.name.endswith(".pkg.tar.xz")):
                        pkg_count += 1
                        try:
                            total_size += entry.stat().st_size
                        except OSError:
                            pass
            except Exception as e:
                print(f"Error scanning cache dir {cache_dir}: {e}")

        return {
            "path": cache_dir,
            "total_size": total_size,
            "pkg_count": pkg_count,
        }

    def get_recent_logs(self, limit: int = 150, log_path: str = "/var/log/pacman.log") -> List[LogEntry]:
        """Parse pacman.log for recent actions."""
        entries: List[LogEntry] = []
        if not os.path.exists(log_path):
            return entries

        log_regex = re.compile(
            r"^\[(?P<ts>[^\]]+)\] \[ALPM\] (?P<action>installed|upgraded|removed|reinstalled|downgraded) (?P<pkg>\S+)(?: \((?P<ver>[^\)]+)\))?"
        )

        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                for line in reversed(lines):
                    line = line.strip()
                    m = log_regex.match(line)
                    if m:
                        ts = m.group("ts")
                        action = m.group("action")
                        pkg = m.group("pkg")
                        ver = m.group("ver") or ""
                        entries.append(
                            LogEntry(
                                timestamp=ts,
                                action=action,
                                pkg_name=pkg,
                                version_info=ver,
                                raw_line=line,
                            )
                        )
                        if len(entries) >= limit:
                            break
        except Exception as e:
            print(f"Error reading {log_path}: {e}")

        return entries
