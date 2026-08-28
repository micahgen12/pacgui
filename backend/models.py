"""
Data models and utility functions for PacGUI.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


def format_size(bytes_size: Optional[int]) -> str:
    """Format bytes into human-readable string (KiB, MiB, GiB)."""
    if bytes_size is None or bytes_size <= 0:
        return "0 B"
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    val = float(bytes_size)
    idx = 0
    while val >= 1024.0 and idx < len(units) - 1:
        val /= 1024.0
        idx += 1
    return f"{val:.1f} {units[idx]}"


@dataclass
class PackageInfo:
    """Represents a package from local DB, sync DB, or AUR."""
    name: str
    version: str
    repo: str
    desc: str = ""
    url: str = ""
    licenses: List[str] = field(default_factory=list)
    groups: List[str] = field(default_factory=list)
    arch: str = ""
    is_installed: bool = False
    installed_version: str = ""
    install_date: Optional[datetime] = None
    build_date: Optional[datetime] = None
    installed_size: int = 0
    download_size: int = 0
    packager: str = ""
    is_explicit: bool = False
    is_orphan: bool = False
    has_update: bool = False
    new_version: str = ""
    depends: List[str] = field(default_factory=list)
    optdepends: List[str] = field(default_factory=list)
    requiredby: List[str] = field(default_factory=list)
    optionalfor: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    replaces: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    is_aur: bool = False
    aur_votes: int = 0
    aur_popularity: float = 0.0

    @property
    def formatted_installed_size(self) -> str:
        return format_size(self.installed_size)

    @property
    def formatted_download_size(self) -> str:
        return format_size(self.download_size)


@dataclass
class UpdateInfo:
    """Represents a pending package update."""
    name: str
    old_version: str
    new_version: str
    repo: str = ""
    download_size: int = 0

    @property
    def formatted_size(self) -> str:
        return format_size(self.download_size)


@dataclass
class LogEntry:
    """Represents an entry in /var/log/pacman.log."""
    timestamp: str
    action: str  # 'installed', 'upgraded', 'removed', 'transaction', 'other'
    pkg_name: str
    version_info: str
    raw_line: str


@dataclass
class TransactionTask:
    """Represents a transaction to be executed via runner."""
    action_type: str  # 'install', 'remove', 'upgrade', 'clean_cache', 'remove_orphans', 'aur_install', 'aur_remove'
    packages: List[str]
    title: str
    description: str
    flags: List[str] = field(default_factory=list)
    use_aur_helper: bool = False
