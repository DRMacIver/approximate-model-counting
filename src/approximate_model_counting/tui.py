"""Textual TUI for processing CNF files."""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import DataTable, Footer, Header, ProgressBar, Static

if TYPE_CHECKING:
    from concurrent.futures import Future


class FileStatus:
    """Track processing status for a file."""

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    SKIPPED = "skipped"
    ERROR = "error"
    TIMEOUT = "timeout"


class SubprocessRunner:
    """Runs a subprocess and allows it to be cancelled."""

    def __init__(
        self,
        cnf_path: Path,
        seed: int | None,
        timeout: float | None,
        on_start: Callable[[], None] | None = None,
    ):
        self.cnf_path = cnf_path
        self.seed = seed
        self.timeout = timeout
        self.on_start = on_start
        self.process: subprocess.Popen[str] | None = None
        self._cancelled = False
        self._lock = threading.Lock()

    def cancel(self) -> None:
        """Cancel the subprocess if running."""
        with self._lock:
            self._cancelled = True
            if self.process is not None:
                with contextlib.suppress(OSError):
                    self.process.kill()

    def run(self) -> tuple[Path, dict[str, Any]]:
        """Run the subprocess and return results."""
        # Signal that this runner is starting
        if self.on_start is not None:
            self.on_start()

        if self._cancelled:
            return self.cnf_path, {
                "file": str(self.cnf_path),
                "status": "CANCELLED",
                "root": None,
                "samples": [],
            }

        cmd = [
            sys.executable,
            "-c",
            f"""
import json
import sys
from pathlib import Path
from approximate_model_counting.cli import process_file

result = process_file(Path({str(self.cnf_path)!r}), seed={self.seed!r})
print(json.dumps(result))
""",
        ]

        try:
            with self._lock:
                if self._cancelled:
                    return self.cnf_path, {
                        "file": str(self.cnf_path),
                        "status": "CANCELLED",
                        "root": None,
                        "samples": [],
                    }
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

            stdout, _ = self.process.communicate(timeout=self.timeout)

            if self._cancelled:
                return self.cnf_path, {
                    "file": str(self.cnf_path),
                    "status": "CANCELLED",
                    "root": None,
                    "samples": [],
                }

            if self.process.returncode != 0:
                return self.cnf_path, {
                    "file": str(self.cnf_path),
                    "status": "ERROR",
                    "error": f"Process exited with code {self.process.returncode}",
                    "root": None,
                    "samples": [],
                }

            return self.cnf_path, json.loads(stdout)

        except subprocess.TimeoutExpired:
            with self._lock:
                if self.process is not None:
                    self.process.kill()
                    self.process.wait()

            from approximate_model_counting.cli import make_timeout_result

            return self.cnf_path, make_timeout_result(
                self.cnf_path, self.timeout if self.timeout else 0
            )

        except (json.JSONDecodeError, OSError) as e:
            return self.cnf_path, {
                "file": str(self.cnf_path),
                "status": "ERROR",
                "error": str(e),
                "root": None,
                "samples": [],
            }


def format_int_list(
    lst: list[int], max_width: int = 120, max_items: int | None = None
) -> str:
    """Format a list of integers compactly, wrapping at max_width.

    If max_items is set and list is longer, show first few items and "..."
    """
    if not lst:
        return "(none)"

    # Truncate if too long, but only if hiding a meaningful number of items
    truncated = False
    display_lst = lst
    if max_items is not None and len(lst) > max_items:
        # Only truncate if we're hiding at least 5 items
        # (showing "20 items... (21 total)" is silly)
        hidden_count = len(lst) - max_items
        if hidden_count >= 5:
            display_lst = lst[:max_items]
            truncated = True

    items = [str(x) for x in display_lst]
    if truncated:
        items.append(f"... ({len(lst)} total)")

    lines = []
    current_line: list[str] = []
    current_len = 0
    for item in items:
        item_len = len(item) + 2  # +2 for ", "
        if current_len + item_len > max_width and current_line:
            lines.append(", ".join(current_line))
            current_line = [item]
            current_len = len(item)
        else:
            current_line.append(item)
            current_len += item_len
    if current_line:
        lines.append(", ".join(current_line))
    return "\n".join(lines)


def format_solution_info(
    info: dict[str, Any], max_width: int = 120, include_samples: bool = False
) -> str:
    """Format solution information for display.

    Args:
        info: The solution info dict (backbone, equivalence_classes, etc.)
        max_width: Maximum line width for wrapping
        include_samples: Whether to include sample rows in output
    """
    lines = []

    # Backbone - truncate if over 20 items
    backbone = info.get("backbone", [])
    lines.append(f"Backbone ({len(backbone)} literals):")
    if backbone:
        max_show = 20 if len(backbone) > 20 else None
        lines.append(format_int_list(backbone, max_width=max_width, max_items=max_show))
    else:
        lines.append("  (none)")
    lines.append("")

    # Equivalence classes - show all (view is scrollable)
    equiv = info.get("equivalence_classes", [])
    lines.append(f"Equivalence classes: {len(equiv)}")
    for cls in equiv:
        max_show = 20 if len(cls) > 20 else None
        lines.append(f"  {format_int_list(cls, max_width=max_width - 2, max_items=max_show)}")
    lines.append("")

    # Table info - truncate variables if over 20
    table_vars = info.get("table_variables", [])
    table_size = info.get("table_size", 0)
    lines.append(f"Solution table: {table_size:,} rows, {len(table_vars)} variables")
    if table_vars:
        max_show = 20 if len(table_vars) > 20 else None
        var_str = format_int_list(table_vars, max_width=max_width, max_items=max_show)
        lines.append(f"Variables: {var_str}")

    # Sample rows - only if requested
    if include_samples:
        samples = info.get("sample_rows", [])
        if samples:
            lines.append("")
            lines.append(f"Sample rows ({len(samples)}):")
            for row in samples:
                max_show = 20 if len(row) > 20 else None
                lines.append(
                    f"  {format_int_list(row, max_width=max_width - 2, max_items=max_show)}"
                )

    return "\n".join(lines)


def format_file_status(data: dict[str, Any], max_width: int = 120) -> str:
    """Format the top-level file status."""
    status = data.get("status", "UNKNOWN")
    lines = [f"Status: {status}", ""]

    if status == "TIMEOUT":
        timeout = data.get("timeout_seconds", 0)
        lines.append(f"Timed out after {timeout:.0f} seconds")
        return "\n".join(lines)

    if status == "UNSATISFIABLE":
        lines.append("Formula is unsatisfiable - no solutions exist")
        return "\n".join(lines)

    root = data.get("root", {})
    if root:
        lines.append(format_solution_info(root, max_width=max_width, include_samples=False))

    return "\n".join(lines)


class ProcessingApp(App[None]):
    """TUI for processing CNF files."""

    CSS = """
    #main-container {
        height: 1fr;
    }

    #left-pane {
        width: 35;
        border: solid yellow;
    }

    #right-pane {
        width: 1fr;
        border: solid green;
    }

    #processing-table {
        height: 1fr;
    }

    #file-list {
        height: 8;
        border-bottom: solid gray;
    }

    #breadcrumb {
        height: 1;
        padding: 0 1;
        color: cyan;
    }

    #info-scroll {
        height: 1fr;
    }

    #info-view {
        padding: 0 1;
    }

    #samples-table {
        height: 8;
        border-top: solid gray;
    }

    #samples-table.hidden {
        display: none;
    }

    #progress-container {
        height: auto;
        padding: 1;
        dock: bottom;
    }

    #status-text {
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "go_back", "Back", show=False),
    ]

    def __init__(
        self,
        cnf_files: list[Path],
        seed: int | None,
        overwrite: bool,
        max_workers: int | None,
        timeout: float | None = None,
        auto_start: bool = True,
    ) -> None:
        super().__init__()
        self.cnf_files = cnf_files
        self.seed = seed
        self.overwrite = overwrite
        self.max_workers = max_workers
        self.timeout = timeout
        self.auto_start = auto_start
        self.file_statuses: dict[Path, str] = {}
        self.processed_count = 0
        self.total_count = 0
        self._files_to_process: list[Path] = []
        self._completed_files: list[Path] = []  # Files with JSON (done/skipped)
        self._start_times: dict[Path, float] = {}  # When each file started processing
        self._table_ready = threading.Event()
        self._stop_processing = threading.Event()
        self._runners: list[SubprocessRunner] = []
        self._executor: ThreadPoolExecutor | None = None
        self._timer_interval: float = 1.0
        # State for info view navigation
        self._current_file: Path | None = None
        self._current_data: dict[str, Any] | None = None
        self._current_sample_idx: int | None = None  # None = root view

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            with Vertical(id="left-pane"):
                yield Static("Processing", id="left-title")
                yield DataTable(id="processing-table")
            with Vertical(id="right-pane"):
                yield Static("Results", id="right-title")
                yield DataTable(id="file-list")
                yield Static("", id="breadcrumb")
                with VerticalScroll(id="info-scroll"):
                    yield Static("Select a file to view details", id="info-view")
                yield DataTable(id="samples-table")
        with Horizontal(id="progress-container"):
            yield ProgressBar(id="progress-bar", show_eta=True)
            yield Static("Ready", id="status-text")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the tables and start processing."""
        # Set up processing table (left pane) - not focusable
        proc_table = self.query_one("#processing-table", DataTable)
        proc_table.add_column("File", key="file")
        proc_table.add_column("Time", key="time", width=8)
        proc_table.can_focus = False

        # Set up file list (right pane)
        file_list = self.query_one("#file-list", DataTable)
        file_list.add_column("File", key="file")
        file_list.add_column("Status", key="status", width=10)
        file_list.cursor_type = "row"

        # Set up samples table (hidden initially)
        samples_table = self.query_one("#samples-table", DataTable)
        samples_table.add_column("#", key="idx", width=4)
        samples_table.add_column("Sample Row", key="sample")
        samples_table.cursor_type = "row"
        samples_table.add_class("hidden")

        # Determine which files to process
        for cnf in self.cnf_files:
            json_path = cnf.with_suffix(".json")
            if not self.overwrite and json_path.exists():
                self.file_statuses[cnf] = FileStatus.SKIPPED
                self._completed_files.append(cnf)
            else:
                self.file_statuses[cnf] = FileStatus.PENDING
                self._files_to_process.append(cnf)

        # Add skipped files to the file list
        self._rebuild_file_list()

        self.total_count = len(self._files_to_process)

        # Set up progress bar
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_bar.update(total=max(1, self.total_count))

        # Update status
        pending = len(self._files_to_process)
        skipped = len(self._completed_files)
        self._update_status(f"Pending: {pending}, Skipped: {skipped}")

        # Signal that the table is ready for updates
        self._table_ready.set()

        # Start timer to update elapsed times
        self.set_interval(self._timer_interval, self._update_elapsed_times)

        if self._files_to_process and self.auto_start:
            # Run in a thread to avoid blocking the UI
            self.run_worker(self._process_all, thread=True, exclusive=True)
        elif not self._files_to_process:
            self._update_status("No files to process")

        # Focus the file list by default
        file_list.focus()

    def _rebuild_file_list(self) -> None:
        """Rebuild the file list in the right pane."""
        file_list = self.query_one("#file-list", DataTable)
        scroll_y = file_list.scroll_y
        file_list.clear()

        # Sort: done/error/timeout first (newest first), then skipped (alphabetically)
        def sort_key(cnf: Path) -> tuple[int, str]:
            status = self.file_statuses.get(cnf, FileStatus.PENDING)
            if status == FileStatus.SKIPPED:
                return (1, str(cnf))
            return (0, str(cnf))

        sorted_files = sorted(self._completed_files, key=sort_key)
        for cnf in sorted_files:
            status = self.file_statuses[cnf]
            file_list.add_row(cnf.name, status, key=str(cnf))

        file_list.scroll_y = scroll_y

    def _rebuild_processing_table(self) -> None:
        """Rebuild the processing table in the left pane."""
        proc_table = self.query_one("#processing-table", DataTable)
        proc_table.clear()

        now = time.time()
        for cnf, status in self.file_statuses.items():
            if status == FileStatus.PROCESSING:
                start = self._start_times.get(cnf, now)
                elapsed = int(now - start)
                mins, secs = divmod(elapsed, 60)
                time_str = f"{mins}:{secs:02d}"
                proc_table.add_row(cnf.name, time_str, key=str(cnf))

    def _update_elapsed_times(self) -> None:
        """Update the elapsed time display for all processing files."""
        self._rebuild_processing_table()

    def _get_max_width(self) -> int:
        """Get the max width for formatting based on info scroll width."""
        info_scroll = self.query_one("#info-scroll", VerticalScroll)
        return max(40, info_scroll.size.width - 4)

    def _update_info_display(self) -> None:
        """Update the info view based on current state."""
        info_view = self.query_one("#info-view", Static)
        breadcrumb = self.query_one("#breadcrumb", Static)
        samples_table = self.query_one("#samples-table", DataTable)
        max_width = self._get_max_width()

        if self._current_file is None or self._current_data is None:
            breadcrumb.update("")
            info_view.update("Select a file to view details")
            samples_table.add_class("hidden")
            return

        filename = self._current_file.name
        status = self._current_data.get("status", "UNKNOWN")

        if self._current_sample_idx is None:
            # Root view
            breadcrumb.update(f"{filename}")
            samples_table.remove_class("hidden")

            if status == "TIMEOUT":
                timeout = self._current_data.get("timeout_seconds", 0)
                info_view.update(f"Status: TIMEOUT\n\nTimed out after {timeout:.0f} seconds")
                samples_table.add_class("hidden")
            elif status == "UNSATISFIABLE":
                info_view.update("Status: UNSATISFIABLE\n\nFormula is unsatisfiable")
                samples_table.add_class("hidden")
            else:
                root = self._current_data.get("root", {})
                if root:
                    text = f"Status: {status}\n\n"
                    text += format_solution_info(root, max_width=max_width, include_samples=False)
                    info_view.update(text)
                    self._populate_samples_table(root.get("sample_rows", []))
                else:
                    info_view.update(f"Status: {status}")
                    samples_table.add_class("hidden")
        else:
            # Sample view
            samples = self._current_data.get("samples", [])
            if self._current_sample_idx < len(samples):
                sample = samples[self._current_sample_idx]
                breadcrumb.update(
                    f"{filename} > Sample {self._current_sample_idx + 1} [Esc=back]"
                )
                formatted = format_solution_info(
                    sample, max_width=max_width, include_samples=True
                )
                info_view.update(formatted)
            else:
                breadcrumb.update(
                    f"{filename} > Sample {self._current_sample_idx + 1} [Esc=back]"
                )
                info_view.update("Sample data not available")
            samples_table.add_class("hidden")

    def _populate_samples_table(self, sample_rows: list[list[int]]) -> None:
        """Populate the samples table with sample rows."""
        samples_table = self.query_one("#samples-table", DataTable)
        samples_table.clear()

        if not sample_rows:
            samples_table.add_class("hidden")
            return

        # Get the right pane width for table content
        right_pane = self.query_one("#right-pane", Vertical)
        # Use a generous width - table cells can scroll horizontally
        max_width = max(120, right_pane.size.width - 10)
        for i, row in enumerate(sample_rows):
            # Show all items since they're selectable - don't truncate
            row_str = format_int_list(row, max_width=max_width, max_items=None)
            # Replace newlines with spaces for table display
            row_str = row_str.replace("\n", " ")
            samples_table.add_row(str(i + 1), row_str, key=str(i))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight (cursor movement) in tables."""
        if event.data_table.id == "file-list":
            self._on_file_highlighted(event)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection (Enter) in tables."""
        if event.data_table.id == "samples-table":
            self._on_sample_selected(event)

    def _on_file_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle file selection in the file list."""
        row_key = event.row_key
        if row_key is None:
            return

        cnf_path = Path(str(row_key.value))
        json_path = cnf_path.with_suffix(".json")

        # Reset to root view for new file
        self._current_file = cnf_path
        self._current_sample_idx = None

        if json_path.exists():
            try:
                with open(json_path) as f:
                    self._current_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._current_data = None
        else:
            self._current_data = None

        self._update_info_display()

    def _on_sample_selected(self, event: DataTable.RowSelected) -> None:
        """Handle sample row selection."""
        if self._current_sample_idx is not None:
            # Already in sample view, don't allow nested selection
            return

        row_key = event.row_key
        if row_key is None:
            return

        sample_idx = int(str(row_key.value))
        self._current_sample_idx = sample_idx
        self._update_info_display()

    def action_go_back(self) -> None:
        """Go back from sample view to root view."""
        if self._current_sample_idx is not None:
            self._current_sample_idx = None
            self._update_info_display()
            # Focus back on samples table
            samples_table = self.query_one("#samples-table", DataTable)
            samples_table.focus()

    def _process_all(self) -> None:
        """Process all files using subprocesses (runs in a thread)."""
        self._table_ready.wait(timeout=10)

        if self._stop_processing.is_set():
            return

        files = self._files_to_process

        def make_on_start(cnf: Path) -> Callable[[], None]:
            def on_start() -> None:
                self._start_times[cnf] = time.time()
                self.call_from_thread(self._update_file_status, cnf, FileStatus.PROCESSING)

            return on_start

        runners = [
            SubprocessRunner(f, self.seed, self.timeout, on_start=make_on_start(f))
            for f in files
        ]
        self._runners = runners

        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        try:
            futures: dict[Future[tuple[Path, dict[str, Any]]], SubprocessRunner] = {
                self._executor.submit(runner.run): runner for runner in runners
            }

            for future in as_completed(futures):
                if self._stop_processing.is_set():
                    break

                runner = futures[future]
                cnf_path = runner.cnf_path
                try:
                    _, result = future.result()

                    if result.get("status") == "CANCELLED":
                        continue

                    # Write the JSON file
                    json_path = cnf_path.with_suffix(".json")
                    json_path.write_text(json.dumps(result, indent=2))

                    if result.get("status") == "TIMEOUT":
                        self.call_from_thread(
                            self._file_completed, cnf_path, FileStatus.TIMEOUT
                        )
                    elif result.get("status") == "ERROR":
                        self.call_from_thread(
                            self._file_completed, cnf_path, FileStatus.ERROR
                        )
                    else:
                        self.call_from_thread(
                            self._file_completed, cnf_path, FileStatus.DONE
                        )
                except Exception:
                    self.call_from_thread(
                        self._file_completed, cnf_path, FileStatus.ERROR
                    )

                self.processed_count += 1
                self.call_from_thread(self._update_progress)
        finally:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

        if not self._stop_processing.is_set():
            self.call_from_thread(
                self._update_status,
                f"Done: {self.processed_count}/{self.total_count} processed",
            )

    def _update_file_status(self, cnf: Path, status: str) -> None:
        """Update the status of a file."""
        self.file_statuses[cnf] = status
        self._rebuild_processing_table()

    def _file_completed(self, cnf: Path, status: str) -> None:
        """Handle a file completing processing."""
        self.file_statuses[cnf] = status
        # Add to completed files at the beginning (newest first)
        if cnf not in self._completed_files:
            self._completed_files.insert(0, cnf)
        # Remove from start times
        self._start_times.pop(cnf, None)
        # Rebuild both tables
        self._rebuild_processing_table()
        self._rebuild_file_list()

    def _update_status(self, text: str) -> None:
        """Update the status text."""
        status_text = self.query_one("#status-text", Static)
        status_text.update(text)

    def _update_progress(self) -> None:
        """Update the progress bar."""
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_bar.update(progress=self.processed_count)

        remaining = self.total_count - self.processed_count
        processing = sum(1 for s in self.file_statuses.values() if s == FileStatus.PROCESSING)
        self._update_status(f"Processing: {processing}, Remaining: {remaining}")

    async def action_quit(self) -> None:
        """Handle quit action - cancel all processing and exit."""
        self._cleanup()
        self.exit()

    def _cleanup(self) -> None:
        """Cancel all running processes and clean up."""
        self._stop_processing.set()

        for runner in self._runners:
            runner.cancel()

        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)


def run_tui(
    cnf_files: list[Path],
    seed: int | None,
    overwrite: bool,
    max_workers: int | None,
    timeout: float | None = None,
) -> None:
    """Run the TUI for processing CNF files."""
    app = ProcessingApp(cnf_files, seed, overwrite, max_workers, timeout)
    app.run()
