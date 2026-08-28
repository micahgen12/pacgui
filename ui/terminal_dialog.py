"""
Terminal dialog for live execution of pacman transactions with real-time output.
"""

import re
from typing import Callable, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Pango

from backend.models import TransactionTask
from backend.runner import TransactionRunner


class TerminalDialog(Adw.Window):
    """Modal dialog displaying live terminal logs during a package manager transaction."""

    def __init__(
        self,
        parent_window: Gtk.Window,
        task: TransactionTask,
        runner: TransactionRunner,
        on_complete: Optional[Callable[[bool], None]] = None,
        aur_helper: Optional[str] = "yay",
    ):
        super().__init__(
            transient_for=parent_window,
            modal=True,
            title=task.title,
            default_width=750,
            default_height=500,
        )
        self.task = task
        self.runner = runner
        self.on_complete = on_complete
        self.aur_helper = aur_helper
        self.is_finished = False

        self._setup_ui()
        self._start_transaction()

    def _setup_ui(self):
        # Toolbar View
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        # Header Bar
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        header.set_show_start_title_buttons(False)
        toolbar_view.add_top_bar(header)

        # Title widget
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.title_label = Gtk.Label(label=self.task.title, css_classes=["title"])
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.subtitle_label = Gtk.Label(
            label=self.task.description,
            css_classes=["subtitle"],
        )
        self.subtitle_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_box.append(self.title_label)
        title_box.append(self.subtitle_label)
        header.set_title_widget(title_box)

        # Action / Close button
        self.action_btn = Gtk.Button(label="Cancel")
        self.action_btn.connect("clicked", self._on_action_btn_clicked)
        header.pack_end(self.action_btn)

        # Spinner in header
        self.spinner = Gtk.Spinner()
        self.spinner.start()
        header.pack_start(self.spinner)

        # Main content box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)

        # Command display banner
        self.cmd_label = Gtk.Label(
            label="Preparing command...",
            halign=Gtk.Align.START,
            css_classes=["code-pill"],
        )
        self.cmd_label.set_selectable(True)
        main_box.append(self.cmd_label)

        # Scrolled Text View for terminal output
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scrolled.add_css_class("terminal-window")

        self.text_view = Gtk.TextView(
            editable=False,
            cursor_visible=False,
            wrap_mode=Gtk.WrapMode.CHAR,
            monospace=True,
        )
        self.text_view.add_css_class("terminal-textview")
        self.buffer = self.text_view.get_buffer()

        # Tags for colored text
        self._init_tags()

        scrolled.set_child(self.text_view)
        main_box.append(scrolled)

        # Status Bar / Progress Indicator
        self.progress_bar = Gtk.ProgressBar(show_text=False)
        self.progress_bar.pulse()
        main_box.append(self.progress_bar)

        toolbar_view.set_content(main_box)

    def _init_tags(self):
        """Create formatting tags for terminal buffer."""
        self.buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        self.buffer.create_tag("green", foreground="#2ec27e")
        self.buffer.create_tag("red", foreground="#e01b24")
        self.buffer.create_tag("blue", foreground="#3584e4")
        self.buffer.create_tag("orange", foreground="#e66100")
        self.buffer.create_tag("dim", foreground="#888888")

    def _start_transaction(self):
        """Begin transaction execution with the runner."""
        try:
            self.runner.execute(
                task=self.task,
                on_output=self._handle_output,
                on_finished=self._handle_finished,
                on_start=self._handle_started,
                aur_helper=self.aur_helper,
            )
        except Exception as e:
            self._handle_output(f"Failed to start process: {e}\n")
            self._handle_finished(-1, False)

    def _handle_started(self, cmd: List[str]):
        """Called when command starts."""
        cmd_str = " ".join(cmd)
        self.cmd_label.set_label(f"$ {cmd_str}")
        self._append_text(f"Starting transaction...\nCommand: {cmd_str}\n\n", "dim")

    def _clean_ansi(self, text: str) -> str:
        """Strip ANSI escape sequences from text for clean log output."""
        ansi_regex = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_regex.sub("", text)

    def _append_text(self, text: str, tag_name: Optional[str] = None):
        """Append text to buffer and scroll to end."""
        end_iter = self.buffer.get_end_iter()
        cleaned = self._clean_ansi(text)
        if tag_name:
            self.buffer.insert_with_tags_by_name(end_iter, cleaned, tag_name)
        else:
            self.buffer.insert(end_iter, cleaned)

        # Auto scroll to bottom
        mark = self.buffer.create_mark(None, self.buffer.get_end_iter(), False)
        self.text_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

    def _handle_output(self, line: str):
        """Stream line to terminal output buffer."""
        # Check for error or success markers
        lower = line.lower()
        if "error:" in lower or "failed" in lower:
            self._append_text(line, "red")
        elif "warning:" in lower:
            self._append_text(line, "orange")
        elif "success" in lower or "completed" in lower or "done" in lower:
            self._append_text(line, "green")
        else:
            self._append_text(line)

        self.progress_bar.pulse()

    def _handle_finished(self, returncode: int, success: bool):
        """Called when transaction process exits."""
        self.is_finished = True
        self.spinner.stop()
        self.spinner.set_visible(False)
        self.progress_bar.set_visible(False)

        if success:
            self.title_label.set_label(f"✓ {self.task.title} Completed")
            self._append_text("\n[PacGUI]: Transaction completed successfully.\n", "green")
            self.action_btn.set_label("Done")
            self.action_btn.add_css_class("suggested-action")
        else:
            self.title_label.set_label(f"✗ {self.task.title} Failed")
            self._append_text(f"\n[PacGUI]: Transaction exited with return code {returncode}.\n", "red")
            self.action_btn.set_label("Close")
            self.action_btn.add_css_class("destructive-action")

        if self.on_complete:
            self.on_complete(success)

    def _on_action_btn_clicked(self, button):
        """Handle button click (Cancel or Close/Done)."""
        if not self.is_finished:
            # Running -> cancel
            self.runner.cancel()
            self._append_text("\n[PacGUI]: Cancelling transaction...\n", "orange")
            self.action_btn.set_sensitive(False)
        else:
            # Finished -> close window
            self.close()
