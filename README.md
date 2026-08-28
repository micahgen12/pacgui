# PacGUI 📦
> **Modern GTK4 / Libadwaita Graphical Package Manager & Software Center for Arch Linux & ALPM Distributions**

PacGUI is a fast, responsive, and feature-rich graphical user interface for `pacman`, the Arch User Repository (AUR), and Flatpak applications. Built using **Python**, **GTK4 / Libadwaita**, and **`pyalpm`** (ALPM C library bindings), PacGUI provides instantaneous search across tens of thousands of packages, detailed package inspection, and safe elevated operations.

---

## ✨ Features

### ⚡ Core & Performance
- **⚡ Sub-Millisecond ALPM Engine**: Powered by native `pyalpm` to query local databases and sync repositories (`core`, `extra`, `multilib`, `cachyos`, etc.) in memory without slow shell spawning.
- **🎨 Modern Libadwaita UI**:
  - Adaptive sidebar with categorized navigation and curated software collections.
  - Native dark/light theme support.
  - Interactive package cards with status indicators (Installed, Updatable, Orphan, AUR, Flatpak).

### 🛍️ Batch Operations & Queue
- **🛍️ Multi-Package Action Queue ("Shopping Cart")**: Queue multiple package installations and removals, review the complete change list, and apply all operations in a single consolidated transaction.

### 🚀 Unified Software Center
- **🌐 AUR Integration**: Search and install Arch User Repository packages using `yay` or the official AUR RPC v5.
- **📦 Flatpak Hub**: Browse, search, install, update, and manage sandboxed Flathub applications alongside native packages.
- **🗂️ Curated Categories**: Discover software organized into curated groups:
  - 💻 *Development* (compilers, IDEs, git, debuggers)
  - 🌐 *Internet & Network* (browsers, messaging, torrents, VPNs)
  - 🎬 *Multimedia* (audio/video players, encoders, editors)
  - 🎨 *Graphics & 3D* (Blender, GIMP, Inkscape, viewers)
  - ⚙️ *System & Utilities* (system monitors, terminals, disk tools)
  - 🎮 *Gaming & Emulation* (Steam, Wine, Proton, emulators)
  - 📄 *Office & Reading* (document editors, PDF readers, note apps)

### 🔍 Advanced Discovery & Inspection
- **🔍 Instant Search & Repo Filtering**: Real-time debounced search across package names and descriptions.
- **📊 Advanced Sorting**: Sort package lists by Name (A-Z / Z-A), Installed Size (find disk hogs), Download Size, or Build Date.
- **🔎 File Owner Inspector**: Enter any filesystem path (e.g. `/usr/bin/bash` or `libcrypto.so`) to identify which package owns it (`pacman -Qo`).
- **📦 Comprehensive Package Inspector**: View descriptions, maintainers, licenses, sizes, build/install dates, installed files, and click any dependency to navigate directly to it.

### 🧹 System Maintenance & Optimization
- **⚡ Mirror Benchmark & Speed Optimizer**: Benchmark and rank download servers into `/etc/pacman.d/mirrorlist` using `reflector` or `rate-mirrors`.
- **📂 Package List Snapshots (Backup & Restore)**: Export your explicitly installed packages (`pacman -Qqe`) to a snapshot file and restore/batch install them on new machines.
- **🔧 System Health Troubleshooter**: Detect and remove stuck `/var/lib/pacman/db.lck` database locks, and repair Arch/CachyOS keyrings (`pacman-key`).
- **🧹 Cache Manager & Orphan Cleaner**: Visualize `/var/cache/pacman/pkg` disk usage, prune old versions (`paccache -r` / `paccache -rk1`), and clean unneeded orphan packages.
- **📜 Transaction Log Viewer**: Searchable audit log of recent installs, upgrades, and removals from `/var/log/pacman.log`.
- **🛡️ Real-Time Terminal Dialog**: Live modal console running elevated transactions (`pkexec`) with color tags, output streaming, and progress bar.

---

## 🚀 How to Run

```bash
# Using the launch script
./run.sh

# Or directly with Python
python3 main.py
```

### Install Desktop Launcher
To add PacGUI to your application launcher (e.g. KDE Application Launcher, GNOME App Grid, Rofi, Wofi):
```bash
cp pacgui.desktop ~/.local/share/applications/
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Ctrl + F` | Focus Search Bar |
| `Ctrl + R` | Refresh Package Databases |
| `Ctrl + U` | Check for System Updates |
| `Ctrl + O` | Open File Owner Lookup Tool |
| `Ctrl + Q` | Quit PacGUI |

---

## 🏗️ Project Structure

```
pacman-gui/
├── main.py                  # Adw.Application entry point & global actions
├── run.sh                   # Executable startup wrapper
├── pacgui.desktop           # Freedesktop desktop launcher
├── README.md                # Project documentation
├── backend/
│   ├── models.py            # Data structures (PackageInfo, FlatpakApp, QueueItem, SnapshotInfo)
│   ├── alpm_manager.py      # Fast ALPM query engine, sorting & file owner lookup
│   ├── aur_manager.py       # AUR RPC & yay/paru helper integration
│   ├── flatpak_manager.py   # Flatpak / Flathub CLI integration
│   ├── mirror_manager.py    # Reflector & rate-mirrors benchmark manager
│   ├── snapshot_manager.py  # Package snapshot backup & restore manager
│   └── runner.py            # Async PTY transaction executor with pkexec
├── ui/
│   ├── window.py            # MainWindow (NavigationSplitView, HeaderBar, ToastOverlay)
│   ├── package_list.py      # Virtualized package list, sorting & queue controls
│   ├── package_detail.py    # PreferencesPage detail view & dependency explorer
│   ├── queue_bar.py         # Multi-package queue bar & batch review dialog
│   ├── flatpak_view.py      # Flatpak application hub
│   ├── updates_view.py      # System updates management panel
│   ├── maintenance_view.py  # Maintenance dashboard (Cache, Mirrors, Snapshots, Keyring)
│   ├── file_owner_dialog.py # File owner inspector modal
│   ├── terminal_dialog.py   # Live execution console modal
│   └── style.css            # Custom Adwaita styles & badge accents
└── tests/
    └── test_backend.py      # Automated unit tests
```
