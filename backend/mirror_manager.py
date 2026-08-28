"""
Mirrorlist ranking and optimization manager.
"""

import os
import shutil
from typing import List, Optional


class MirrorManager:
    """Manager for ranking and configuring pacman mirrors using reflector / rate-mirrors."""

    def __init__(self, mirrorlist_path: str = "/etc/pacman.d/mirrorlist"):
        self.mirrorlist_path = mirrorlist_path
        self.has_reflector = bool(shutil.which("reflector"))
        self.has_rate_mirrors = bool(shutil.which("rate-mirrors"))

    def get_current_mirrors(self, limit: int = 15) -> List[str]:
        """Read top active mirror servers from mirrorlist."""
        servers = []
        if not os.path.exists(self.mirrorlist_path):
            return servers

        try:
            with open(self.mirrorlist_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("Server = ") or line.startswith("Server="):
                        url = line.split("=", 1)[1].strip()
                        servers.append(url)
                        if len(servers) >= limit:
                            break
        except Exception as e:
            print(f"Error reading {self.mirrorlist_path}: {e}")

        return servers

    def build_rank_command(
        self,
        tool: str = "auto",
        country: Optional[str] = None,
        max_mirrors: int = 20,
    ) -> List[str]:
        """Generate command to rank mirrors."""
        selected_tool = tool
        if selected_tool == "auto":
            if self.has_reflector:
                selected_tool = "reflector"
            elif self.has_rate_mirrors:
                selected_tool = "rate-mirrors"
            else:
                raise RuntimeError("Neither reflector nor rate-mirrors is installed on this system.")

        if selected_tool == "reflector":
            cmd = [
                "pkexec",
                "reflector",
                "--protocol",
                "https",
                "--latest",
                str(max_mirrors),
                "--sort",
                "rate",
                "--save",
                self.mirrorlist_path,
            ]
            if country and country != "Worldwide":
                cmd.extend(["--country", country])
            return cmd

        elif selected_tool == "rate-mirrors":
            return [
                "pkexec",
                "rate-mirrors",
                f"--save={self.mirrorlist_path}",
                "arch",
            ]

        raise ValueError(f"Unknown ranking tool: {tool}")
