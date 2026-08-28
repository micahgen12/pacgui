"""
Unit tests for PacGUI backend components.
"""

import unittest
from backend.models import PackageInfo, TransactionTask, UpdateInfo, format_size
from backend.alpm_manager import AlpmManager
from backend.aur_manager import AurManager
from backend.runner import TransactionRunner


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


class TestAlpmManager(unittest.TestCase):
    """Test ALPM database interface."""

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


class TestTransactionRunner(unittest.TestCase):
    """Test command building for pacman transactions."""

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

    def test_build_remove_command(self):
        task = TransactionTask(
            action_type="remove",
            packages=["nano"],
            title="Remove",
            description="Remove nano",
        )
        cmd = self.runner.build_command(task)
        self.assertEqual(cmd, ["pkexec", "pacman", "-Rns", "--noconfirm", "nano"])

    def test_build_upgrade_command(self):
        task = TransactionTask(
            action_type="upgrade",
            packages=[],
            title="Upgrade",
            description="Upgrade system",
        )
        cmd = self.runner.build_command(task)
        self.assertEqual(cmd, ["pkexec", "pacman", "-Syu", "--noconfirm"])

    def test_build_aur_command(self):
        task = TransactionTask(
            action_type="install",
            packages=["spotify"],
            title="Install AUR",
            description="Install spotify",
            use_aur_helper=True,
        )
        cmd = self.runner.build_command(task, aur_helper="yay")
        self.assertEqual(cmd, ["yay", "-S", "--noconfirm", "spotify"])


if __name__ == "__main__":
    unittest.main()
