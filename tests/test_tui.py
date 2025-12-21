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
