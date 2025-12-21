"""Textual TUI for processing CNF files."""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor, TimeoutError, as_completed
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

    def on_mount(self) -> None:
        """Set up the file list and start processing."""
        table = self.query_one("#file-list", DataTable)
        table.add_columns("File", "Status")

        # Determine which files to process
        files_to_process: list[Path] = []
        for cnf in self.cnf_files:
            json_path = cnf.with_suffix(".json")
            if not self.overwrite and json_path.exists():
                self.file_statuses[cnf] = FileStatus.SKIPPED
            else:
                self.file_statuses[cnf] = FileStatus.PENDING
                files_to_process.append(cnf)

        # Add all files to the table
        for cnf in self.cnf_files:
            status = self.file_statuses[cnf]
            table.add_row(str(cnf), status, key=str(cnf))

        self.total_count = len(files_to_process)

        # Set up progress bar
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_bar.update(total=max(1, self.total_count))

        if files_to_process and self.auto_start:
            self.run_worker(self._process_all(files_to_process), exclusive=True)
        elif not files_to_process:
            self._update_status("No files to process")

    async def _process_all(self, files: list[Path]) -> None:
        """Process all files in parallel."""
        from approximate_model_counting.cli import _process_file_wrapper, make_timeout_result

        self._update_status(f"Processing {len(files)} files...")

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            args = [(f, self.seed) for f in files]
            futures: dict[Future[tuple[Path, dict[str, Any]]], Path] = {
                executor.submit(_process_file_wrapper, arg): arg[0] for arg in args
            }

            # Mark all as processing
            for cnf in files:
                self._update_file_status(cnf, FileStatus.PROCESSING)

            for future in as_completed(futures):
                cnf_path = futures[future]
                try:
                    _, result = future.result(timeout=self.timeout)
                    # Write the JSON file
                    json_path = cnf_path.with_suffix(".json")
                    json_path.write_text(json.dumps(result, indent=2))
                    self._update_file_status(cnf_path, FileStatus.DONE)
                except TimeoutError:
                    # Cancel and write timeout placeholder
                    future.cancel()
                    result = make_timeout_result(cnf_path, self.timeout if self.timeout else 0)
                    json_path = cnf_path.with_suffix(".json")
                    json_path.write_text(json.dumps(result, indent=2))
                    self._update_file_status(cnf_path, FileStatus.TIMEOUT)
                    self.log.warning(f"Timeout processing {cnf_path}")
                except Exception as e:
                    self._update_file_status(cnf_path, FileStatus.ERROR)
                    self.log.error(f"Error processing {cnf_path}: {e}")

                self.processed_count += 1
                self._update_progress()

        self._update_status(f"Done: {self.processed_count}/{self.total_count} files processed")

    def _update_file_status(self, cnf: Path, status: str) -> None:
        """Update the status of a file in the table."""
        self.file_statuses[cnf] = status
        table = self.query_one("#file-list", DataTable)
        table.update_cell(str(cnf), "Status", status)

    def _update_status(self, text: str) -> None:
        """Update the status text."""
        status_text = self.query_one("#status-text", Static)
        status_text.update(text)

    def _update_progress(self) -> None:
        """Update the progress bar."""
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_bar.update(progress=self.processed_count)


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
