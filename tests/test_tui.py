"""Tests for the TUI module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from approximate_model_counting.tui import FileStatus, ProcessingApp


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_cnf(temp_dir: Path) -> Path:
    """Create a sample CNF file."""
    cnf_path = temp_dir / "sample.cnf"
    cnf_path.write_text("""\
c Sample CNF
p cnf 3 3
1 2 0
-1 -2 0
2 3 0
""")
    return cnf_path


class TestFileStatus:
    """Tests for FileStatus constants."""

    def test_pending_status(self):
        assert FileStatus.PENDING == "pending"

    def test_done_status(self):
        assert FileStatus.DONE == "done"

    def test_skipped_status(self):
        assert FileStatus.SKIPPED == "skipped"

    def test_timeout_status(self):
        assert FileStatus.TIMEOUT == "timeout"


class TestProcessingAppInit:
    """Tests for ProcessingApp initialization."""

    def test_stores_cnf_files(self, sample_cnf: Path):
        app = ProcessingApp([sample_cnf], seed=42, overwrite=False, max_workers=1)
        assert app.cnf_files == [sample_cnf]

    def test_stores_seed(self, sample_cnf: Path):
        app = ProcessingApp([sample_cnf], seed=42, overwrite=False, max_workers=1)
        assert app.seed == 42

    def test_stores_overwrite(self, sample_cnf: Path):
        app = ProcessingApp([sample_cnf], seed=None, overwrite=True, max_workers=1)
        assert app.overwrite is True

    def test_stores_max_workers(self, sample_cnf: Path):
        app = ProcessingApp([sample_cnf], seed=None, overwrite=False, max_workers=4)
        assert app.max_workers == 4

    def test_initial_counts(self, sample_cnf: Path):
        app = ProcessingApp([sample_cnf], seed=None, overwrite=False, max_workers=1)
        assert app.processed_count == 0
        assert app.total_count == 0


class TestProcessingAppUI:
    """Tests for ProcessingApp UI components."""

    @pytest.mark.asyncio
    async def test_app_has_header(self, sample_cnf: Path):
        """Test that the app has a header."""
        app = ProcessingApp(
            [sample_cnf], seed=42, overwrite=False, max_workers=None, auto_start=False
        )
        async with app.run_test(size=(120, 40)):
            from textual.widgets import Header

            headers = app.query(Header)
            assert len(headers) == 1

    @pytest.mark.asyncio
    async def test_app_has_footer(self, sample_cnf: Path):
        """Test that the app has a footer."""
        app = ProcessingApp(
            [sample_cnf], seed=42, overwrite=False, max_workers=None, auto_start=False
        )
        async with app.run_test(size=(120, 40)):
            from textual.widgets import Footer

            footers = app.query(Footer)
            assert len(footers) == 1

    @pytest.mark.asyncio
    async def test_app_has_data_table(self, sample_cnf: Path):
        """Test that the app has a data table."""
        app = ProcessingApp(
            [sample_cnf], seed=42, overwrite=False, max_workers=None, auto_start=False
        )
        async with app.run_test(size=(120, 40)):
            from textual.widgets import DataTable

            tables = app.query(DataTable)
            assert len(tables) == 1

    @pytest.mark.asyncio
    async def test_app_has_progress_bar(self, sample_cnf: Path):
        """Test that the app has a progress bar."""
        app = ProcessingApp(
            [sample_cnf], seed=42, overwrite=False, max_workers=None, auto_start=False
        )
        async with app.run_test(size=(120, 40)):
            from textual.widgets import ProgressBar

            bars = app.query(ProgressBar)
            assert len(bars) == 1

    def test_quit_binding_registered(self, sample_cnf: Path):
        """Test that 'q' binding exists."""
        app = ProcessingApp([sample_cnf], seed=42, overwrite=False, max_workers=None)
        # Check that the binding is registered (BINDINGS is a list of tuples)
        bindings = app.BINDINGS
        assert any(b[0] == "q" for b in bindings)  # type: ignore[index]


class TestProcessingLogic:
    """Tests for the file processing logic (outside TUI context)."""

    def test_process_file_wrapper_works(self, sample_cnf: Path):
        """Test that the processing wrapper works with ProcessPoolExecutor."""
        from concurrent.futures import ProcessPoolExecutor

        from approximate_model_counting.cli import _process_file_wrapper

        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_process_file_wrapper, (sample_cnf, 42))
            path, result = future.result(timeout=30)

        assert path == sample_cnf
        assert result["status"] == "SATISFIABLE"
        assert "root" in result

    def test_process_multiple_files_in_parallel(self, temp_dir: Path):
        """Test that multiple files can be processed in parallel."""
        from concurrent.futures import ProcessPoolExecutor, as_completed

        from approximate_model_counting.cli import _process_file_wrapper

        # Create multiple CNF files
        cnf_files = []
        for i in range(3):
            cnf = temp_dir / f"test_{i}.cnf"
            cnf.write_text(f"p cnf {i + 1} 1\n{' '.join(str(j + 1) for j in range(i + 1))} 0\n")
            cnf_files.append(cnf)

        results = {}
        with ProcessPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(_process_file_wrapper, (f, 42)): f for f in cnf_files
            }
            for future in as_completed(futures):
                path, result = future.result(timeout=30)
                results[path] = result

        assert len(results) == 3
        for cnf in cnf_files:
            assert cnf in results
            assert results[cnf]["status"] == "SATISFIABLE"


class TestFileSorting:
    """Tests for file sorting in the TUI."""

    @pytest.mark.asyncio
    async def test_pending_files_sorted_before_skipped(self, temp_dir: Path):
        """Test that pending files appear before skipped files."""
        # Create CNF files with names that would sort differently alphabetically
        cnf_z = temp_dir / "z_file.cnf"
        cnf_a = temp_dir / "a_file.cnf"
        cnf_z.write_text("p cnf 1 1\n1 0\n")
        cnf_a.write_text("p cnf 1 1\n1 0\n")

        # Create a JSON for a_file so it gets skipped
        (temp_dir / "a_file.json").write_text("{}")

        app = ProcessingApp(
            [cnf_z, cnf_a],  # z first in input
            seed=42,
            overwrite=False,  # Don't overwrite, so a_file is skipped
            max_workers=1,
            auto_start=False,
        )

        async with app.run_test(size=(120, 40)):
            from textual.widgets import DataTable

            table = app.query_one("#file-list", DataTable)

            # Get row order
            rows = list(table.rows.keys())
            assert len(rows) == 2

            # z_file should be first (pending), a_file second (skipped)
            # Even though 'a' comes before 'z' alphabetically
            row_data = [table.get_row(r) for r in rows]
            assert "z_file.cnf" in str(row_data[0][0])
            assert "a_file.cnf" in str(row_data[1][0])

    @pytest.mark.asyncio
    async def test_skipped_files_sorted_alphabetically(self, temp_dir: Path):
        """Test that skipped files are sorted alphabetically."""
        # Create CNF files
        cnf_b = temp_dir / "b_file.cnf"
        cnf_a = temp_dir / "a_file.cnf"
        cnf_b.write_text("p cnf 1 1\n1 0\n")
        cnf_a.write_text("p cnf 1 1\n1 0\n")

        # Create JSONs for both so they get skipped
        (temp_dir / "b_file.json").write_text("{}")
        (temp_dir / "a_file.json").write_text("{}")

        app = ProcessingApp(
            [cnf_b, cnf_a],  # b first in input
            seed=42,
            overwrite=False,
            max_workers=1,
            auto_start=False,
        )

        async with app.run_test(size=(120, 40)):
            from textual.widgets import DataTable

            table = app.query_one("#file-list", DataTable)

            rows = list(table.rows.keys())
            row_data = [table.get_row(r) for r in rows]

            # Both skipped, so should be alphabetical: a before b
            assert "a_file.cnf" in str(row_data[0][0])
            assert "b_file.cnf" in str(row_data[1][0])


class TestCleanup:
    """Tests for cleanup on quit."""

    @pytest.mark.asyncio
    async def test_quit_cancels_runners(self, sample_cnf: Path):
        """Test that pressing q cancels running subprocesses."""
        app = ProcessingApp(
            [sample_cnf],
            seed=42,
            overwrite=True,
            max_workers=1,
            timeout=60,  # Long timeout
            auto_start=True,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            # Give it a moment to start processing
            await pilot.pause()

            # Quit the app
            await pilot.press("q")

            # Verify cleanup was triggered
            assert app._stop_processing.is_set()


class TestTUIWithProcessing:
    """Tests for the TUI with actual processing enabled."""

    @pytest.mark.asyncio
    async def test_tui_processes_file_with_auto_start(self, sample_cnf: Path):
        """Test that the TUI can process a file with auto_start=True."""
        import asyncio

        app = ProcessingApp(
            [sample_cnf],
            seed=42,
            overwrite=True,
            max_workers=1,
            timeout=30,
            auto_start=True,  # Enable actual processing
        )

        async with app.run_test(size=(120, 40)):
            # Wait for processing to complete (with timeout)
            for _ in range(100):  # Max 10 seconds
                await asyncio.sleep(0.1)
                if app.processed_count >= 1:
                    break

            # Verify processing completed
            assert app.processed_count == 1
            assert app.file_statuses[sample_cnf] == FileStatus.DONE

            # Verify JSON file was created
            json_path = sample_cnf.with_suffix(".json")
            assert json_path.exists()

    @pytest.mark.asyncio
    async def test_tui_processes_multiple_files(self, temp_dir: Path):
        """Test that the TUI can process multiple files."""
        import asyncio

        # Create multiple CNF files
        cnf_files = []
        for i in range(3):
            cnf = temp_dir / f"test_{i}.cnf"
            cnf.write_text(f"p cnf {i + 1} 1\n{' '.join(str(j + 1) for j in range(i + 1))} 0\n")
            cnf_files.append(cnf)

        app = ProcessingApp(
            cnf_files,
            seed=42,
            overwrite=True,
            max_workers=2,
            timeout=30,
            auto_start=True,
        )

        async with app.run_test(size=(120, 40)):
            # Wait for processing to complete
            for _ in range(100):  # Max 10 seconds
                await asyncio.sleep(0.1)
                if app.processed_count >= 3:
                    break

            assert app.processed_count == 3
            for cnf in cnf_files:
                assert app.file_statuses[cnf] == FileStatus.DONE
                assert cnf.with_suffix(".json").exists()
