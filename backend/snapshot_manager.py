"""
Package list snapshot backup and restore manager.
"""

import json
import os
from datetime import datetime
from typing import List, Optional

from backend.models import SnapshotInfo


class SnapshotManager:
    """Manager for exporting, importing, and restoring package snapshots."""

    def __init__(self, storage_dir: Optional[str] = None):
        if storage_dir:
            self.storage_dir = storage_dir
        else:
            self.storage_dir = os.path.expanduser("~/.config/pacgui/snapshots")
        os.makedirs(self.storage_dir, exist_ok=True)

    def export_snapshot(
        self,
        package_names: List[str],
        name: Optional[str] = None,
        custom_path: Optional[str] = None,
    ) -> SnapshotInfo:
        """Export package list to snapshot file."""
        now = datetime.now()
        ts_str = now.strftime("%Y-%m-%d_%H-%M-%S")
        snap_name = name or f"pacgui_snapshot_{ts_str}"

        target_file = custom_path or os.path.join(self.storage_dir, f"{snap_name}.json")

        data = {
            "name": snap_name,
            "created_at": now.isoformat(),
            "package_count": len(package_names),
            "packages": sorted(list(set(package_names))),
        }

        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return SnapshotInfo(
            file_path=target_file,
            name=snap_name,
            created_at=now.strftime("%Y-%m-%d %H:%M:%S"),
            package_count=len(package_names),
            packages=data["packages"],
        )

    def import_snapshot(self, file_path: str) -> SnapshotInfo:
        """Read and parse a snapshot file (.json or plain text pkglist.txt)."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Snapshot file not found: {file_path}")

        if file_path.endswith(".json"):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return SnapshotInfo(
                    file_path=file_path,
                    name=data.get("name", os.path.basename(file_path)),
                    created_at=data.get("created_at", "Unknown"),
                    package_count=data.get("package_count", len(data.get("packages", []))),
                    packages=data.get("packages", []),
                )
        else:
            # Plain text file (one package per line)
            packages = []
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        packages.append(line.split()[0])

            base_name = os.path.basename(file_path)
            return SnapshotInfo(
                file_path=file_path,
                name=base_name,
                created_at="Custom Import",
                package_count=len(packages),
                packages=sorted(list(set(packages))),
            )

    def list_saved_snapshots(self) -> List[SnapshotInfo]:
        """List all saved snapshots in the config storage directory."""
        snapshots = []
        if not os.path.exists(self.storage_dir):
            return snapshots

        for entry in os.scandir(self.storage_dir):
            if entry.is_file() and entry.name.endswith(".json"):
                try:
                    snap = self.import_snapshot(entry.path)
                    snapshots.append(snap)
                except Exception:
                    pass

        snapshots.sort(key=lambda s: s.created_at, reverse=True)
        return snapshots

    def get_missing_packages(self, snapshot_packages: List[str], installed_packages: List[str]) -> List[str]:
        """Find packages in snapshot that are not currently installed."""
        installed_set = set(installed_packages)
        return [p for p in snapshot_packages if p not in installed_set]
