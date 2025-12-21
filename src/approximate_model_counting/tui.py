"""Textual TUI for processing CNF files."""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Label, ProgressBar, Static

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


class ProcessingApp(App[None]):
    """TUI for processing CNF files."""

    CSS = """
    #main-container {
        height: 100%;
    }

    #file-list {
        height: 1fr;
        border: solid green;
    }

    #status-panel {
        height: auto;
        max-height: 10;
        border: solid blue;
        padding: 1;
    }

    #progress-container {
        height: auto;
        padding: 1;
    }

    .status-pending {
        color: gray;
    }

    .status-processing {
        color: yellow;
    }

    .status-done {
        color: green;
    }

    .status-skipped {
        color: cyan;
    }

    .status-error {
        color: red;
    }

    .status-timeout {
        color: orange;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
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
        self.current_file: Path | None = None
        self._files_to_process: list[Path] = []
        self._processing_order: dict[Path, int] = {}  # Track order for pending files
        self._table_ready = threading.Event()
        self._stop_processing = threading.Event()
        self._runners: list[SubprocessRunner] = []
        self._executor: ThreadPoolExecutor | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-container"):
            yield DataTable(id="file-list")
            with Horizontal(id="status-panel"):
                yield Label("Status: ", id="status-label")
                yield Static("Ready", id="status-text")
            with Horizontal(id="progress-container"):
                yield ProgressBar(id="progress-bar", show_eta=True)
        yield Footer()

    def _file_sort_key(self, cnf: Path) -> tuple[int, int | str, str]:
        """Return a sort key for ordering files in the table.

        Sort order:
        1. Processing files (alphabetically)
        2. Pending files (in processing order)
        3. Done/Error/Timeout files (alphabetically)
        4. Skipped files (alphabetically)
        """
        status = self.file_statuses.get(cnf, FileStatus.PENDING)
        path_str = str(cnf)

        if status == FileStatus.PROCESSING:
            return (0, path_str, path_str)
        elif status == FileStatus.PENDING:
            # Use processing order as secondary key
            order = self._processing_order.get(cnf, 999999)
            return (1, order, path_str)
        elif status in (FileStatus.DONE, FileStatus.ERROR, FileStatus.TIMEOUT):
            return (2, path_str, path_str)
        else:  # SKIPPED
            return (3, path_str, path_str)

    def _rebuild_table(self) -> None:
        """Rebuild the table with files in sorted order, preserving scroll position."""
        table = self.query_one("#file-list", DataTable)

        # Save current scroll position
        scroll_y = table.scroll_y

        table.clear()

        # Sort all files by the sort key
        sorted_files = sorted(self.cnf_files, key=self._file_sort_key)

        for cnf in sorted_files:
            status = self.file_statuses[cnf]
            table.add_row(str(cnf), status, key=str(cnf))

        # Restore scroll position
        table.scroll_y = scroll_y

    def on_mount(self) -> None:
        """Set up the file list and start processing."""
        table = self.query_one("#file-list", DataTable)
        table.add_column("File", key="file")
        table.add_column("Status", key="status")

        # Determine which files to process
        for cnf in self.cnf_files:
            json_path = cnf.with_suffix(".json")
            if not self.overwrite and json_path.exists():
                self.file_statuses[cnf] = FileStatus.SKIPPED
            else:
                self.file_statuses[cnf] = FileStatus.PENDING
                self._files_to_process.append(cnf)

        # Record the processing order for pending files
        for i, cnf in enumerate(self._files_to_process):
            self._processing_order[cnf] = i

        # Add all files to the table in sorted order
        sorted_files = sorted(self.cnf_files, key=self._file_sort_key)
        for cnf in sorted_files:
            status = self.file_statuses[cnf]
            table.add_row(str(cnf), status, key=str(cnf))

        self.total_count = len(self._files_to_process)

        # Set up progress bar
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_bar.update(total=max(1, self.total_count))

        # Signal that the table is ready for updates
        self._table_ready.set()

        if self._files_to_process and self.auto_start:
            # Run in a thread to avoid blocking the UI
            self.run_worker(self._process_all, thread=True, exclusive=True)
        elif not self._files_to_process:
            self._update_status("No files to process")

    def _process_all(self) -> None:
        """Process all files using subprocesses (runs in a thread)."""
        # Wait for the table to be ready before updating cells
        self._table_ready.wait(timeout=10)

        if self._stop_processing.is_set():
            return

        files = self._files_to_process
        self.call_from_thread(self._update_status, f"Processing {len(files)} files...")

        # Create runners for all files with on_start callback to mark as processing
        def make_on_start(cnf: Path) -> Callable[[], None]:
            def on_start() -> None:
                self.call_from_thread(self._update_file_status, cnf, FileStatus.PROCESSING)

            return on_start

        runners = [
            SubprocessRunner(f, self.seed, self.timeout, on_start=make_on_start(f))
            for f in files
        ]
        self._runners = runners

        # Use ThreadPoolExecutor to manage subprocess calls
        # (subprocess.run is blocking, so we use threads to parallelize)
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

                    # Skip cancelled results
                    if result.get("status") == "CANCELLED":
                        continue

                    # Write the JSON file
                    json_path = cnf_path.with_suffix(".json")
                    json_path.write_text(json.dumps(result, indent=2))

                    if result.get("status") == "TIMEOUT":
                        self.call_from_thread(
                            self._update_file_status, cnf_path, FileStatus.TIMEOUT
                        )
                    elif result.get("status") == "ERROR":
                        self.call_from_thread(
                            self._update_file_status, cnf_path, FileStatus.ERROR
                        )
                    else:
                        self.call_from_thread(
                            self._update_file_status, cnf_path, FileStatus.DONE
                        )
                except Exception:
                    self.call_from_thread(
                        self._update_file_status, cnf_path, FileStatus.ERROR
                    )

                self.processed_count += 1
                self.call_from_thread(self._update_progress)
        finally:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

        if not self._stop_processing.is_set():
            self.call_from_thread(
                self._update_status,
                f"Done: {self.processed_count}/{self.total_count} files processed",
            )

    def _update_file_status(self, cnf: Path, status: str) -> None:
        """Update the status of a file in the table and re-sort."""
        self.file_statuses[cnf] = status
        self._rebuild_table()

    def _update_status(self, text: str) -> None:
        """Update the status text."""
        status_text = self.query_one("#status-text", Static)
        status_text.update(text)

    def _update_progress(self) -> None:
        """Update the progress bar."""
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_bar.update(progress=self.processed_count)

    async def action_quit(self) -> None:
        """Handle quit action - cancel all processing and exit."""
        self._cleanup()
        self.exit()

    def _cleanup(self) -> None:
        """Cancel all running processes and clean up."""
        self._stop_processing.set()

        # Cancel all subprocess runners
        for runner in self._runners:
            runner.cancel()

        # Shutdown executor if running
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
