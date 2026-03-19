"""Tests for the TUI module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from approximate_model_counting.tui import (
    FileStatus,
    ProcessingApp,
    format_file_status,
    format_int_list,
    format_solution_info,
)


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
    async def test_app_has_three_data_tables(self, sample_cnf: Path):
        """Test that the app has three data tables (processing, file list, samples)."""
        app = ProcessingApp(
            [sample_cnf], seed=42, overwrite=False, max_workers=None, auto_start=False
        )
        async with app.run_test(size=(120, 40)):
            from textual.widgets import DataTable

            tables = app.query(DataTable)
            assert len(tables) == 3

            # Check specific tables exist
            proc_table = app.query_one("#processing-table", DataTable)
            file_list = app.query_one("#file-list", DataTable)
            samples_table = app.query_one("#samples-table", DataTable)
            assert proc_table is not None
            assert file_list is not None
            assert samples_table is not None

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
        from textual.binding import Binding

        app = ProcessingApp([sample_cnf], seed=42, overwrite=False, max_workers=None)
        # BINDINGS is a list of Binding objects
        bindings = app.BINDINGS
        assert any(
            (isinstance(b, Binding) and b.key == "q") or (isinstance(b, tuple) and b[0] == "q")
            for b in bindings
        )


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
            futures = {executor.submit(_process_file_wrapper, (f, 42)): f for f in cnf_files}
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
    async def test_skipped_files_appear_in_file_list(self, temp_dir: Path):
        """Test that skipped files appear in the file list (right pane)."""
        cnf_a = temp_dir / "a_file.cnf"
        cnf_a.write_text("p cnf 1 1\n1 0\n")

        # Create a JSON for a_file so it gets skipped
        (temp_dir / "a_file.json").write_text("{}")

        app = ProcessingApp(
            [cnf_a],
            seed=42,
            overwrite=False,  # Don't overwrite, so a_file is skipped
            max_workers=1,
            auto_start=False,
        )

        async with app.run_test(size=(120, 40)):
            from textual.widgets import DataTable

            file_list = app.query_one("#file-list", DataTable)

            # Skipped file should be in file list
            rows = list(file_list.rows.keys())
            assert len(rows) == 1
            row_data = file_list.get_row(rows[0])
            assert "a_file.cnf" in str(row_data[0])
            assert "skipped" in str(row_data[1])

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

    @pytest.mark.asyncio
    async def test_completed_files_appear_in_file_list(self, sample_cnf: Path):
        """Test that completed files appear in the file list."""
        import asyncio

        app = ProcessingApp(
            [sample_cnf],
            seed=42,
            overwrite=True,
            max_workers=1,
            timeout=30,
            auto_start=True,
        )

        async with app.run_test(size=(120, 40)):
            from textual.widgets import DataTable

            # Wait for processing to complete
            for _ in range(100):
                await asyncio.sleep(0.1)
                if app.processed_count >= 1:
                    break

            # File should now be in the file list
            file_list = app.query_one("#file-list", DataTable)
            rows = list(file_list.rows.keys())
            assert len(rows) == 1
            row_data = file_list.get_row(rows[0])
            assert "sample.cnf" in str(row_data[0])
            assert "done" in str(row_data[1])


class TestSampleNavigation:
    """Tests for sample row navigation in the TUI."""

    @pytest.mark.asyncio
    async def test_sample_table_hidden_initially(self, sample_cnf: Path):
        """Test that samples table is hidden when no file is selected."""
        app = ProcessingApp(
            [sample_cnf], seed=42, overwrite=False, max_workers=None, auto_start=False
        )
        async with app.run_test(size=(120, 40)):
            from textual.widgets import DataTable

            samples_table = app.query_one("#samples-table", DataTable)
            assert samples_table.has_class("hidden")

    @pytest.mark.asyncio
    async def test_breadcrumb_shows_filename(self, sample_cnf: Path):
        """Test that breadcrumb is updated when a file is selected."""
        import asyncio

        app = ProcessingApp(
            [sample_cnf],
            seed=42,
            overwrite=True,
            max_workers=1,
            timeout=30,
            auto_start=True,
        )

        async with app.run_test(size=(120, 40)):
            from textual.widgets import DataTable

            # Wait for processing to complete
            for _ in range(100):
                await asyncio.sleep(0.1)
                if app.processed_count >= 1:
                    break

            # Select the file in the file list
            file_list = app.query_one("#file-list", DataTable)
            rows = list(file_list.rows.keys())
            assert len(rows) >= 1

            # Move cursor to first row (which triggers row highlighted)
            file_list.move_cursor(row=0)
            await asyncio.sleep(0.1)

            # Verify the current file is set
            assert app._current_file == sample_cnf
            assert app._current_data is not None

    @pytest.mark.asyncio
    async def test_go_back_action(self, sample_cnf: Path):
        """Test that Escape key clears sample selection."""
        app = ProcessingApp(
            [sample_cnf], seed=42, overwrite=False, max_workers=None, auto_start=False
        )
        async with app.run_test(size=(120, 40)) as pilot:
            # Set up state to simulate being in a sample view
            app._current_sample_idx = 0
            app._current_file = sample_cnf
            app._current_data = {
                "status": "SATISFIABLE",
                "samples": [{"backbone": [1], "table_size": 1}],
            }

            # Press Escape
            await pilot.press("escape")

            # Sample index should be cleared
            assert app._current_sample_idx is None


class TestFormatIntList:
    """Tests for format_int_list formatting."""

    def test_empty_list(self):
        assert format_int_list([]) == "(none)"

    def test_simple_list(self):
        result = format_int_list([1, 2, 3])
        assert result == "1, 2, 3"

    def test_wraps_long_list(self):
        # A list that needs wrapping
        long_list = list(range(1, 30))
        result = format_int_list(long_list, max_width=40)
        assert "\n" in result

    def test_negative_numbers(self):
        result = format_int_list([-1, 2, -3])
        assert result == "-1, 2, -3"

    def test_truncates_long_list(self):
        long_list = list(range(1, 101))  # 100 items
        result = format_int_list(long_list, max_items=10)
        assert "... (100 total)" in result
        assert "1, 2, 3" in result  # First items present
        assert "100" not in result or "100 total" in result  # 100 only in total count

    def test_no_truncate_when_few_hidden(self):
        """Don't truncate when hiding < 5 items (not worth the '...' noise)."""
        lst = list(range(1, 13))  # 12 items
        result = format_int_list(lst, max_items=10)
        # Only hiding 2, so should show all 12
        assert "total" not in result
        assert "12" in result


class TestFormatFileStatus:
    """Tests for format_file_status formatting (top-level status)."""

    def test_timeout_status(self):
        data = {"status": "TIMEOUT", "timeout_seconds": 60}
        result = format_file_status(data)
        assert "TIMEOUT" in result
        assert "60" in result

    def test_unsat_status(self):
        data = {"status": "UNSATISFIABLE"}
        result = format_file_status(data)
        assert "UNSATISFIABLE" in result
        assert "no solutions" in result

    def test_sat_with_backbone(self):
        data = {
            "status": "SATISFIABLE",
            "root": {
                "backbone": [1, 2, -3],
                "equivalence_classes": [],
                "table_variables": [4, 5],
                "table_size": 4,
                "sample_rows": [],
            },
        }
        result = format_file_status(data)
        assert "SATISFIABLE" in result
        assert "Backbone (3 literals)" in result
        assert "1, 2, -3" in result

    def test_empty_root(self):
        data = {"status": "SATISFIABLE", "root": {}}
        result = format_file_status(data)
        assert "SATISFIABLE" in result


class TestFormatSolutionInfo:
    """Tests for format_solution_info formatting (solution info)."""

    def test_backbone_formatting(self):
        info = {
            "backbone": [1, 2, -3],
            "equivalence_classes": [],
            "table_variables": [4, 5],
            "table_size": 4,
            "sample_rows": [],
        }
        result = format_solution_info(info)
        assert "Backbone (3 literals)" in result
        assert "1, 2, -3" in result

    def test_equivalence_classes(self):
        info = {
            "backbone": [],
            "equivalence_classes": [[1, 2], [3, 4, 5]],
            "table_variables": [],
            "table_size": 0,
        }
        result = format_solution_info(info)
        assert "Equivalence classes: 2" in result
        assert "1, 2" in result
        assert "3, 4, 5" in result

    def test_table_info(self):
        info = {
            "backbone": [],
            "equivalence_classes": [],
            "table_variables": [1, 2, 3],
            "table_size": 8,
        }
        result = format_solution_info(info)
        assert "Solution table: 8 rows, 3 variables" in result
        assert "Variables: 1, 2, 3" in result

    def test_empty_info(self):
        info = {}
        result = format_solution_info(info)
        assert "Backbone (0 literals)" in result
        assert "(none)" in result

    def test_include_samples(self):
        info = {
            "backbone": [1],
            "equivalence_classes": [],
            "table_variables": [],
            "table_size": 0,
            "sample_rows": [[1, -2], [1, 2]],
        }
        result = format_solution_info(info, include_samples=True)
        assert "Sample rows (2)" in result
        assert "1, -2" in result

    def test_include_samples_empty(self):
        info = {
            "backbone": [],
            "equivalence_classes": [],
            "table_variables": [],
            "table_size": 0,
            "sample_rows": [],
        }
        result = format_solution_info(info, include_samples=True)
        # Empty samples should not add a samples section
        assert "Sample rows" not in result
