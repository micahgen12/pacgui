"""
Unit tests for PacGUI backend components.
"""

import os
import tempfile
import unittest

from backend.alpm_manager import AlpmManager
from backend.aur_manager import AurManager
from backend.flatpak_manager import FlatpakManager
from backend.mirror_manager import MirrorManager
from backend.models import FlatpakApp, PackageInfo, QueueItem, SnapshotInfo, TransactionTask, UpdateInfo, format_size
from backend.runner import TransactionRunner
from backend.snapshot_manager import SnapshotManager


class TestModels(unittest.TestCase):
    """Test data models and helper functions."""

    def test_format_size(self):
        self.assertEqual(format_size(0), "0 B")
        self.assertEqual(format_size(500), "500.0 B")
        self.assertEqual(format_size(1024), "1.0 KiB")
        self.assertEqual(format_size(1024 * 1024 * 5), "5.0 MiB")
        self.assertEqual(format_size(1024 * 1024 * 1024 * 2), "2.0 GiB")

    def test_package_info(self):
        pkg = PackageInfo(
            name="test-pkg",
            version="1.0.0-1",
            repo="extra",
            desc="A test package",
            installed_size=1048576,
            download_size=524288,
        )
        self.assertEqual(pkg.formatted_installed_size, "1.0 MiB")
        self.assertEqual(pkg.formatted_download_size, "512.0 KiB")

    def test_queue_item(self):
        item = QueueItem(pkg_name="neovim", action="install", size=10485760)
        self.assertEqual(item.formatted_size, "10.0 MiB")


class TestAlpmManager(unittest.TestCase):
    """Test ALPM database interface and queries."""

    def setUp(self):
        self.mgr = AlpmManager()

    def test_initialization(self):
        self.assertIsNotNone(self.mgr.handle)
        self.assertGreater(len(self.mgr._local_cache), 0)
        self.assertGreater(len(self.mgr._sync_cache), 0)

    def test_search_packages(self):
        results = self.mgr.search_packages(query="pacman", scope="all")
        self.assertGreater(len(results), 0)
        pacman_pkg = next((p for p in results if p.name == "pacman"), None)
        self.assertIsNotNone(pacman_pkg)
        self.assertEqual(pacman_pkg.name, "pacman")

    def test_sorting_by_size(self):
        results = self.mgr.search_packages(scope="installed", sort_by="size_desc", limit=20)
        self.assertGreater(len(results), 1)
        # Check descending order
        sizes = [p.installed_size for p in results]
        self.assertEqual(sizes, sorted(sizes, reverse=True))

    def test_category_search(self):
        results = self.mgr.search_packages(scope="cat:development", limit=20)
        self.assertGreater(len(results), 0)

    def test_file_owner_lookup(self):
        info = self.mgr.get_file_owner("/usr/bin/pacman")
        if info:
            self.assertEqual(info.name, "pacman")

    def test_get_package_info(self):
        info = self.mgr.get_package_info("pacman", deep=True)
        self.assertIsNotNone(info)
        self.assertEqual(info.name, "pacman")
        self.assertTrue(info.is_installed)
        self.assertGreater(len(info.depends), 0)

    def test_cache_info(self):
        info = self.mgr.get_cache_info()
        self.assertIn("path", info)
        self.assertIn("total_size", info)
        self.assertIn("pkg_count", info)


class TestMirrorManager(unittest.TestCase):
    """Test mirrorlist optimizer commands."""

    def setUp(self):
        self.mirror_mgr = MirrorManager()

    def test_build_rank_command(self):
        if self.mirror_mgr.has_reflector:
            cmd = self.mirror_mgr.build_rank_command(tool="reflector", max_mirrors=15)
            self.assertIn("reflector", cmd)
            self.assertIn("--latest", cmd)
        elif self.mirror_mgr.has_rate_mirrors:
            cmd = self.mirror_mgr.build_rank_command(tool="rate-mirrors")
            self.assertIn("rate-mirrors", cmd)


class TestSnapshotManager(unittest.TestCase):
    """Test package snapshot export, import, and diffing."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.snap_mgr = SnapshotManager(storage_dir=self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_export_and_import_snapshot(self):
        pkgs = ["firefox", "neovim", "git", "alacritty"]
        snap = self.snap_mgr.export_snapshot(pkgs, name="test_backup")
        self.assertTrue(os.path.exists(snap.file_path))
        self.assertEqual(snap.package_count, 4)

        imported = self.snap_mgr.import_snapshot(snap.file_path)
        self.assertEqual(imported.package_count, 4)
        self.assertEqual(imported.packages, sorted(pkgs))

    def test_missing_packages_diff(self):
        snapshot_pkgs = ["firefox", "neovim", "vlc", "steam"]
        installed_pkgs = ["firefox", "git"]
        missing = self.snap_mgr.get_missing_packages(snapshot_pkgs, installed_pkgs)
        self.assertEqual(missing, ["neovim", "vlc", "steam"])


class TestFlatpakManager(unittest.TestCase):
    """Test Flatpak manager."""

    def setUp(self):
        self.flatpak_mgr = FlatpakManager()

    def test_installed_apps(self):
        if self.flatpak_mgr.is_available:
            apps = self.flatpak_mgr.get_installed_apps()
            self.assertIsInstance(apps, list)

    def test_build_commands(self):
        cmd_inst = self.flatpak_mgr.build_install_command("org.videolan.VLC")
        self.assertEqual(cmd_inst, ["flatpak", "install", "-y", "flathub", "org.videolan.VLC"])

        cmd_rm = self.flatpak_mgr.build_remove_command("org.videolan.VLC")
        self.assertEqual(cmd_rm, ["flatpak", "uninstall", "-y", "org.videolan.VLC"])


class TestTransactionRunner(unittest.TestCase):
    """Test command building for transactions including batch."""

    def setUp(self):
        self.runner = TransactionRunner()

    def test_build_install_command(self):
        task = TransactionTask(
            action_type="install",
            packages=["neovim", "htop"],
            title="Install",
            description="Install packages",
        )
        cmd = self.runner.build_command(task)
        self.assertEqual(cmd, ["pkexec", "pacman", "-S", "--noconfirm", "--needed", "neovim", "htop"])

    def test_build_batch_command(self):
        task = TransactionTask(
            action_type="batch",
            packages=["neovim"],
            remove_packages=["nano"],
            title="Batch",
            description="Batch execute",
        )
        cmd = self.runner.build_command(task)
        self.assertEqual(cmd[0], "pkexec")
        self.assertEqual(cmd[1], "bash")
        self.assertEqual(cmd[2], "-c")
        self.assertIn("pacman -Rns --noconfirm nano", cmd[3])
        self.assertIn("pacman -S --noconfirm --needed neovim", cmd[3])


if __name__ == "__main__":
    unittest.main()
