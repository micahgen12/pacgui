"""
Privileged and non-privileged asynchronous transaction runner with PTY support.
"""

import os
import pty
import select
import shutil
import subprocess
import threading
from typing import Callable, List, Optional

from gi.repository import GLib

from backend.models import TransactionTask


class TransactionRunner:
    """Runs pacman / yay / paccache commands in background with live terminal streaming."""

    def __init__(self):
        self._current_proc: Optional[subprocess.Popen] = None
        self._master_fd: Optional[int] = None
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    def build_command(self, task: TransactionTask, aur_helper: Optional[str] = None) -> List[str]:
        """Generate the shell command list based on transaction type."""
        pkgs = [p.strip() for p in task.packages if p.strip()]

        if task.action_type == "install":
            if task.use_aur_helper and aur_helper:
                return [aur_helper, "-S", "--noconfirm"] + pkgs + task.flags
            return ["pkexec", "pacman", "-S", "--noconfirm", "--needed"] + pkgs + task.flags

        elif task.action_type == "reinstall":
            if task.use_aur_helper and aur_helper:
                return [aur_helper, "-S", "--noconfirm"] + pkgs + task.flags
            return ["pkexec", "pacman", "-S", "--noconfirm"] + pkgs + task.flags

        elif task.action_type == "remove":
            return ["pkexec", "pacman", "-Rns", "--noconfirm"] + pkgs + task.flags

        elif task.action_type == "upgrade":
            if task.use_aur_helper and aur_helper:
                return [aur_helper, "-Syu", "--noconfirm"] + task.flags
            return ["pkexec", "pacman", "-Syu", "--noconfirm"] + task.flags

        elif task.action_type == "clean_cache":
            if shutil.which("paccache"):
                return ["pkexec", "paccache", "-r"]
            return ["pkexec", "pacman", "-Sc", "--noconfirm"]

        elif task.action_type == "clean_cache_all":
            if shutil.which("paccache"):
                return ["pkexec", "paccache", "-rk1"]
            return ["pkexec", "pacman", "-Scc", "--noconfirm"]

        elif task.action_type == "remove_orphans":
            return ["pkexec", "pacman", "-Rns", "--noconfirm"] + pkgs + task.flags

        elif task.action_type == "custom":
            return task.flags

        raise ValueError(f"Unknown action type: {task.action_type}")

    def execute(
        self,
        task: TransactionTask,
        on_output: Callable[[str], None],
        on_finished: Callable[[int, bool], None],
        on_start: Optional[Callable[[List[str]], None]] = None,
        aur_helper: Optional[str] = "yay",
    ):
        """Execute task asynchronously in background thread."""
        if self._is_running:
            raise RuntimeError("Another transaction is already running")

        cmd = self.build_command(task, aur_helper=aur_helper)
        self._is_running = True

        def _worker():
            master_fd = None
            slave_fd = None
            returncode = -1
            try:
                if on_start:
                    GLib.idle_add(on_start, cmd)

                master_fd, slave_fd = pty.openpty()
                self._master_fd = master_fd

                # Set environment for clean UTF-8 output
                env = os.environ.copy()
                env["LC_ALL"] = "C.UTF-8"
                env["LANG"] = "C.UTF-8"

                self._current_proc = subprocess.Popen(
                    cmd,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True,
                    env=env,
                )
                os.close(slave_fd)
                slave_fd = None

                # Read output chunks and stream lines
                buffer = ""
                while self._is_running and self._current_proc.poll() is None:
                    r, _, _ = select.select([master_fd], [], [], 0.05)
                    if master_fd in r:
                        try:
                            raw = os.read(master_fd, 2048)
                            if not raw:
                                break
                            text = raw.decode("utf-8", errors="replace")
                            buffer += text
                            # Split by \n or carriage returns \r for progress bars
                            lines = buffer.split("\n")
                            for line in lines[:-1]:
                                GLib.idle_add(on_output, line + "\n")
                            buffer = lines[-1]
                        except OSError:
                            break

                # Read any remaining output
                if master_fd is not None:
                    try:
                        r, _, _ = select.select([master_fd], [], [], 0.1)
                        if master_fd in r:
                            raw = os.read(master_fd, 4096)
                            if raw:
                                buffer += raw.decode("utf-8", errors="replace")
                    except OSError:
                        pass

                if buffer:
                    GLib.idle_add(on_output, buffer + "\n")

                if self._current_proc:
                    returncode = self._current_proc.wait()

            except Exception as e:
                GLib.idle_add(on_output, f"\n[PacGUI Error]: {str(e)}\n")
                returncode = -1
            finally:
                if slave_fd is not None:
                    try:
                        os.close(slave_fd)
                    except OSError:
                        pass
                if master_fd is not None:
                    try:
                        os.close(master_fd)
                    except OSError:
                        pass

                self._master_fd = None
                self._current_proc = None
                self._is_running = False
                success = (returncode == 0)
                GLib.idle_add(on_finished, returncode, success)

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()

    def cancel(self):
        """Cancel active transaction."""
        if not self._is_running:
            return
        self._is_running = False
        if self._current_proc:
            try:
                self._current_proc.terminate()
                self._current_proc.poll()
            except Exception:
                pass
