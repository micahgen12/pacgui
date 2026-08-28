# PacGUI 📦
> **Modern GTK4 / Libadwaita Graphical Package Manager for Arch Linux & ALPM Distributions**

PacGUI is a fast, responsive, and feature-rich graphical user interface for `pacman` and the Arch User Repository (AUR). Built using **Python**, **GTK4 / Libadwaita**, and **`pyalpm`** (ALPM C library bindings), PacGUI provides instantaneous search across tens of thousands of packages, detailed package inspection, and safe elevated operations.

---

## ✨ Features

- **⚡ Blazing Fast In-Memory Queries**: Powered by native `pyalpm` to query local databases and sync repos (`core`, `extra`, `multilib`, `cachyos`, etc.) in sub-milliseconds.
- **🎨 Modern Libadwaita UI**:
  - Adaptive sidebar with categories (Browse All, Installed, Explicit, Dependencies, Updates, Maintenance).
  - Native dark/light theme support.
  - Interactive package cards with status indicators (Installed, Update Available, Orphan, AUR).
- **🔍 Instant Search & Repo Filtering**: Filter packages by name, description, repository, or installation status with search debouncing.
- **📦 Comprehensive Package Inspector**:
  - Metadata: Description, Maintainer, Version, Installed Size, Download Size, Architecture, Licenses, Build & Install Dates.
  - Interactive Dependencies & Reverse Dependencies (click any dependency to inspect it directly).
  - Installed Files Tree.
  - Direct project website launcher.
- **🚀 System Updates Manager**:
  - Live check for repository updates.
  - One-click System Upgrade (`pacman -Syu` / `yay -Syu`).
- **🛡️ Integrated Terminal Console**:
  - Real-time modal console running elevated transactions (`pkexec`) with colored output and progress indicator.
- **🧹 Maintenance Tools**:
  - **Orphans Cleaner**: Detects unneeded dependency packages (`-Qtdq`) and cleans them with one click.
  - **Cache Manager**: Visualizes `/var/cache/pacman/pkg` disk usage and prunes old package versions (`paccache -r` / `paccache -rk1`).
  - **History Viewer**: Searchable audit log of recent installs, upgrades, and removals from `/var/log/pacman.log`.
- **🌐 Optional AUR Integration**: Seamlessly search and install Arch User Repository packages using `yay`.

---

## 🚀 How to Run

You can launch PacGUI directly using the launch script or Python:

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
│   ├── models.py            # Data structures (PackageInfo, UpdateInfo, TransactionTask)
│   ├── alpm_manager.py      # Fast ALPM query engine (pyalpm)
│   ├── aur_manager.py       # AUR RPC & helper integration
│   └── runner.py            # Async PTY transaction executor with pkexec
├── ui/
│   ├── window.py            # MainWindow (NavigationSplitView, HeaderBar, ToastOverlay)
│   ├── package_list.py      # Virtualized package list & row components
│   ├── package_detail.py    # PreferencesPage detail view & dependency explorer
│   ├── updates_view.py      # System updates management panel
│   ├── maintenance_view.py  # Cache cleaner, orphan cleaner & history log
│   ├── terminal_dialog.py   # Live execution console modal
│   └── style.css            # Custom Adwaita styles & badge accents
└── tests/
    └── test_backend.py      # Automated unit tests
```
