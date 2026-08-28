"""
Flatpak application manager.
"""

import shutil
import subprocess
from typing import List, Optional

from backend.models import FlatpakApp


class FlatpakManager:
    """Manager for querying, installing, and managing Flatpak applications."""

    def __init__(self):
        self.is_available = bool(shutil.which("flatpak"))

    def get_installed_apps(self) -> List[FlatpakApp]:
        """Fetch all installed Flatpak applications."""
        if not self.is_available:
            return []

        apps = []
        try:
            cmd = [
                "flatpak",
                "list",
                "--app",
                "--columns=application,name,version,branch,arch,origin,description,size",
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
            if res.returncode == 0 and res.stdout:
                for line in res.stdout.strip().splitlines():
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        app_id = parts[0].strip()
                        name = parts[1].strip() or app_id
                        ver = parts[2].strip()
                        branch = parts[3].strip()
                        arch = parts[4].strip()
                        origin = parts[5].strip()
                        desc = parts[6].strip() if len(parts) > 6 else ""

                        apps.append(
                            FlatpakApp(
                                app_id=app_id,
                                name=name,
                                version=ver,
                                branch=branch,
                                arch=arch,
                                origin=origin,
                                desc=desc,
                                is_installed=True,
                            )
                        )
        except Exception as e:
            print(f"Error fetching installed Flatpaks: {e}")

        apps.sort(key=lambda a: a.name.lower())
        return apps

    def search_apps(self, query: str, limit: int = 40) -> List[FlatpakApp]:
        """Search Flathub and remotes for applications."""
        if not self.is_available or not query or len(query.strip()) < 2:
            return []

        installed_ids = {a.app_id for a in self.get_installed_apps()}
        apps = []

        try:
            cmd = [
                "flatpak",
                "search",
                "--columns=application,name,version,branch,remotes,description",
                query.strip(),
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if res.returncode == 0 and res.stdout:
                for line in res.stdout.strip().splitlines()[:limit]:
                    parts = line.split("\t")
                    if len(parts) >= 5:
                        app_id = parts[0].strip()
                        name = parts[1].strip() or app_id
                        ver = parts[2].strip()
                        branch = parts[3].strip()
                        origin = parts[4].strip()
                        desc = parts[5].strip() if len(parts) > 5 else ""

                        apps.append(
                            FlatpakApp(
                                app_id=app_id,
                                name=name,
                                version=ver,
                                branch=branch,
                                origin=origin,
                                desc=desc,
                                is_installed=(app_id in installed_ids),
                            )
                        )
        except Exception as e:
            print(f"Error searching Flatpaks for '{query}': {e}")

        return apps

    def build_install_command(self, app_id: str, remote: str = "flathub") -> List[str]:
        """Generate command to install Flatpak app."""
        return ["flatpak", "install", "-y", remote, app_id]

    def build_remove_command(self, app_id: str) -> List[str]:
        """Generate command to uninstall Flatpak app."""
        return ["flatpak", "uninstall", "-y", app_id]

    def build_update_command(self) -> List[str]:
        """Generate command to update all Flatpak apps."""
        return ["flatpak", "update", "-y"]
