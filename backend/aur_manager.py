"""
AUR (Arch User Repository) manager using AUR RPC v5 and yay/paru helper.
"""

import json
import shutil
import urllib.parse
import urllib.request
from typing import List, Optional

from backend.models import PackageInfo


class AurManager:
    """Manager for querying AUR and handling AUR packages."""

    def __init__(self):
        self.helper = self._detect_helper()

    def _detect_helper(self) -> Optional[str]:
        """Detect available AUR helper (yay or paru)."""
        if shutil.which("yay"):
            return "yay"
        if shutil.which("paru"):
            return "paru"
        return None

    def search(self, query: str, limit: int = 50) -> List[PackageInfo]:
        """Search AUR using the v5 RPC API."""
        if not query or len(query.strip()) < 2:
            return []

        clean_query = query.strip()
        encoded = urllib.parse.quote(clean_query)
        url = f"https://aur.archlinux.org/rpc/v5/search/{encoded}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "PacGUI-PackageManager/1.0"},
            )
            with urllib.request.urlopen(req, timeout=6) as response:
                data = json.loads(response.read().decode("utf-8"))
                raw_results = data.get("results", [])

                packages = []
                for item in raw_results[:limit]:
                    pkg = PackageInfo(
                        name=item.get("Name", ""),
                        version=item.get("Version", ""),
                        repo="aur",
                        desc=item.get("Description", "") or "",
                        url=item.get("URL", "") or "",
                        licenses=item.get("License", []) or [],
                        is_aur=True,
                        aur_votes=item.get("NumVotes", 0) or 0,
                        aur_popularity=float(item.get("Popularity", 0.0) or 0.0),
                        packager=item.get("Maintainer", "") or "orphan",
                        depends=item.get("Depends", []) or [],
                        optdepends=item.get("OptDepends", []) or [],
                        conflicts=item.get("Conflicts", []) or [],
                        provides=item.get("Provides", []) or [],
                    )
                    packages.append(pkg)

                # Sort by popularity / votes, exact name first
                q_lower = clean_query.lower()
                packages.sort(
                    key=lambda p: (
                        0 if p.name.lower() == q_lower else (1 if p.name.lower().startswith(q_lower) else 2),
                        -p.aur_votes,
                        -p.aur_popularity,
                        p.name.lower(),
                    )
                )
                return packages
        except Exception as e:
            print(f"Error querying AUR for '{query}': {e}")
            return []

    def get_info(self, name: str) -> Optional[PackageInfo]:
        """Fetch full info for a specific package from AUR."""
        encoded = urllib.parse.quote(name.strip())
        url = f"https://aur.archlinux.org/rpc/v5/info/{encoded}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "PacGUI-PackageManager/1.0"},
            )
            with urllib.request.urlopen(req, timeout=6) as response:
                data = json.loads(response.read().decode("utf-8"))
                results = data.get("results", [])
                if not results:
                    return None

                item = results[0]
                return PackageInfo(
                    name=item.get("Name", ""),
                    version=item.get("Version", ""),
                    repo="aur",
                    desc=item.get("Description", "") or "",
                    url=item.get("URL", "") or "",
                    licenses=item.get("License", []) or [],
                    is_aur=True,
                    aur_votes=item.get("NumVotes", 0) or 0,
                    aur_popularity=float(item.get("Popularity", 0.0) or 0.0),
                    packager=item.get("Maintainer", "") or "orphan",
                    depends=item.get("Depends", []) or [],
                    optdepends=item.get("OptDepends", []) or [],
                    conflicts=item.get("Conflicts", []) or [],
                    provides=item.get("Provides", []) or [],
                )
        except Exception as e:
            print(f"Error fetching AUR package info for '{name}': {e}")
            return None
